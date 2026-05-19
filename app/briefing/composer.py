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
    "You write a sharp daily AI briefing in Telegram HTML. Follow this exact structure:\n\n"

    "HEADER (output this literally, substituting today's date):\n"
    "📡 <b>AI Briefing</b> · {DATE}\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"

    "BODY — group items by company/source. For each group:\n"
    "  - One header line: <emoji> <b>Source Name</b>\n"
    "  - Use these emoji per source: Google DeepMind → 🔵  Google AI → 🔵  OpenAI → ⚫  "
    "Anthropic → 🟠  Meta AI → 🔷  Hugging Face → 🟡  arXiv → 📄  other → 🔹\n"
    "  - Each item under the group: <b>headline</b> on its own line, then exactly 1 sentence "
    "(why it matters to AI practitioners — the impact or implication, not a restatement of the title), "
    "then <a href=\"URL\">↗ read more</a>\n"
    "  - Separate groups with a blank line\n\n"

    "FOOTER (output this literally):\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "<i>Briefcast · daily at 09:00 IST</i>\n\n"

    "Rules: AI and ML content only — skip anything not about models, research, or tooling. "
    "No preamble. No sign-off. No 'Here is your briefing'."
)

_MAX_ITEMS = 10
_MAX_PER_COMPANY = 2

# Source name substrings that belong to the same company for diversity capping.
_COMPANY_GROUPS: dict[str, list[str]] = {
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
    for key, patterns in _COMPANY_GROUPS.items():
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
        if company_counts.get(key, 0) < _MAX_PER_COMPANY:
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
    lines = [f"DATE: {today}\n\nCompose the briefing from these {len(articles)} articles:\n"]
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source_name']}] {a['title']}\n   {a.get('summary', '')}\n   URL: {a['url']}\n"
        )
    return "\n".join(lines)


_TELEGRAM_INLINE_TAGS = ["b", "i", "u", "s", "code", "pre"]


def _close_open_tags(text: str) -> str:
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


async def compose(articles: list[dict[str, Any]]) -> str:
    """
    Select top articles, call Haiku to compose a Telegram-HTML briefing, return the text.
    Caller should pass articles sorted by score descending (output of ranker.rank()).
    Returns empty string if no articles are provided.
    """
    if not articles:
        log.warning("composer.no_articles")
        return ""

    selected = _select(articles)
    user_prompt = _build_user_prompt(selected)

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/briefcast",
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
    text = _close_open_tags(text)
    log.info("composer.done", selected=len(selected), latency_ms=round(latency_ms, 1))
    return text
