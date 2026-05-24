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
from app.rag.web_searcher import build_web_context, search_web

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

# Minimum cosine similarity to treat a retrieved article as relevant.
# Below this, results are semantically unrelated — treat as corpus miss.
_MIN_SIMILARITY = 0.35

_SYSTEM_PROMPT = (
    "You are a precise AI research assistant. "
    "Rules:\n"
    "- Cite every factual claim inline as <a href=\"URL\">Source Name</a>.\n"
    "- NEVER answer from your training knowledge — only from the provided context.\n"
    "- If context is empty or off-topic, say exactly: "
    "\"I don't have recent data on this topic. Try rephrasing or check back after the next ingestion.\"\n"
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


def _build_corpus_context(articles: list[dict]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"[{i}] {a['source_name']} — {a['title']}\n"
            f"    URL: {a['url']}\n"
            f"    {a['summary']}"
        )
    return "\n\n".join(lines)


def _has_relevant_results(articles: list[dict]) -> bool:
    """True if at least one retrieved article clears the similarity threshold."""
    return bool(articles) and articles[0]["similarity"] >= _MIN_SIMILARITY


async def respond(query: str, corpus_only: bool = False) -> str:
    """
    Embed query → retrieve from pgvector → generate grounded answer via Claude Sonnet.

    Routing:
      1. Corpus hit (similarity ≥ _MIN_SIMILARITY) → RAG answer with citations.
      2. Corpus miss + corpus_only=False + TAVILY_API_KEY set → web search fallback.
      3. Corpus miss + corpus_only=True → canned "not in corpus" message (no LLM, zero cost).
      4. Corpus miss + no Tavily key → canned "no data" message (no LLM, zero cost).

    corpus_only=True is used by the /ask command so users can explicitly restrict to
    the ingested corpus without a web fallback.

    Prompt caching: static system prompt marked cache_control=ephemeral (5-min TTL).
    LangSmith tracing: automatic when LANGSMITH_TRACING=true.

    Returns Telegram-HTML formatted text with inline citations.
    """
    # Embed + retrieve — explicit steps, logged via structlog
    query_embedding = await embed(query, task_type="search_query")

    db = SessionLocal()
    try:
        articles = retrieve(query_embedding, db)
    finally:
        db.close()

    used_web_search = False  # track routing path for logging

    # --- Gate: corpus miss check ---
    if not _has_relevant_results(articles):
        best_sim = articles[0]["similarity"] if articles else 0.0
        log.info(
            "responder.corpus_miss",
            best_similarity=best_sim,
            articles_returned=len(articles),
            corpus_only=corpus_only,
        )

        if corpus_only:
            return (
                "I don't have recent articles on that topic in my 14-day AI corpus.\n\n"
                "Try asking without <b>/ask</b> (plain message) to enable live web search, "
                "or rephrase — e.g. include a company or model name."
            )

        # Try web search fallback
        web_results = await search_web(query)
        if web_results:
            context_block = build_web_context(web_results)
            used_web_search = True
        else:
            # No corpus, no Tavily key → hard gate, no LLM call
            return (
                "I don't have recent articles on that topic in my 14-day AI corpus.\n\n"
                "Try <b>/chat</b> for a general answer, or ask again after tomorrow's ingestion. "
                "You can also rephrase — e.g. include a company or model name."
            )
    else:
        context_block = _build_corpus_context(articles)

    messages = [
        _CACHED_SYSTEM_MESSAGE,
        HumanMessage(content=f"Context:\n{context_block}\n\nQuestion: {query}"),
    ]

    # _llm.ainvoke is traced in LangSmith automatically when tracing is enabled
    t0 = time.monotonic()
    ai_message = await _llm.ainvoke(messages)
    latency_ms = (time.monotonic() - t0) * 1000

    web_disclaimer = (
        "\n\n<i>⚡ Answered from live web search — not in my 14-day corpus.</i>"
        if used_web_search else ""
    )
    answer: str = ai_message.content + web_disclaimer

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
        source="web_search" if used_web_search else "corpus",
        latency_ms=round(latency_ms, 1),
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    return answer
