import time
from typing import Any

import httpx
import structlog

from app.config import settings
from app.observability.logger import log_llm_call

log = structlog.get_logger()

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "google/gemini-2.5-flash"

# Gemini 2.5 Flash pricing (USD per 1M tokens, as of 2026-05)
_COST_PER_INPUT_TOKEN = 0.50 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 1.50 / 1_000_000

_SYSTEM_PROMPT = (
    "You are a precise technical summariser for an AI research briefing. "
    "Write 3-5 sentences. Cover: what was announced or found, why it matters, "
    "and any key numbers or names. Be factual. No filler phrases."
)


async def summarise(title: str, abstract: str, source_name: str) -> str:
    """
    Summarise an article for Mode A storage.
    For Mode B (arXiv), the abstract is stored directly — do not call this function.
    Returns a 3-5 sentence summary string.
    """
    user_prompt = f"Title: {title}\n\nContent: {abstract}"

    payload: dict[str, Any] = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 300,
        "temperature": 0.2,
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/briefcast",
                },
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("summariser.http_error", source=source_name, error=str(exc))
        raise

    latency_ms = (time.monotonic() - t0) * 1000
    data = response.json()
    summary: str = data["choices"][0]["message"]["content"].strip()

    usage = data.get("usage", {})
    input_tokens: int = usage.get("prompt_tokens", 0)
    output_tokens: int = usage.get("completion_tokens", 0)
    cost = input_tokens * _COST_PER_INPUT_TOKEN + output_tokens * _COST_PER_OUTPUT_TOKEN

    log_llm_call(
        model=_MODEL,
        task="summarise",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=cost,
        source=source_name,
    )

    return summary
