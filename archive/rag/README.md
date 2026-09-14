# Archived — RAG query-back

> Parked, not deleted. See [ADR 015](../../decisions/015-park-rag-query-back.md)
> for why. This directory preserves the feature's full working state at the
> point it was removed from the active app, so it can be restored intact once
> real usage data justifies rebuilding it.

## What's here

| Path | Was |
|---|---|
| `app/rag/retriever.py` | pgvector cosine search, 14-day window, optional tier filter |
| `app/rag/responder.py` | Sonnet via OpenRouter, LangChain LCEL, similarity gate, prompt caching, LangSmith tracing |
| `app/rag/web_searcher.py` | Tavily web search fallback on corpus miss |
| `app/templates/ask.html` | The `/ask` query form template |
| `evals/` | RAGAS 4-metric eval harness, 20 grounded Q&A pairs, Haiku judge |
| `scripts/run_evals.py` | CLI entry point for the eval harness |
| `tests/test_retriever.py` | Integration tests for the retriever |
| `docs/eval-harness.md` | Eval harness usage guide |
| `docs/langsmith-tracing.md` | LangSmith tracing setup guide |

## To restore

1. Move each path back to its original location (mirror the table above, in reverse — e.g. `archive/rag/app/rag` → `app/rag`).
2. Re-add to `pyproject.toml`: `langchain>=0.2`, `langchain-openai>=0.1` (main deps); `ragas>=0.2,<0.3`, `datasets>=2.19` (dev deps) — the exact pins that were in place when this was archived.
3. Re-add to `app/config.py`: `rag_min_similarity`, `tavily_api_key`, `langsmith_api_key`, `langsmith_project`, `langsmith_tracing`, `langsmith_endpoint` (see git history on that file around the archive commit for exact defaults).
4. Re-wire `app/delivery/web.py`: `GET /ask` + `POST /api/ask` routes, importing `respond` from `app.rag.responder`.
5. Re-add the "Ask" nav link in `app/templates/base.html`.
6. Re-add `TAVILY_API_KEY` and the `LANGSMITH_*` block to `.env.example`.
7. Re-run `pip install -e ".[dev]"` and `pytest tests/test_retriever.py -v`.

The code itself was not modified when archived — it should work as-is once
wired back in, modulo whatever else has changed in the surrounding app since.
