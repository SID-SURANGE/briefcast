# 📋 Changelog

> All notable changes to Briefcast are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versions map to the project's v1 → v1.5 → v2 milestone structure.

---

## [v1.5] — 2026-05-25

### Added
- **RAGAS eval harness** (`evals/`) — 4-metric evaluation (faithfulness, answer_relevancy, context_precision, context_recall) over 20 grounded Q&A pairs; Haiku as judge LLM; reports saved to `evals/reports/` (gitignored). Run via `python scripts/run_evals.py`.
- **Tavily web search fallback** (`app/rag/web_searcher.py`) — when query similarity falls below the corpus gate (0.35), the responder falls back to Tavily web search and answers from live results. Fail-safe if `TAVILY_API_KEY` is unset.
- **LLM-based relevance classifier** (`app/ingestion/classifier.py`) — Gemini Flash YES/NO filter applied during ingestion; narrows corpus to model releases, research, system design, and observability tools.
- **Full LangSmith pipeline tracing** (`app/rag/responder.py`) — `@traceable` decorator on the full RAG pipeline; embed, retrieve, and generate spans visible end-to-end in LangSmith without requiring full LangChain LCEL. See ADR 012.
- **Single-path query UX** — removed `/ask` and `/chat` commands; any plain message goes through corpus-first → web-fallback pipeline. `/help` is the only command. See ADR 011.
- **Prompt caching on RAG system prompt** — static system prompt marked `cache_control: ephemeral`; cache reads cost 90% less than full input; `cache_read_tokens` and `cache_write_tokens` logged on every `responder.done` event. See ADR 010.
- **Forum Topics support** — `send_briefing()` and `send_alert()` accept optional `message_thread_id`; no-op when unset (works in flat personal chat by default).
- ADR 010: prompt caching on RAG system prompt  
- ADR 011: single-path query UX  
- ADR 012: full LangSmith pipeline tracing  
- `evals/questions.json` ground truths updated for May 2026 model landscape (GPT-5.5, Gemini 3.5 Flash/Omni, Llama 4 Scout/Maverick, Blackwell B200)

### Changed
- `app/rag/responder.py` — dual system prompts (corpus vs web); similarity gate (0.35) gates corpus path; web fallback marked with ⚡ in Telegram reply
- `design-faq.md` — updated LangChain usage answer (no LCEL pipe in responder); added corpus miss routing explanation

---

## [v1.0] — 2026-05-19

### Added
- **End-to-end pipeline** — ingestion → dedup → summarise → rank → brief → RAG query-back, fully deployed on Railway
- **Source registry** — 8 sources: 4 Tier 1 Google (AI Blog, Research Blog, Cloud AI Blog, DeepMind Blog) + 4 Tier 2 (OpenAI, Meta AI, Hugging Face, Microsoft AI) + arXiv cs.AI/cs.LG
- **2-layer deduplication** — L1 SHA-256 URL hash (O(1)) + L2 cosine similarity via pgvector (`DEDUP_THRESHOLD=0.92`)
- **Ingestion job** — APScheduler cron every 6h; feedparser + httpx for RSS/Atom; arXiv Atom API
- **Summariser** — Gemini 2.5 Flash via OpenRouter; 3–5 sentence summary per article (Mode A); arXiv abstracts stored directly (Mode B)
- **Embedder** — Nomic API `nomic-embed-text-v1.5`; `embed()` + `embed_batch()`; zero RAM overhead on Railway Hobby
- **Ranker** — `score = tier(0.35) + recency(0.35) + novelty(0.30)`; Tier 1 always represented in briefing
- **Briefing composer** — Claude Haiku via OpenRouter; top 6–8 items; citations mandatory; HTML formatted for Telegram
- **RAG retriever** — pgvector cosine distance; 14-day rolling window; optional tier filter; returns similarity score
- **RAG responder** — Claude Sonnet via OpenRouter; grounded answer with inline citations; structured cost logging
- **Telegram delivery** — `send_briefing()` + `send_alert()`; webhook mode via FastAPI; daily at 09:00 IST
- **Circuit breaker** — 3 consecutive feed failures → source marked `degraded` → Telegram alert
- **Observability** — structlog JSON on every LLM call (model, task, tokens, latency, cost); `scripts/cost_report.py` for weekly aggregation; LangSmith tracing for RAG path
- **Database** — PostgreSQL + pgvector via Railway; SQLAlchemy 2.x; Alembic migrations from day 1; soft-delete on all content tables
- **32 tests** — `test_dedup.py`, `test_ranker.py`, `test_retriever.py`; all passing
- ADRs 001–009 documenting every key architectural decision

### Architecture
- Railway deployment: API service (FastAPI webhook) + Worker service (APScheduler cron) + Railway Postgres
- OpenRouter as unified LLM gateway — single API key, model swaps with one parameter change
- No scraping, no paywalls, no full article body stored — RSS/Atom feeds and official APIs only

---

## Upcoming [v1.5 — remaining]

- [ ] Tier 3 sources — DeepSeek, Qwen, Kimi, Mistral
- [ ] Tier 4 newsletters — Import AI, Ahead of AI, The Gradient
- [ ] Hybrid BM25 + vector search — measure vector baseline first

## Planned [v2]

- [ ] GCP migration — Cloud Run + Cloud SQL, same Docker images, no code changes
- [ ] Local embedding model — switch from Nomic API when self-hosting or memory allows
- [ ] X/Twitter connector — requires `TWITTER_BEARER_TOKEN`; store summary + URL only
