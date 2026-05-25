# ADR 012: Full RAG pipeline tracing via LangSmith @traceable

## Status
Accepted — 2026-05-25

## Context
After adding LangSmith tracing in ADR 010, only the final LLM generation step
(`_llm.ainvoke()`) appeared in LangSmith traces. The three upstream steps —
query embedding, vector retrieval, and Tavily web search — were invisible.

This meant:
- No visibility into retrieval latency or how many articles were returned
- No way to see what similarity scores looked like for a given query
- No trace of whether Tavily fired or not, and what it returned
- Failures in embedding or retrieval appeared as silent errors in structlog only

Additionally, traces from Railway were not appearing in LangSmith UI despite the
API key being set. Root cause: `os.environ.setdefault()` is a no-op when the env
var is already present (Railway injects all env vars at startup). The tracing env
vars were being set in pydantic-settings but not propagated to `os.environ` on
Railway. LangChain reads from `os.environ` directly, not from Settings objects.

## Decision

### 1. Force-set all LangSmith env vars at import time

Replace `os.environ.setdefault(...)` with `os.environ[...] = ...` so our
pydantic-settings values always win, including on Railway where env vars are
already present in `os.environ`.

Add legacy variable names for older LangChain versions:
- `LANGCHAIN_TRACING_V2` mirrors `LANGSMITH_TRACING`
- `LANGCHAIN_ENDPOINT` mirrors `LANGSMITH_ENDPOINT`

Log the active endpoint in the startup `responder.tracing` log line so Railway
misconfiguration is immediately visible in logs.

### 2. Add @traceable wrappers for each pipeline step

Use `langsmith.traceable` (already a transitive dependency via `langchain`) to
wrap each step as a named child span inside the parent `rag_pipeline` trace:

```
rag_pipeline              (chain)     @traceable on respond()
├── embed_query           (embedding) @traceable on _traced_embed()
├── vector_retrieve       (retriever) @traceable on _traced_retrieve()
├── tavily_web_search     (tool)      @traceable on _traced_web_search() — only on corpus miss
└── ChatOpenAI.invoke     (llm)       auto-traced by LangChain
```

Wrappers are thin functions in `responder.py` — the tracing concern does not
leak into `embedder.py`, `retriever.py`, or `web_searcher.py`. Those modules
remain unaware of LangSmith.

### 3. Failure propagation

Exceptions raised in any child span propagate naturally to the parent
`rag_pipeline` span and are recorded as errors in LangSmith. No explicit
error-capture code is needed.

## Consequences
- Every query is now a full-fidelity trace: query in → each step's input/output
  → answer out, with latency at each node.
- Corpus miss rate, similarity score distributions, and Tavily hit/miss rate are
  all visible in LangSmith without adding extra logging.
- `langsmith` does not need to be added to `pyproject.toml` — it is already a
  transitive dependency of `langchain>=0.2`. Pin it explicitly if the indirect
  dependency ever becomes unstable.
- The `run_type` labels (`embedding`, `retriever`, `tool`, `chain`) enable
  LangSmith's built-in per-type grouping and cost attribution.
- Cache token logging in `responder.done` structlog is unchanged — cost tracking
  works independently of LangSmith tracing.

## Verification checklist (run after Railway deploy)
1. Check Railway API logs for: `responder.tracing enabled=True endpoint=https://apac.api.smith.langchain.com`
2. Send a plain message to the bot
3. Open LangSmith → project `briefcast-dev` → confirm `rag_pipeline` run appears
4. Expand the run tree — confirm `embed_query`, `vector_retrieve`, and
   `ChatOpenAI` appear as child spans
5. Ask an out-of-corpus question — confirm `tavily_web_search` appears as a
   child span on that run only
