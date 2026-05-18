import time

import httpx
import structlog

from app.config import settings
from app.db import SessionLocal
from app.observability.logger import log_llm_call
from app.processing.embedder import embed
from app.rag.retriever import retrieve

log = structlog.get_logger()

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "anthropic/claude-sonnet-4-6"

_COST_PER_INPUT_TOKEN = 3.00 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.00 / 1_000_000

_SYSTEM_PROMPT = (
    "You are a precise AI research assistant answering questions from a personal briefing corpus. "
    "Rules:\n"
    "- Cite every factual claim inline as <a href=\"URL\">Source Name</a>.\n"
    "- If the provided context is insufficient, say so — do not hallucinate facts.\n"
    "- Answer in 3–6 sentences unless the question genuinely requires more.\n"
    "- Format output as Telegram HTML: <b>key terms</b>, inline citation links as above.\n"
    "- Do not mention that you are using a corpus or context — answer naturally."
)


def _build_context_block(articles: list[dict]) -> str:
    if not articles:
        return "No relevant articles found in the last 14 days."
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"[{i}] {a['source_name']} — {a['title']}\n"
            f"    URL: {a['url']}\n"
            f"    {a['summary']}"
        )
    return "\n\n".join(lines)


async def respond(query: str) -> str:
    """
    Embed the query, retrieve relevant articles, call Sonnet for a grounded answer.
    Returns Telegram-HTML formatted text with inline citations.
    """
    query_embedding = await embed(query, task_type="search_query")

    db = SessionLocal()
    try:
        articles = retrieve(query_embedding, db)
    finally:
        db.close()

    context_block = _build_context_block(articles)
    user_prompt = f"Context:\n{context_block}\n\nQuestion: {query}"

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
                    "max_tokens": 800,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("responder.http_error", error=str(exc))
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
        task="rag",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=cost,
        source="query",
    )
    log.info("responder.done", context_articles=len(articles), latency_ms=round(latency_ms, 1))
    return answer
