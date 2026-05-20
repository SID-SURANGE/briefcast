import os
import time

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.db import SessionLocal
from app.observability.logger import log_llm_call
from app.processing.embedder import embed
from app.rag.retriever import retrieve

log = structlog.get_logger(__name__)

# LangChain reads tracing config from os.environ directly.
# pydantic-settings populates our Settings object but does not write to os.environ,
# so we bridge the two here at import time.
# Only enable tracing when a key is present — prevents 403 noise when unset.
_tracing_enabled = bool(settings.langsmith_api_key and settings.langsmith_tracing == "true")
os.environ.setdefault("LANGSMITH_TRACING", "true" if _tracing_enabled else "false")
os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
log.info("responder.tracing", enabled=_tracing_enabled, project=settings.langsmith_project)

_MODEL = "anthropic/claude-sonnet-4-6"
_COST_PER_INPUT_TOKEN = 3.00 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.00 / 1_000_000
_COST_PER_CACHE_READ_TOKEN = 0.30 / 1_000_000   # 90% cheaper than full input
_COST_PER_CACHE_WRITE_TOKEN = 3.75 / 1_000_000  # 25% more expensive, paid once

_SYSTEM_PROMPT = (
    "You are a precise AI research assistant answering questions from a personal briefing corpus. "
    "Rules:\n"
    "- Cite every factual claim inline as <a href=\"URL\">Source Name</a>.\n"
    "- If the provided context is insufficient, say so — do not hallucinate facts.\n"
    "- Answer in 3–6 sentences unless the question genuinely requires more.\n"
    "- Format output as Telegram HTML: <b>key terms</b>, inline citation links as above.\n"
    "- Do not mention that you are using a corpus or context — answer naturally."
)

# System message with cache_control so the static system prompt is cached across queries.
# Anthropic's prompt cache has a 5-min TTL — any query within that window gets a cache hit.
_CACHED_SYSTEM_MESSAGE = SystemMessage(content=[
    {"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
])

# anthropic-beta header opts this model into prompt caching via OpenRouter.
_llm = ChatOpenAI(
    model=_MODEL,
    openai_api_key=settings.openrouter_api_key,
    openai_api_base="https://openrouter.ai/api/v1",
    max_tokens=800,
    temperature=0.1,
    default_headers={
        "HTTP-Referer": settings.openrouter_app_referer,
        "anthropic-beta": "prompt-caching-2024-07-31",
    },
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
    Embed query → retrieve from pgvector → generate grounded answer via Claude Sonnet.

    Flow: embed query → pgvector cosine search (k=10, 14-day window) → build context
    block → invoke LangChain ChatOpenAI (OpenRouter) with cached system prompt →
    return Telegram-HTML answer with inline citations.

    Prompt caching: the static system prompt is marked with cache_control=ephemeral.
    Anthropic caches it for 5 minutes — repeat queries within that window pay ~10% of
    normal input token cost for the system prompt portion.

    LangSmith tracing: _llm.ainvoke() is automatically traced when LANGSMITH_TRACING=true,
    capturing the full message list (system + context + query), token counts, and latency.

    Returns Telegram-HTML formatted text with inline citations.
    """
    # Embed + retrieve — explicit steps, logged via structlog
    query_embedding = await embed(query, task_type="search_query")

    db = SessionLocal()
    try:
        articles = retrieve(query_embedding, db)
    finally:
        db.close()

    context_block = _build_context_block(articles)

    messages = [
        _CACHED_SYSTEM_MESSAGE,
        HumanMessage(content=f"Context:\n{context_block}\n\nQuestion: {query}"),
    ]

    # _llm.ainvoke is traced in LangSmith automatically when tracing is enabled
    t0 = time.monotonic()
    ai_message = await _llm.ainvoke(messages)
    latency_ms = (time.monotonic() - t0) * 1000

    answer: str = ai_message.content

    # Cost logging — cache reads are 90% cheaper than full input tokens
    usage = getattr(ai_message, "usage_metadata", None)
    input_tokens: int = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens: int = getattr(usage, "output_tokens", 0) if usage else 0
    details = getattr(usage, "input_token_details", None)
    cache_read_tokens: int = getattr(details, "cache_read", 0) if details else 0
    cache_write_tokens: int = getattr(details, "cache_creation", 0) if details else 0
    billed_input = input_tokens - cache_read_tokens - cache_write_tokens
    cost = (
        billed_input * _COST_PER_INPUT_TOKEN
        + cache_read_tokens * _COST_PER_CACHE_READ_TOKEN
        + cache_write_tokens * _COST_PER_CACHE_WRITE_TOKEN
        + output_tokens * _COST_PER_OUTPUT_TOKEN
    )

    log_llm_call(
        model=_MODEL,
        task="rag",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=cost,
        source="query",
    )
    log.info(
        "responder.done",
        context_articles=len(articles),
        latency_ms=round(latency_ms, 1),
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    return answer
