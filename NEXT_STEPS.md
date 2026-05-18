# Briefcast — Implementation Checklist

Current state: skeleton + database foundation + source registry complete.
Work from top to bottom. Each phase builds on the previous one.

---

## Phase 0 — Local environment (do this first, everything else depends on it)

- [ ] Copy `.env.example` to `.env` and fill in `DATABASE_URL` (use docker-compose value: `postgresql+psycopg://briefcast:briefcast@localhost:5432/briefcast`)
- [ ] `docker-compose up -d` — start Postgres with pgvector
- [ ] `pip install -e ".[dev]"` — install dependencies
- [ ] `alembic upgrade head` — apply both migrations, verify tables exist
- [ ] `python scripts/dry_run_ingestion.py` — confirm registry loads cleanly
- [ ] `uvicorn app.main:app --reload` → `GET /healthz` returns `{"status": "ok"}`

---

## Phase 1 — Observability (implement before any real logic — everything logs)

- [ ] `app/observability/logger.py` — implement `configure_logging()` with structlog JSON output; implement `log_llm_call()` with cost calculation
- [ ] Call `configure_logging()` at startup in `app/main.py` and `app/worker.py`
- [ ] Confirm structlog emits JSON to stdout (no `print()` anywhere)

---

## Phase 2 — Ingestion pipeline

### 2a — Verify source feeds (do before writing any fetcher code)
- [ ] Test Google AI Blog feed live: `curl https://blog.google/technology/ai/rss/`
- [ ] Test Google Research Blog: `curl https://research.google/blog/rss/`
- [ ] Test Google DeepMind: `curl https://deepmind.google/blog/rss.xml`
- [ ] Test Google Cloud AI: `curl https://cloudblog.withgoogle.com/rss/` (filter AI/ML)
- [ ] Test Tier 2 feeds — see CLAUDE.md source table for URLs and `[VERIFY]` markers
- [ ] For each confirmed feed: change `classification` from `"verify-before-enabling"` to `"verified-official"` in `app/ingestion/registry.py`
- [ ] Add all confirmed Tier 1 + Tier 2 sources to `SOURCES` in `registry.py`
- [ ] Run `sync_sources(db)` to seed all verified sources into the DB

### 2b — Fetcher (`app/ingestion/fetcher.py`)
- [ ] Implement `fetch_rss(url)` — use `feedparser` + `httpx`; respect `ETag` / `Cache-Control`; log fetch: source, timestamp, item_count, http_status, latency_ms
- [ ] Implement `fetch_arxiv(query, max_results)` — use arXiv export API; parse Atom response; store full abstract (Mode B)
- [ ] Add `fetch_rss` integration test with a real feed URL (not mocked)

### 2c — Circuit breaker (`app/ingestion/circuit_breaker.py`)
- [ ] Implement `record_failure(source_name)` — increment `consecutive_failures`; set state to `"degraded"` at `MAX_FAILURES = 3`; send Telegram alert when tripped
- [ ] Implement `record_success(source_name)` — reset `consecutive_failures` and state to `"closed"`
- [ ] Implement `is_open(source_name)` — returns `True` when state is `"degraded"` (skip fetch)
- [ ] Write `tests/test_circuit_breaker.py`

### 2d — Deduplication (`app/ingestion/dedup.py`)
- [ ] Implement `l1_hash(url)` — SHA-256 hex of URL; check `dedup_hash` index in DB before any API call
- [ ] Implement `l2_cosine(embedding_a, embedding_b)` — cosine similarity; compare against `settings.dedup_threshold`
- [ ] Implement `is_duplicate(url, title_embedding)` — L1 first, then L2 only if L1 misses
- [ ] Write `tests/test_dedup.py` (stubs already exist)

---

## Phase 3 — Processing

### 3a — Embedder (`app/processing/embedder.py`)
- [ ] Get Nomic API key → add `NOMIC_API_KEY` to `.env`
- [ ] Implement `embed(text)` and `embed_batch(texts)` using `nomic-embed-text-v1.5` via Nomic API
- [ ] Log every API call via `log_llm_call()`

