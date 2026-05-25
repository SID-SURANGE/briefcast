# LangSmith Tracing

> End-to-end observability for the Briefcast RAG pipeline.  
> Every query traced: embed → retrieve → generate — with full context and token visibility.

---

## What is traced

Only the **RAG query path** is traced. Batch jobs (summariser, briefing composer) use raw `httpx` — no tracing overhead where per-call visibility is not needed.

```
User message (Telegram)
        ↓
  rag_pipeline  ←── root span (run_type: chain)
  ├── embed_query         ←── child span (run_type: embedding)
  ├── vector_retrieve     ←── child span (run_type: retriever)
  ├── tavily_web_search   ←── child span (run_type: tool)  [only on corpus miss]
  └── ChatOpenAI.ainvoke  ←── child span (auto-traced by LangChain)
```

Each span captures: inputs, outputs, latency, token counts. The `ChatOpenAI` span shows the full prompt sent to Claude Sonnet — including all retrieved context articles.

---

## Implementation

### `@traceable` on the pipeline function

```python
# app/rag/responder.py

from langsmith import traceable

@traceable(name="rag_pipeline", run_type="chain")
async def respond(query: str) -> str:
    query_embedding = await _traced_embed(query)      # → embed_query span
    articles = _traced_retrieve(query_embedding, db)  # → vector_retrieve span
    ...
    ai_message = await _llm.ainvoke(messages)          # → ChatOpenAI span (auto)
```

### Thin `@traceable` wrappers for sub-steps

```python
@traceable(name="embed_query", run_type="embedding")
async def _traced_embed(query: str) -> list[float]:
    return await embed(query, task_type="search_query")

@traceable(name="vector_retrieve", run_type="retriever")
def _traced_retrieve(query_embedding: list[float], db: object) -> list[dict]:
    return retrieve(query_embedding, db)

@traceable(name="tavily_web_search", run_type="tool")
async def _traced_web_search(query: str) -> list[dict]:
    return await search_web(query)
```

**Why thin wrappers?** The tracing concern stays in `responder.py` — `embedder.py`, `retriever.py`, and `web_searcher.py` remain clean and independently testable. The wrappers add no logic, only observability.

### Environment bridging

LangSmith reads from `os.environ`. `pydantic-settings` populates `Settings` but does not write to `os.environ`. `responder.py` bridges this at import time:

```python
_tracing_enabled = bool(settings.langsmith_api_key and settings.langsmith_tracing == "true")
os.environ["LANGSMITH_TRACING"] = "true" if _tracing_enabled else "false"
os.environ["LANGCHAIN_TRACING_V2"] = "true" if _tracing_enabled else "false"  # legacy compat
os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
```

Tracing is silently disabled if `LANGSMITH_API_KEY` is empty — no 403 noise in dev.

---

## Setup

### 1. Create a LangSmith account

Free developer tier: [smith.langchain.com](https://smith.langchain.com)  
Free tier: **5,000 traces/month** — sufficient for personal use.

### 2. Get an API key

LangSmith dashboard → Settings → API Keys → Create.

### 3. Set environment variables

**Local (`.env`):**
```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=briefcast-dev
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com
```

**Railway (both API and Worker services):**

| Variable | Value |
|---|---|
| `LANGSMITH_TRACING` | `true` |
| `LANGSMITH_API_KEY` | your key |
| `LANGSMITH_PROJECT` | `briefcast-dev` |
| `LANGSMITH_ENDPOINT` | `https://apac.api.smith.langchain.com` (APAC) or `https://api.smith.langchain.com` (US) |

> Use the APAC endpoint (`apac.api.smith.langchain.com`) if you are in Asia-Pacific — lower latency and same free tier.

### 4. Verify

Check Railway API logs for:
```
responder.tracing  enabled=True  project=briefcast-dev  endpoint=https://apac.api.smith.langchain.com
```

If `enabled=False`, `LANGSMITH_API_KEY` is missing or `LANGSMITH_TRACING` is not `"true"`.

---

## Reading a trace

Open [smith.langchain.com](https://smith.langchain.com) → your project → a `rag_pipeline` run.

| Span | What to look for |
|---|---|
| `rag_pipeline` | Total latency; routing path (corpus vs web) |
| `embed_query` | Embedding latency; confirms Nomic API is responding |
| `vector_retrieve` | Retrieved articles and their similarity scores |
| `tavily_web_search` | Present only on corpus miss; shows Tavily results |
| `ChatOpenAI` | **Full prompt sent to Sonnet** — including all context articles; token counts; cache hit/miss |

The `ChatOpenAI` span is the most valuable: you can see exactly what context the model saw, verify citations are grounded, and check whether the system prompt is being cached (look for `cache_read_tokens > 0`).

---

## Prompt caching and tracing

The corpus system prompt is marked `cache_control: ephemeral` — Anthropic caches it for 5 minutes. Cache behaviour is visible in the `ChatOpenAI` span token breakdown:

```
input_tokens         = total tokens consumed
cache_read_tokens    = tokens served from cache (cost: $0.30/M instead of $3.00/M)
cache_write_tokens   = tokens written to cache this window (cost: $3.75/M, paid once)
```

A healthy trace shows `cache_read_tokens > 0` for any query after the first in a 5-minute window. If `cache_read_tokens` is always 0, check that `anthropic-beta: prompt-caching-2024-07-31` is set in the `ChatOpenAI` headers and that `OPENROUTER_API_KEY` supports Anthropic models.

These values are also logged to structlog on every `responder.done` event and aggregated by `scripts/cost_report.py`.

---

## Best practices demonstrated

| Practice | Where |
|---|---|
| Trace only the interactive path, not batch jobs | `responder.py` only — summariser and composer use raw `httpx` |
| Keep tracing concerns in one file | All `@traceable` wrappers in `responder.py`; underlying modules stay clean |
| Fail silently when key is absent | `_tracing_enabled` guard; no 403 noise in local dev |
| Bridge pydantic-settings → os.environ at import time | Force-set at module top; overrides Railway env vars with our validated config |
| Use `run_type` semantics | `chain`, `embedding`, `retriever`, `tool` — makes LangSmith UI grouping meaningful |
| Log cache token breakdown | `cache_read_tokens` and `cache_write_tokens` on every `responder.done` — cost visibility without a separate dashboard |

---

## Files

```
app/rag/
└── responder.py     # @traceable wrappers + rag_pipeline root span + env bridging

app/config.py        # langsmith_api_key, langsmith_project, langsmith_endpoint,
                     # langsmith_tracing — all pydantic-settings fields
```
