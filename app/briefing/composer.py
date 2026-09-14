import re
import time
from datetime import date
from typing import Any

import httpx
import structlog

from app.config import settings
from app.observability.logger import log_llm_call

log = structlog.get_logger()

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "anthropic/claude-haiku-4-5"

_COST_PER_INPUT_TOKEN = 1.00 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 5.00 / 1_000_000

_SYSTEM_PROMPT = (
    "You write a daily AI briefing for a web page using HTML formatting only. "
    "No markdown asterisks, no raw URLs, no bracket-style links, no typed separator lines.\n\n"

    "HEADER (output literally, substituting DATE and COUNT from the user prompt):\n"
    "📅 <b>BRIEFCAST | {DATE}</b>  ·  <code>{COUNT} articles</code>\n\n"

    "BODY — group articles by source blog. Use EXACTLY this format for every group:\n\n"
    "<source_emoji> <b><u>Source Name</u></b>\n\n"
    "<b>First Article Title</b>\n"
    "<blockquote>• <i>One sentence on what it is.</i>\n"
    "\n"
    "💡 <i>One sentence on why it matters.</i>\n"
    "\n"
    "🔗 <a href=\"URL\">Read Post</a></blockquote>\n\n"
    "<b>Second Article Title (same source)</b>\n"
    "<blockquote>• <i>One sentence on what it is.</i>\n"
    "\n"
    "💡 <i>One sentence on why it matters.</i>\n"
    "\n"
    "🔗 <a href=\"URL\">Read Post</a></blockquote>\n\n"
    "<source_emoji> <b><u>Next Source</u></b>\n\n"
    "<b>Article Title</b>\n"
    "<blockquote>...</blockquote>\n\n"
    "CRITICAL RULES for the format above:\n"
    "  - ONE source header per blog — never repeat it between articles from the same source.\n"
    "  - All articles from the same source follow consecutively under their single header.\n"
    "  - Article title is OUTSIDE the blockquote — always visible. Only the detail content goes inside <blockquote>.\n"
    "  - One blank line between source header and first article title. One blank line between articles.\n"
    "  - Each article's detail content is ONE <blockquote> block. Do NOT nest blockquotes inside.\n"
    "  - The 💡 line is plain italic text inside the blockquote — not a nested blockquote.\n"
    "  - TWO blank lines between source groups. No dashes, no dividers.\n"
    "  - Do NOT output literal placeholder text like '(blank line)' or '<source_emoji>'.\n"
    "  Emoji per source: Google AI Blog → 🔵  Google Research Blog → 🔵  "
    "Google Cloud AI Blog → 🔵  Google DeepMind Blog → 🔵  other → 🔹\n"
    "  Wrap model names, version strings, and key metrics in <code>tags</code> "
    "(e.g. <code>Gemini 2.5 Flash</code>, <code>94.7%</code>) in the • line.\n"
    "  Use 'Read Post' for all sources.\n\n"

    "FOOTER (output literally):\n"
    "<i>Briefcast · next briefing tomorrow · 💬 type any question to dig deeper into today's stories</i>\n\n"

    "Rules: AI and ML content only. No preamble. No sign-off. No 'Here is your briefing'. "
    "Never run the bold title and any subtitle on the same line."
)

_MAX_ITEMS = 8
# Per-blog cap, not per-company: the registry is Google-family-only (see ADR 016),
# so there's no longer a cross-company balance to strike — this just stops one
# blog having a big publishing day from crowding out the other three.
_DEFAULT_MAX_PER_SOURCE = 3


def _source_key(source_name: str) -> str:
    """Diversity-capping key — one entry per exact source blog."""
    return source_name.lower()


def _select(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Pick up to _MAX_ITEMS articles with a per-source diversity cap.
    Articles must be pre-sorted by score descending.
    """
    selected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    for article in articles:
        if len(selected) >= _MAX_ITEMS:
            break
        key = _source_key(article.get("source_name", ""))
        if source_counts.get(key, 0) < _DEFAULT_MAX_PER_SOURCE:
            selected.append(article)
            source_counts[key] = source_counts.get(key, 0) + 1

    return selected


def _build_user_prompt(articles: list[dict[str, Any]]) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    lines = [f"DATE: {today}\nCOUNT: {len(articles)}\n\nCompose the briefing from these {len(articles)} articles:\n"]
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source_name']}] {a['title']}\n   {a.get('summary', '')}\n   URL: {a['url']}\n"
        )
    return "\n".join(lines)


_INLINE_TAGS = ["b", "i", "u", "s", "code", "pre"]


def close_open_tags(text: str) -> str:
    """Close any inline HTML tags left open by a truncated LLM response."""
    open_tags: list[str] = []
    for m in re.finditer(r"<(/?)(\w+)[^>]*>", text):
        closing, tag = m.group(1), m.group(2).lower()
        if tag not in _INLINE_TAGS:
            continue
        if closing:
            if open_tags and open_tags[-1] == tag:
                open_tags.pop()
        else:
            open_tags.append(tag)
    for tag in reversed(open_tags):
        text += f"</{tag}>"
    return text


async def compose(articles: list[dict[str, Any]]) -> tuple[str, list[str], set[str]]:
    """
    Select top articles, call Haiku to compose an HTML briefing.
    Returns (briefing_text, source_keys, shown_urls) where source_keys is the ordered
    list of unique source keys in the briefing and shown_urls is the set of article
    URLs included in the briefing.
    Caller should pass articles sorted by score descending (output of ranker.rank()).
    Returns ("", [], set()) if no articles are provided.
    """
    if not articles:
        log.warning("composer.no_articles")
        return "", [], set()

    selected = _select(articles)

    # Collect unique source keys in appearance order (kept for a possible future
    # archive/filter view — not read by the current web page).
    source_keys: list[str] = []
    seen: set[str] = set()
    shown_urls: set[str] = set()
    for a in selected:
        key = _source_key(a.get("source_name", ""))
        if key not in seen:
            source_keys.append(key)
            seen.add(key)
        shown_urls.add(a.get("url", ""))

    user_prompt = _build_user_prompt(selected)

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": settings.openrouter_app_referer,
                },
                json={
                    "model": _MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.4,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("composer.http_error", error=str(exc))
        raise

    latency_ms = (time.monotonic() - t0) * 1000
    data = response.json()
    text: str = data["choices"][0]["message"]["content"].strip()

    usage = data.get("usage", {})
    input_tokens: int = usage.get("prompt_tokens", 0)
    output_tokens: int = usage.get("completion_tokens", 0)
    cost = input_tokens * _COST_PER_INPUT_TOKEN + output_tokens * _COST_PER_OUTPUT_TOKEN

    log_llm_call(
        model=_MODEL,
        task="briefing",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=cost,
        source="briefing",
    )
    text = close_open_tags(text)
    log.info("composer.done", selected=len(selected), latency_ms=round(latency_ms, 1))
    return text, source_keys, shown_urls