### 3b — Summariser (`app/processing/summariser.py`)
- [ ] Get OpenRouter API key → add `OPENROUTER_API_KEY` to `.env`
- [ ] Implement `summarise(text, source_name)` — Gemini Flash via OpenRouter; 3–5 sentence output; respect `storage_mode` (skip for Mode B — arXiv stores abstract directly)
- [ ] Log every call with token counts + estimated cost
- [ ] **Hard rule:** never call this with Sonnet — wrong cost tier

---

## Phase 4 — Ranking

- [ ] Implement `score(article)` in `app/ranking/ranker.py` — formula: `(tier_weight × 0.35) + (recency × 0.35) + (novelty × 0.30)` where novelty = 1 − max cosine similarity to already-selected items
- [ ] Implement `rank(articles)` — returns sorted list descending by score
- [ ] Write `tests/test_ranker.py` (stubs already exist — fill in the three test cases)

---

## Phase 5 — Briefing + Delivery

- [ ] Create Telegram bot via BotFather → add `TELEGRAM_BOT_TOKEN` to `.env`; find your personal chat ID
- [ ] Implement `app/delivery/telegram_bot.py` — `send_briefing()`, `send_alert()`, `handle_query()`
- [ ] Implement `app/briefing/composer.py` — Claude Haiku via OpenRouter; citations mandatory in prompt; select top 6–8 ranked items; Tier 1 always represented
- [ ] Wire `app/worker.py` — APScheduler jobs: ingestion every 6h (06:00 UTC), briefing daily (08:00 UTC)
- [ ] End-to-end smoke test: run worker manually, confirm Telegram message arrives

---

## Phase 6 — RAG query-back

- [ ] Implement `app/rag/retriever.py` — `retrieve(query_embedding, k=10)`; metadata filter: `published_at >= now() - 14 days`; pgvector cosine search
- [ ] Implement `app/rag/responder.py` — Claude Sonnet via OpenRouter; grounded answer + inline citations; wrap with LangChain LCEL for LangSmith tracing
- [ ] Wire Telegram `handle_query()` → embed query → retrieve → respond → reply
- [ ] Write `tests/test_retriever.py` (stubs already exist)
- [ ] Add `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_PROJECT` to `.env`

---

## Phase 7 — Tests + deployment

- [ ] Fill in all test stubs in `tests/` — minimum: dedup, ranker, retriever
- [ ] `pytest tests/ -v` passes clean
- [ ] `ruff check app/ && black --check app/ && isort --check app/` passes clean
- [ ] Push Docker image to Railway — set all env vars in Railway dashboard
- [ ] Confirm `/healthz` responds on Railway URL
- [ ] Confirm first scheduled briefing arrives in Telegram

---

## Phase 8 — ADRs (do alongside the work, not after)

Each ADR file in `decisions/` is a stub. Fill them in as you implement the related feature:

- [ ] `001` — when you confirm pgvector works in production
- [ ] `002` — after first real LLM calls confirm cost/quality assumptions
- [ ] `003` — after RSS fetcher is live
- [ ] `004` — after first briefing with citations lands in Telegram
- [ ] `005` — after Tier 1 ranking boost is measurable
- [ ] `006` — after storage modes are enforced in summariser
- [ ] `007` — after first OpenRouter billing statement
- [ ] `008` — after first Telegram briefing
- [ ] `009` — after Nomic API is live and token usage is visible

---

## Milestone summary

| Milestone | Phases complete | What you can do |
|---|---|---|
| DB foundation | 0 | Apply migrations, see tables in Postgres |
| First real fetch | 0 + 2a + 2b | Pull articles from RSS into DB |
| Full ingestion | 0–2d | Fetch, dedup, circuit-break, persist |
| First summary | 3 | Articles have summaries and embeddings |
| First briefing | 4 + 5 | Daily Telegram message with ranked, cited items |
| Query-back | 6 | Reply to Telegram with grounded RAG answers |
| Production | 7 | Running on Railway, monitored, tested |
