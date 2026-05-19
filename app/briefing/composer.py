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
    "You write a concise daily AI briefing formatted as Telegram HTML. "
    "Rules: use <b>title</b> for each headline; end each item with [Source Name] as citation; "
    "no preamble, no sign-off, no 'Here is your briefing'; start directly with item 1; "
    "3-4 sentences per item; cover what happened and why it matters to AI practitioners."
)

_MIN_ITEMS = 6
_MAX_ITEMS = 8


def _select(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Pick up to _MAX_ITEMS articles sorted by score.
    Guarantees at least one Tier 1 article if any exist in the corpus.
    """
    # articles are already score-sorted descending by the caller
    selected = list(articles[:_MAX_ITEMS])

    has_tier1 = any(a.get("source_tier") == 1 for a in selected)
    if not has_tier1:
        tier1_outside = [a for a in articles[_MAX_ITEMS:] if a.get("source_tier") == 1]
        if tier1_outside:
            selected[-1] = tier1_outside[0]

    return selected


def _build_user_prompt(articles: list[dict[str, Any]]) -> str:
    today = date.today().strftime("%B %d, %Y")
    lines = [f"Compose the daily AI briefing for {today} from these {len(articles)} articles:\n"]
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source_name']}] {a['title']}\n   {a.get('summary', '')}\n   URL: {a['url']}\n"
        )
    return "\n".join(lines)


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
                    "max_tokens": 1200,
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
    log.info("composer.done", selected=len(selected), latency_ms=round(latency_ms, 1))
    return text
