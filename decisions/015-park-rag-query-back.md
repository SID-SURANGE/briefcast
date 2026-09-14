# ADR 015 · Park RAG query-back until usage is measured

## Status
Accepted

## Context
RAG query-back (`app/rag/`, retriever + responder + Tavily web fallback)
carried the largest architectural surface area in the app relative to its
actual, unmeasured usage: a RAGAS eval harness, full LangSmith pipeline
tracing, and prompt-cache tuning, none of which serve the feature's function
for a single user — they exist because one of this project's stated goals
(CLAUDE.md) is "build RAG engineering depth," a learning/portfolio goal, not
a user-need goal.

Actual query frequency is unknown. The user stopped opening the Telegram bot
for about a month before ADR 013 — direct evidence of low engagement with
push notifications, and no evidence either way on how often ad-hoc questions
would actually get asked through a web form. Building further on top of an
unmeasured feature (more evals, more tracing) compounds the uncertainty
instead of resolving it.

## Decision
Remove RAG from the active app and archive it intact in `archive/rag/`
rather than delete it — see `archive/rag/README.md` for exact restore steps.
This includes the retriever, responder, web search fallback, the `/ask` web
route and template, the RAGAS eval harness, `test_retriever.py`, and the
LangSmith tracing / eval-harness docs. `app/config.py` drops the
RAG-specific settings (`rag_min_similarity`, `tavily_api_key`,
`langsmith_*`); `pyproject.toml` drops `langchain`, `langchain-openai`,
`ragas`, `datasets`.

The core pipeline (ingest → dedup → rank → compose → web digest) is
unaffected — this is a delivery-surface removal, not a pipeline change.

## Consequences
- Smaller dependency footprint and no unused config surface for a feature
  not currently in use.
- Loses the ability to ask follow-up questions about the corpus until
  restored — a real capability loss, not a cosmetic one, if it turns out
  usage would have been high enough to justify it.
- Restoring is a mechanical copy-back (see `archive/rag/README.md`), not a
  rebuild — the code was archived working, not deleted and re-derived.
- The right trigger to revive: real usage data (once the web digest itself
  has been used for a few weeks) showing follow-up questions are actually
  wanted, at which point the RAG feature can be rebuilt scoped to that
  measured need rather than to portfolio completeness.
