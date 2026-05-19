import time
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
    "You are a knowledgeable AI assistant in a personal Telegram bot. "
    "Answer clearly and concisely. Use Telegram HTML formatting where helpful: "
    "<b>bold</b> for key terms, <code>code</code> for technical snippets. "
    "Do not use markdown — only Telegram HTML tags."
)


async def chat(query: str) -> str:
    """Direct LLM conversation with no retrieval. Uses Haiku for speed and cost."""
    payload: dict[str, Any] = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "max_tokens": 800,
        "temperature": 0.7,
    }

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
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("chat_responder.http_error", error=str(exc))
        raise

    latency_ms = (time.monotonic() - t0) * 1000
    data = response.json()
    answer: str = data["choices"][0]["message"]["content"].strip()

    usage = data.get("usage", {})
    input_tokens: int = usage.get("prompt_tokens", 0)
    output_tokens: int = usage.get("completion_tokens", 0)
    cost = input_tokens * _COST_PER_INPUT_TOKEN + output_tokens * _COST_PER_OUTPUT_TOKEN

    log_llm_call(
        model=_MODEL,
        task="chat",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=cost,
        source="telegram",
    )
    log.info("chat_responder.done", latency_ms=round(latency_ms, 1))
    return answer
