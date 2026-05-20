import os
import time

import structlog
from langchain_core.prompts import ChatPromptTemplate
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

_SYSTEM_PROMPT = (
    "You are a precise AI research assistant answering questions from a personal briefing corpus. "
    "Rules:\n"
    "- Cite every factual claim inline as <a href=\"URL\">Source Name</a>.\n"
    "- If the provided context is insufficient, say so — do not hallucinate facts.\n"
    "- Answer in 3–6 sentences unless the question genuinely requires more.\n"
    "- Format output as Telegram HTML: <b>key terms</b>, inline citation links as above.\n"
    "- Do not mention that you are using a corpus or context — answer naturally."
)

# LCEL chain: prompt → Sonnet via OpenRouter.
# When LANGCHAIN_TRACING_V2=true this chain is automatically traced in LangSmith,
# capturing the full prompt (with retrieved context), token usage, and latency.
_llm = ChatOpenAI(
    model=_MODEL,
    openai_api_key=settings.openrouter_api_key,
    openai_api_base="https://openrouter.ai/api/v1",
    max_tokens=800,
    temperature=0.1,
    default_headers={"HTTP-Referer": settings.openrouter_app_referer},
)

_prompt = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    ("human", "Context:\n{context}\n\nQuestion: {query}"),
])

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
    Embed query → retrieve from pgvector → generate grounded answer via LCEL chain.

    The prompt | llm chain is traced end-to-end in LangSmith (full prompt with
    retrieved context, token counts, latency). Embedding and retrieval steps are
    logged via structlog.

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

    # LCEL chain — traced in LangSmith automatically
    t0 = time.monotonic()
    ai_message = await (_prompt | _llm).ainvoke({
        "context": context_block,
        "query": query,
    })
    latency_ms = (time.monotonic() - t0) * 1000

    answer: str = ai_message.content

    # Cost logging via structlog — feeds cost_report.py
    usage = getattr(ai_message, "usage_metadata", None) or {}
    input_tokens: int = usage.get("input_tokens", 0)
    output_tokens: int = usage.get("output_tokens", 0)
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
