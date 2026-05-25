import os
import time

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from app.config import settings
from app.db import SessionLocal
from app.observability.logger import log_llm_call
from app.processing.embedder import embed
from app.rag.retriever import retrieve
from app.rag.web_searcher import build_web_context, search_web

log = structlog.get_logger(__name__)

# LangChain + LangSmith read tracing config from os.environ.
# pydantic-settings populates Settings but does not write to os.environ,
# so we force-set here at import time. We override (not setdefault) so that
# our config always wins — important on Railway where env vars are already present
# but may point to the wrong endpoint or project.
_tracing_enabled = bool(settings.langsmith_api_key and settings.langsmith_tracing == "true")
os.environ["LANGSMITH_TRACING"] = "true" if _tracing_enabled else "false"
os.environ["LANGCHAIN_TRACING_V2"] = "true" if _tracing_enabled else "false"  # legacy compat
os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint  # legacy compat
log.info("responder.tracing", enabled=_tracing_enabled, project=settings.langsmith_project,
         endpoint=settings.langsmith_endpoint)

_MODEL = "anthropic/claude-sonnet-4-6"
_COST_PER_INPUT_TOKEN = 3.00 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.00 / 1_000_000
_COST_PER_CACHE_READ_TOKEN = 0.30 / 1_000_000   # 90% cheaper than full input
_COST_PER_CACHE_WRITE_TOKEN = 3.75 / 1_000_000  # 25% more expensive, paid once

# Loaded from config (RAG_MIN_SIMILARITY env var, default 0.65).
# Tune via Railway env var without code changes — raise if Tavily fires too often on valid
# corpus queries; lower if genuine on-topic questions are missing the corpus.
_MIN_SIMILARITY: float = settings.rag_min_similarity

_SYSTEM_PROMPT_CORPUS = (
    "You are a precise AI research assistant. "
    "Rules:\n"
    "- Cite every factual claim inline as <a href=\"URL\">Source Name</a>.\n"
    "- NEVER answer from your training knowledge — only from the provided context.\n"
    "- If context is empty, say exactly: "
    "\"I don't have recent data on this topic. Try rephrasing or check back after the next ingestion.\"\n"
    "- Answer in 3–6 sentences unless the question genuinely requires more.\n"
    "- Format output as Telegram HTML: <b>key terms</b>, inline citation links as above.\n"
    "- Do not mention that you are using a corpus or context — answer naturally."
)

_SYSTEM_PROMPT_WEB = (
    "You are a helpful research assistant answering questions from live web search results. "
    "Rules:\n"
    "- Cite every factual claim inline as <a href=\"URL\">Source Name</a>.\n"
    "- Answer only from the provided web search context — do not add training knowledge.\n"
    "- If context is empty, say: \"I couldn't find recent information on that topic.\"\n"
    "- Answer in 3–6 sentences unless the question genuinely requires more.\n"
    "- Format output as Telegram HTML: <b>key terms</b>, inline citation links as above.\n"
    "- Answer any topic — you are not restricted to AI subjects."
)

# System message with cache_control so the static system prompt is cached across queries.
# Anthropic's prompt cache has a 5-min TTL — any query within that window gets a cache hit.
# Only the corpus prompt is cacheable (it's reused across many queries).
# Web search prompt is built fresh per-request (less frequent, not worth caching).
_CACHED_SYSTEM_MESSAGE = SystemMessage(content=[
    {"type": "text", "text": _SYSTEM_PROMPT_CORPUS, "cache_control": {"type": "ephemeral"}}
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


# ---------------------------------------------------------------------------
# Traced wrappers — each becomes a named child span inside the rag_pipeline trace.
# Using thin wrappers keeps the tracing concern out of the underlying modules.
# ---------------------------------------------------------------------------

@traceable(name="embed_query", run_type="embedding")
async def _traced_embed(query: str) -> list[float]:
    return await embed(query, task_type="search_query")


@traceable(name="vector_retrieve", run_type="retriever")
def _traced_retrieve(query_embedding: list[float], db: object) -> list[dict]:
    return retrieve(query_embedding, db)


@traceable(name="tavily_web_search", run_type="tool")
async def _traced_web_search(query: str) -> list[dict]:
    return await search_web(query)


@traceable(name="rag_pipeline", run_type="chain")
async def respond(query: str) -> str:
    """
    Embed query → retrieve from pgvector → generate grounded answer via Claude Sonnet.

    Routing:
      1. Corpus hit (similarity ≥ _MIN_SIMILARITY) → RAG answer with citations.
      2. Corpus miss + TAVILY_API_KEY set → live web search → LLM answer (⚡ marked).
      3. Corpus miss + no Tavily key → canned "no data" message (no LLM, zero cost).

    Prompt caching: static system prompt marked cache_control=ephemeral (5-min TTL).
    LangSmith tracing: full pipeline traced — embed, retrieve, web search, generate.

    Returns Telegram-HTML formatted text with inline citations.
    """
    # Step 1: embed the query (traced as child span via @traceable in embedder)
    query_embedding = await _traced_embed(query)

    # Step 2: retrieve from pgvector (traced as child span)
    db = SessionLocal()
    try:
        articles = _traced_retrieve(query_embedding, db)
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
        )

        # Step 3a: web search fallback (traced as child span)
        web_results = await _traced_web_search(query)
        if web_results:
            context_block = build_web_context(web_results)
            used_web_search = True
        else:
            # No corpus hit, no Tavily key → hard gate, no LLM call
            return (
                "I don't have recent articles on that topic in my 14-day AI corpus, "
                "and web search is not enabled.\n\n"
                "Try rephrasing — e.g. include a company or model name."
            )
    else:
        # Step 3b: format corpus context
        context_block = _build_corpus_context(articles)

    # Step 4: generate — use topic-agnostic prompt for web context to avoid
    # false "off-topic" rejections when Tavily returns non-AI results.
    system_message = (
        SystemMessage(content=_SYSTEM_PROMPT_WEB)
        if used_web_search
        else _CACHED_SYSTEM_MESSAGE
    )
    messages = [
        system_message,
        HumanMessage(content=f"Context:\n{context_block}\n\nQuestion: {query}"),
    ]

    # _llm.ainvoke is auto-traced by LangChain as a child span inside rag_pipeline
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
