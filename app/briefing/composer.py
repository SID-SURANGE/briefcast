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
    "You write a daily AI briefing for Telegram using HTML formatting only. "
    "No markdown asterisks, no raw URLs, no bracket-style links, no typed separator lines.\n\n"

    "HEADER (output literally, substituting DATE and COUNT from the user prompt):\n"
    "📅 <b>BRIEFCAST | {DATE}</b>  ·  <code>{COUNT} articles</code>\n\n"

    "BODY — group articles by company/source. For each group:\n"
    "  1. Source header line: <source_emoji> <b><u>Source Name</u></b>\n"
    "     Emoji per source: Google AI → 🔵  Google Research → 🔵  Google Cloud AI → 🔵  "
    "Google DeepMind → 🔵  OpenAI → ⚫  Anthropic → 🟠  Meta AI → 🔶  "
    "Hugging Face → 🟡  arXiv → 🟥  Microsoft → 🟦  NVIDIA → 🟩  other → 🔹\n"
    "  2. Each article — strictly in this order, each element on its own line:\n"
    "       🔷 <b>Full Project or Paper Title</b>\n"
    "       • <i>What it is</i> — one concise sentence summarising the technology. "
    "Wrap model names, version strings, and key metrics in <code>tags</code> "
    "(e.g. <code>Gemini 2.5 Flash</code>, <code>94.7%</code>).\n"
    "\n"
    "       <blockquote>💡 Why it matters — one sentence on practical impact or implication for AI practitioners.</blockquote>\n"
    "\n"
    "       🔗 <a href=\"URL\">Read Paper</a>  (use 'Read Paper' for arXiv, 'Read Post' for blogs)\n"
    "\n"
    "  3. Separate each source group with TWO blank lines. No dashes, no divider characters whatsoever.\n\n"

    "FOOTER (output literally):\n"
    "<i>Briefcast · next briefing tomorrow at 09:00 IST</i>\n\n"

    "Rules: AI and ML content only. No preamble. No sign-off. No 'Here is your briefing'. "
    "Never run the bold title and any subtitle on the same line."
)

_MAX_ITEMS = 10
_DEFAULT_MAX_PER_COMPANY = 2
_COMPANY_CAP_OVERRIDES: dict[str, int] = {
    "google": 4,  # Tier 1 priority — up to 4 Google/DeepMind articles
}

# Source name substrings that belong to the same company for diversity capping.
COMPANY_GROUPS: dict[str, list[str]] = {
    "google": ["google", "deepmind"],
    "openai": ["openai"],
    "anthropic": ["anthropic"],
    "meta": ["meta"],
    "huggingface": ["hugging face", "huggingface"],
    "arxiv": ["arxiv"],
    "mistral": ["mistral"],
    "cohere": ["cohere"],
    "microsoft": ["microsoft"],
    "nvidia": ["nvidia"],
    "xai": ["xai", "grok"],
}


def _company_key(source_name: str) -> str:
    """Map a source name to a company key for diversity capping."""
    name_lower = source_name.lower()
    for key, patterns in COMPANY_GROUPS.items():
        if any(p in name_lower for p in patterns):
            return key
    return name_lower


def _select(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Pick up to _MAX_ITEMS articles with per-company diversity cap.
    Guarantees at least one Tier 1 article if any exist in the corpus.
    Articles must be pre-sorted by score descending.
    """
    selected: list[dict[str, Any]] = []
    company_counts: dict[str, int] = {}

    for article in articles:
        if len(selected) >= _MAX_ITEMS:
            break
        key = _company_key(article.get("source_name", ""))
        cap = _COMPANY_CAP_OVERRIDES.get(key, _DEFAULT_MAX_PER_COMPANY)
        if company_counts.get(key, 0) < cap:
            selected.append(article)
            company_counts[key] = company_counts.get(key, 0) + 1

    # Guarantee at least one Tier 1 if none made it through
    has_tier1 = any(a.get("source_tier") == 1 for a in selected)
    if not has_tier1:
        for article in articles:
            if article.get("source_tier") == 1 and article not in selected:
                selected[-1] = article
                break

    return selected


def _build_user_prompt(articles: list[dict[str, Any]]) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    lines = [f"DATE: {today}\nCOUNT: {len(articles)}\n\nCompose the briefing from these {len(articles)} articles:\n"]
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source_name']}] {a['title']}\n   {a.get('summary', '')}\n   URL: {a['url']}\n"
        )
    return "\n".join(lines)


_TELEGRAM_INLINE_TAGS = ["b", "i", "u", "s", "code", "pre"]


def close_open_tags(text: str) -> str:
    """Close any inline HTML tags left open by a truncated LLM response."""
    open_tags: list[str] = []
    for m in re.finditer(r"<(/?)(\w+)[^>]*>", text):
        closing, tag = m.group(1), m.group(2).lower()
        if tag not in _TELEGRAM_INLINE_TAGS:
            continue
        if closing:
            if open_tags and open_tags[-1] == tag:
                open_tags.pop()
        else:
            open_tags.append(tag)
    for tag in reversed(open_tags):
        text += f"</{tag}>"
    return text


async def compose(articles: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """
    Select top articles, call Haiku to compose a Telegram-HTML briefing.
    Returns (briefing_text, source_keys) where source_keys is the ordered list of
    unique company keys that appeared in the briefing (used to build drill-down buttons).
    Caller should pass articles sorted by score descending (output of ranker.rank()).
    Returns ("", []) if no articles are provided.
    """
    if not articles:
        log.warning("composer.no_articles")
        return "", []

    selected = _select(articles)

    # Collect unique company keys in appearance order for the inline keyboard
    source_keys: list[str] = []
    seen: set[str] = set()
    for a in selected:
        key = _company_key(a.get("source_name", ""))
        if key not in seen:
            source_keys.append(key)
            seen.add(key)

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
    return text, source_keys
