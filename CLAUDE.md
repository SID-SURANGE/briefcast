# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# Briefcast — personal AI intelligence briefing agent + RAG query-back
**CLAUDE.md · v1.4 · 2026-05-25**

Read this fully at the start of every Claude Code session before writing any code.
Lines marked `[VERIFY]` must be tested live before the connector is enabled.
This repo is open-source. Every decision must be safe for public GitHub.

---

## Project Identity

| Field | Value |
|---|---|
| What it is | Personal Google AI intelligence briefing pipeline (RAG query-back parked — ADR 015) |
| Who uses it | Solo developer · single user · personal tool |
| Why it exists | Stay current on Google AI · strengthen Google profile (ADR 005, ADR 016) |
| Delivery channel | Web UI (FastAPI + Jinja2) — see delivery section. Telegram removed, see ADR 013. |
| Open source | Yes. No scraping. No full-text storage. No credentials in code. Ever. |

**One-line description:** A self-hosted pipeline that ingests Google's own AI blogs via RSS,
deduplicates and ranks them, and composes a daily briefing rendered on a web page with a
browsable archive. RAG query-back over the corpus exists but is archived/parked, not active.

---

## Current State & Next Steps

> **Keep this section current.** Update it at the end of every session or after every feature lands.
> Claude reads this first — an accurate status here avoids redundant codebase exploration.

### What is built and working (as of 2026-09-14)

| Layer | File(s) | Status |
|---|---|---|
| Config | `app/config.py` | ✅ pydantic-settings; RAG-only settings removed (ADR 015) |
| DB session | `app/db.py` | ✅ SQLAlchemy engine; `pool_recycle=280` for Neon's connection behavior |
| Models | `app/models/article.py`, `source.py`, `briefing.py`, `base.py` | ✅ full schema with pgvector, soft-delete; `Briefing` persists composed digests |
| Migrations | `alembic/versions/0001_*`–`0003_*` | ✅ pgvector extension, articles/sources, briefings table |
| API server | `app/main.py` | ✅ FastAPI + `/healthz`; mounts `app/delivery/web.py` router; no webhook (Telegram removed, ADR 013) |
| Web delivery | `app/delivery/web.py`, `app/templates/` | ✅ `GET /` digest + source health, `GET /archive` + `GET /archive/{id}` browsable history, `app/delivery/sanitize.py` (bleach) sanitizes LLM HTML before `\| safe` render |
| Observability | `app/observability/logger.py` | ✅ `configure_logging()` JSON structlog; `log_llm_call()`. LangSmith removed with RAG (ADR 015) |
| RSS fetcher | `app/ingestion/fetcher.py` | ✅ `fetch_rss()` feedparser+httpx (`fetch_arxiv()` still present but unused — no arXiv source active) |
| Deduplication | `app/ingestion/dedup.py` | ✅ L1 SHA-256 hash; L2 cosine (numpy) |
| Embedder | `app/processing/embedder.py` | ✅ Nomic API |
| Circuit breaker | `app/ingestion/circuit_breaker.py` | ✅ 3-strike → `degraded`; surfaced on web dashboard source-health panel (no more Telegram alert) |
| Summariser | `app/processing/summariser.py` | ✅ Gemini Flash via OpenRouter |
| Ranker | `app/ranking/ranker.py` | ✅ tier/recency/novelty weights; tier term is now a constant (every remaining source is tier 1 — see ADR 016) |
| Worker | `app/worker.py` | ✅ APScheduler locally; `run_ingestion()` every 6h, `run_briefing()` 03:30 UTC — persists to `Briefing` table, no Telegram send |
| Composer | `app/briefing/composer.py` | ✅ Haiku via OpenRouter; top 8, capped 3 per source blog (ADR 016 — was per-company, now per-blog since registry is Google-only) |
| Source registry | `app/ingestion/registry.py` | ✅ **4 sources, Google-family only** (ADR 016) — Google AI Blog, Google Research Blog, Google Cloud AI Blog, Google DeepMind Blog. `sync_sources()` soft-deletes any DB row no longer in the registry |
| Tests | `tests/test_dedup.py`, `test_ranker.py` | ✅ passing (`test_retriever.py` archived with RAG) |
| Deployment | Cloud Run + Cloud Scheduler + Neon | Target platform per ADR 014 — see `docs/gcp-deployment.md`. Live-deployment status not yet confirmed in this file; check Railway/Cloud Run dashboards directly rather than trusting a stale note here |

**Parked/archived, not deleted:**
- RAG query-back (retriever, responder, Tavily fallback, `/ask`, RAGAS eval harness, LangSmith tracing) — `archive/rag/`, restore guide in `archive/rag/README.md`, decision in ADR 015
- Telegram delivery — fully removed (not archived), ADR 013. Code is in git history (pre-`feature/web-delivery-gcp-migration` branch) if ever needed for reference
- Non-Google sources (OpenAI, Hugging Face, Meta, arXiv, Microsoft, NVIDIA) — removed from the registry, not archived as code (they were just RSS URLs + tier/classification metadata, trivial to re-add to `SOURCES` if ADR 016 is ever reversed)

### What remains
- Confirm live GCP deployment status (Cloud Run service + 2 Jobs + 2 Scheduler triggers + Neon) — `docs/gcp-deployment.md` has the walkthrough; this file does not track live deployment state, don't assume it's done from anything written here
- Candidate next feature (not started): flashcards generated from digest summaries — see conversation/README roadmap, no ADR yet

### Recent architectural decisions (read the ADRs, don't assume from summaries)
ADR 013 (web UI over Telegram) → ADR 014 (Cloud Run + Neon over Railway) → ADR 015 (park RAG) → ADR 016 (Google-only sources) — these four landed across two sessions and materially changed almost every section below this point in the file. Sections further down (Delivery, Deployment, Models, Observability, File Structure) may still describe the pre-ADR-013 state in places — treat this "Current State" section and the ADRs as the source of truth over older prose elsewhere in this file until a full pass reconciles it.

---

## Development Environment

| Item | Detail |
|---|---|
| Editor | VS Code with the Claude Code extension |
| Auth | Claude Pro subscription ($20/mo) — no separate API key needed for Claude Code |
| Session start | Always open VS Code from the project root — Claude Code reads CLAUDE.md automatically |
| Do NOT use | Cursor free tier — different harness, lower fidelity on multi-file tasks, wrong for cert prep |

**Claude Code discipline:**
- Run from project root every session — CLAUDE.md is your agent context file
- Use Plan mode (`/plan`) before any task touching more than 2 files
- Review every generated code block before running it — do not trust blindly
- Write ADRs with Claude Code assistance, then correct manually — the reasoning habit is the goal
- Use `/clear` between unrelated tasks to reset context; long mixed sessions degrade output quality

**When compacting context:** always preserve the list of modified files, the current "What is built" status table, any Railway env var names, and active test commands.

---

## Source Universe — Google-Only (ADR 016)

**As of ADR 016 (2026-09-14), Briefcast ingests Google sources exclusively.** This is a
deliberate narrowing from the earlier "Google-first, but 8 sources total" design — read
[ADR 016](decisions/016-google-only-sources.md) before adding any non-Google source back;
doing so reverses a documented decision, not a gap to casually fill.

All sources use Mode A (summary + metadata). No Mode B (abstract) source is currently active
— arXiv was removed in ADR 016; the Mode B code path still exists in `app/models/source.py`'s
`storage_mode` field for if it's ever needed again.

New source checklist: (a) URL tested live · (b) ToS reviewed · (c) classification tag assigned ·
(d) storage mode set · (e) **confirms with the user first** — the registry being Google-only is
a decision, not a default.

### Active Sources

| Tier | Source | Feed / Endpoint | Status |
|---|---|---|---|
| 1 | Google AI Blog | `https://blog.google/technology/ai/rss/` | verified live |
| 1 | Google Research Blog | `https://research.google/blog/rss/` | verified live |
| 1 | Google Cloud AI Blog | `https://cloudblog.withgoogle.com/rss/` | verified live |
| 1 | Google DeepMind Blog | `https://deepmind.google/blog/rss.xml` | verified live |

### Removed (ADR 016) — not planned, not disabled, removed

OpenAI, Hugging Face, Meta AI, arXiv cs.AI+cs.LG, Microsoft AI, NVIDIA. Their feed URLs and
verification notes from the pre-016 registry are preserved in git history
(`app/ingestion/registry.py` before this change) if ever needed to re-add one.

**Hard exclusions:** HTML scraping · paywalled sources · region-restricted endpoints · sources prohibiting automated access.

---

## Storage Policy

### Three storage modes

**Mode A — Summary + metadata** (default for all blog/news sources)
Store: URL, title, author, source name, source tier, `published_at`, Claude-generated summary (3–5 sentences),
embedding of our summary, relevance score, dedup hash, `storage_mode`, `deleted_at`.
Do NOT store: original article body, excerpts beyond a headline or subheading, images.

**Mode B — Abstract + metadata** (Arxiv only)
Store: everything in Mode A, PLUS the full abstract text.
Rationale: arXiv provides open programmatic access; abstracts are designed for discovery indexing.
Full PDF body is NOT stored — use fetch-summarise-discard if deeper processing is ever needed.

**Mode C — Fetch → process → discard** (permissive-licence PDFs only)
Permitted only when source carries CC-BY, Apache 2.0, MIT, or explicit redistribution grant.
Pattern: fetch PDF → extract text in memory → generate summary → store summary + metadata → discard raw text.
Never write raw extracted text to the database. Intermediate text lives in memory only.

Source-level storage mode overrides must be documented in `docs/POLICY.md` and set in `app/models/source.py`.

### Hard rules — no exceptions
- Never store full article body text
- Never store body excerpts beyond headline or subheading level
- Never store content from paywalled sources
- Never write Mode C raw text to the database
- X/Twitter: store URL, author handle, our generated summary only — never raw post text
- All content tables must include a `deleted_at` soft-delete column
- Summaries we generate are our own output — store them freely

---

## Ingestion Policy

### Allowed methods (priority order)
1. Official RSS/Atom feeds
2. Official REST APIs (arXiv export, GitHub Releases, HuggingFace API)
3. Public Substack RSS — platform-supported, always allowed
4. PDF fetch-process-discard under Mode C for permissive-licence sources only

### Prohibited (hard constraints)
- HTML scraping of any page, regardless of robots.txt
- Bypassing paywalls or login gates
- Polling faster than 1-hour minimum per source
- Storing raw content fetched under Mode C
- Enabling any source without: (a) URL tested live, (b) ToS reviewed, (c) storage mode assigned

### Required per source
- Respect `ETag` and `Cache-Control` — do not re-fetch unchanged feeds
- Circuit breaker: 3 consecutive failures → mark source `degraded` → Telegram alert
- Log every fetch: `source`, `timestamp`, `item_count`, `http_status`, `latency_ms`

---

## Architecture

```
Sources (Tier 1 + 2 RSS/APIs — v1)
    ↓
Ingestion Job (APScheduler, every 6h)
    ├── feedparser + httpx
    ├── Dedup L1: URL SHA-256 hash (O(1) before any API call)
    ├── Dedup L2: cosine similarity of title embedding > DEDUP_THRESHOLD (config)
    └── Circuit breaker per source (3-strike → degraded → Telegram alert)

Processing Job (after ingestion)
    ├── Gemini Flash via OpenRouter: 3–5 sentence summary (Mode A)
    │   OR abstract stored directly (Arxiv Mode B)
    ├── Embed summary: nomic-embed-text-v1.5 via Nomic API (free tier, 1M tokens/month)
    ├── Tag: source tier, topic, entity mentions, published date
    └── Write to Postgres + pgvector

Ranking Job (daily, before briefing)
    └── score = (tier_weight × 0.35) + (recency × 0.35) + (novelty × 0.30)
        Tier 1: tier_weight=1.0 | Tier 2: 0.7 | Tier 3: 0.5

Briefing Job (APScheduler, 08:00 local)
    ├── Select top 6–8 ranked items (Tier 1 always represented if available)
    ├── Claude Haiku via OpenRouter: compose briefing — citations mandatory
    └── python-telegram-bot: post to personal chat

Query Handler (FastAPI, always-on — Telegram webhook or polling)
    ├── Receive Telegram message → embed query
    ├── Metadata filter: last 14 days, optional tier filter
    ├── pgvector search (k=10)
    ├── Claude Sonnet (Anthropic direct or OpenRouter): grounded answer + inline citations
    └── Reply in Telegram chat
```

---

## Models and LLM Gateway

### Model table

| Task | Model | Via | Rationale |
|---|---|---|---|
| Per-article summarisation | `google/gemini-2.5-flash` | OpenRouter | Lowest hallucination rate on summarisation benchmarks. ~$0.50/M input. 1M context. |
| Daily briefing composition | `claude-haiku-4-5` | OpenRouter | Writing quality and tone matter for daily reading. Haiku beats Gemini Flash in blind evals. $1/M input. |
| RAG query responses | `claude-sonnet-4-6` | OpenRouter | Multi-source grounded reasoning with citation. Hallucination risk is highest here. Sonnet justified. Prompt caching enabled — see ADR 010. |

**RAG prompt caching (ADR 010):**
The static system prompt in `app/rag/responder.py` is marked `cache_control: ephemeral`.
Anthropic caches it server-side for 5 minutes. Cache-hit queries pay $0.30/M on the system prompt
vs $3.00/M uncached — a 90% reduction on that token bucket. Cache writes cost $3.75/M (paid once
per 5-min window). Break-even is 2 queries per window. `cache_read_tokens` and `cache_write_tokens`
are logged in every `responder.done` structured log line.

**Why not Gemini Flash for briefing composition:**
In blind writing quality evaluations, Claude output is preferred ~47% of the time vs Gemini's ~24%.
The daily briefing is the user-facing product — writing quality is not interchangeable with summarisation.

**Why not local embeddings in v1:**
`nomic-embed-text-v1.5` via `sentence-transformers` requires loading `torch` (~1.5GB RAM at runtime on Railway).
This causes OOM risk on the Hobby plan worker service during cron. Use Nomic's free API instead.
Local embeddings are the right v2 upgrade if you self-host or move to a memory-rich instance.

### LLM Gateway: OpenRouter (primary)

OpenRouter provides a single API key and unified billing across all model providers.
Model swaps require one parameter change — no code changes.

**Env vars (all via Railway environment variables — never in source code):**
```
OPENROUTER_API_KEY        # primary LLM gateway
NOMIC_API_KEY             # embedding service (free tier)
TELEGRAM_BOT_TOKEN        # delivery + alert channel
TELEGRAM_CHAT_ID          # personal chat ID — send /start to @userinfobot to get it
DATABASE_URL              # injected by Railway Postgres service
LANGSMITH_API_KEY         # LangSmith tracing
LANGSMITH_PROJECT         # e.g. "briefcast-dev"
LANGSMITH_TRACING         # set to "true"
LANGSMITH_ENDPOINT        # https://apac.api.smith.langchain.com (APAC) or https://api.smith.langchain.com (US)
DEDUP_THRESHOLD=0.92      # plain number only — pydantic-settings cannot parse inline comments
OPENROUTER_APP_REFERER=https://github.com/SID-SURANGE/briefcast   # shown in OpenRouter dashboard
TAVILY_API_KEY            # web search fallback (free tier: 1,000/month at app.tavily.com); leave blank to disable
TELEGRAM_BRIEFING_THREAD_ID   # optional — Forum Topics supergroup thread ID for daily briefing; unset = main chat
TELEGRAM_ALERT_THREAD_ID      # optional — Forum Topics supergroup thread ID for alerts; unset = main chat
```

### Budget

| Account | Plan | Cost/mo |
|---|---|---|
| OpenRouter | Pay-as-you-go | ~$2–3 (Gemini Flash + Haiku + Sonnet RAG) |
| Railway | Hobby | ~$5 (API + worker + Postgres) |
| Telegram | Free | $0 |
| LangSmith | Developer free | $0 (5,000 traces/month) |
| Nomic API | Free | $0 (1M tokens/month) |
| GitHub | Free | $0 |

**App running cost: ~$7–8/month.** Claude Code (Claude.ai Pro, $20/month) is a development tool — cancel it once the app is stable. Log every API call from day one. Run `scripts/cost_report.py` weekly.

---

## Delivery: Web (Telegram removed — ADR 013)

Telegram was the original delivery channel (ADR 008, superseding an earlier Slack plan) but
was fully removed in ADR 013: the user stopped checking it, and a push channel nobody checks
has the same failure mode as no channel at all. `app/delivery/telegram_bot.py` no longer
exists — do not recreate it without the user explicitly asking; this was a considered removal,
not an oversight.

**Current delivery — `app/delivery/web.py` (FastAPI + Jinja2, no build step):**
- `GET /` — latest composed briefing (persisted to the `Briefing` table by `worker.py`) + a
  source-health panel reading `Source.circuit_breaker_state` directly (replaces the old
  Telegram alert-on-degrade)
- `GET /archive` — list of all past briefings; `GET /archive/{id}` — one archived briefing
- LLM-composed HTML is sanitized (`app/delivery/sanitize.py`, bleach allowlist) before being
  rendered with Jinja's `\| safe` — Telegram used to strip unsupported tags client-side as an
  incidental safety net; the browser has none, so this sanitization step is load-bearing, not
  decorative. Don't remove it even if it looks redundant.

`app/delivery/slack_bot.py` is an unwired stub (`send_briefing()` that does nothing) predating
this rework — not connected to `main.py` or `worker.py`. Leave it alone unless asked to build it
out or remove it explicitly; it's dead code, not a delivery option.

---

## Observability (v1 — no Helicone)

Three separate concerns. Keep them separate.

### 1. LLM/RAG tracing — LangSmith
```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<from smith.langchain.com>
LANGSMITH_PROJECT=briefcast-dev
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com   # APAC region — change if on US plan
```
Free tier: 5,000 traces/month — sufficient for personal use.
**Scope:** Only `app/rag/responder.py` uses LangChain LCEL (`_prompt | _llm`). This is the only layer where per-query trace visibility matters — seeing retrieved context + model response in one view.
Summariser and briefing composer use raw `httpx` — no LangChain overhead on batch jobs.
LangSmith env vars are bridged from pydantic-settings → `os.environ` at import time in `responder.py`.
Tracing is silently disabled if `LANGSMITH_API_KEY` is empty — no 403 noise in dev.

### 2. Application + cost logging — structlog (JSON only, no print())
Required fields on every LLM call:
```python
log.info("llm.call", model=model, task="summarise|briefing|rag",
         input_tokens=n, output_tokens=n, latency_ms=n,
         estimated_cost_usd=n, source=source_name)
```
`scripts/cost_report.py` aggregates logs and prints daily/weekly spend. Run manually weekly in v1.

### 3. Infrastructure — Railway native + health check
- `GET /healthz` → 200 (add from day 1)
- If ingestion hasn't run in 25h → post Telegram alert

### v2 additions (not now)
Langfuse or Helicone for richer cost dashboard · OpenTelemetry → Cloud Trace after GCP migration

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Web framework | FastAPI | Telegram webhook handler + `/healthz` |
| ORM | SQLAlchemy 2.x + Alembic | Migrations from day 1 |
| Scheduling | APScheduler (in-process) | No separate service needed in v1 |
| LLM gateway | OpenRouter | Single key for all models (Gemini Flash + Haiku + Sonnet) |
| RAG chains | LangChain LCEL only | Composable + LangSmith-native tracing |
| Text splitting | LangChain RecursiveCharacterTextSplitter | chunk_size=800, overlap=100 |
| Embeddings | Nomic API — `nomic-embed-text-v1.5` | Free tier (1M tokens/month). Local via sentence-transformers is v2. |
| Vector store | pgvector in Postgres | Single DB, no separate vector service |
| Delivery | python-telegram-bot>=21 | Webhook or long-poll mode |
| Ingestion | feedparser + httpx | |
| Containers | Docker + docker-compose | GCP migration path from day 1 |

**Not in v1:** LangGraph · Helicone · cross-encoder reranker · hybrid BM25 ·
query rewriting · frontend · user auth · Slack · local embedding model · Tier 3/4 sources

---

## v1 / v1.5 / v2 Decision Table

| Feature | Version | Key reason |
|---|---|---|
| Tier 1 + 2 sources | v1 | Core product |
| Telegram delivery | v1 | Free, instant setup, personal tool fit |
| Citations in all outputs | v1 | Non-negotiable trust signal |
| Semantic deduplication (2-layer) | v1 | Core value proposition |
| Metadata-filtered retrieval | v1 | RAG quality baseline |
| Structured cost logging | v1 | Replaces Helicone |
| OpenRouter gateway | v1 | Model flexibility + unified billing |
| Nomic API embeddings | v1 | Free, no RAM overhead |
| Tier 3 sources (DeepSeek, Qwen, Kimi) | v1.5 | Strategic but needs ingestion testing |
| Tier 4 newsletters | v1.5 | Add after base pipeline is proven |
| Eval harness (20 questions) | ✅ v1.5 done | RAGAS 4-metric harness built; run `python scripts/run_evals.py` |
| Hybrid BM25 + vector search | v1.5 | Measure vector baseline first |
| Cross-encoder reranker | v1.5 | Adds 100–300ms + API cost; trigger: retrieval quality feels poor after 2+ weeks |
| Query rewriting | v1.5 | Natural LangGraph candidate once baseline is proven |
| Slack delivery | v1.5 | Optional extension in `app/delivery/slack_bot.py` |
| LangGraph | v2 | Justified only with real conditional branching (query agent + validator) |
| Local embedding model | v2 | Switch from Nomic API to local when self-hosting or GCP memory allows |
| X/Twitter connector | v2 | Expensive, optional, not core |
| Any frontend | v2 | Backend pipeline is the product |

---

## File Structure

```
briefcast/
├── CLAUDE.md                   ← this file
├── docs/
│   ├── POLICY.md               ← public ingestion + storage policy for GitHub readers
│   ├── env-setup.md            ← local environment setup guide
│   └── railway-deployment.md  ← Railway deployment walkthrough
├── README.md
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic/
├── app/
│   ├── main.py                 ← FastAPI (Telegram webhook handler + /healthz)
│   ├── worker.py               ← APScheduler entry point
│   ├── config.py               ← all constants via pydantic-settings; no secrets in code
│   ├── db.py                   ← SQLAlchemy engine + SessionLocal + get_db()
│   ├── models/
│   │   ├── base.py             ← DeclarativeBase
│   │   ├── __init__.py         ← re-exports Article, Source (ensures Alembic sees all models)
│   │   ├── article.py          ← url, title, author, source_name, source_tier,
│   │   │                          published_at, summary, embedding, score,
│   │   │                          dedup_hash, storage_mode, deleted_at
│   │   └── source.py           ← source registry, tier, classification tag,
│   │                              circuit_breaker_state, storage_mode
│   ├── ingestion/
│   │   ├── fetcher.py          ← RSS + API fetchers (feedparser + httpx)
│   │   ├── dedup.py            ← L1 URL hash + L2 cosine (DEDUP_THRESHOLD from config)
│   │   └── circuit_breaker.py
│   ├── processing/
│   │   ├── summariser.py       ← Gemini Flash via OpenRouter; respects storage_mode
│   │   └── embedder.py         ← Nomic API client
│   ├── ranking/
│   │   └── ranker.py           ← weighted scorer; tier_weight boost
│   ├── briefing/
│   │   └── composer.py         ← Haiku via OpenRouter; citations mandatory
│   ├── rag/
│   │   ├── retriever.py        ← metadata-filtered pgvector search
│   │   └── responder.py        ← Sonnet (direct or OpenRouter); grounded + cited
│   ├── delivery/
│   │   ├── telegram_bot.py     ← primary delivery; briefings + alerts + query-back
│   │   └── slack_bot.py        ← v1.5 extension; add here without touching core
│   ├── connectors/
│   │   └── twitter/            ← v2; optional; disabled unless TWITTER_BEARER_TOKEN present
│   └── observability/
│       └── logger.py           ← structlog setup + cost calculation helpers
├── scripts/
│   ├── seed_sources.py         ← seed source registry into Postgres
│   ├── dry_run_ingestion.py    ← smoke-test registry and fetcher without writing to DB
│   ├── run_ingestion_once.py   ← one-shot ingestion against live DB
│   ├── run_evals.py            ← CLI entry point for RAGAS eval harness; --limit / --ids flags
│   └── cost_report.py          ← manual weekly cost aggregation from logs
├── evals/                      ← RAGAS eval harness (v1.5 complete)
│   ├── __init__.py             ← package marker
│   ├── questions.json          ← 20 Q&A pairs with ground truths + expected sources (updated May 2026)
│   ├── eval_runner.py          ← RAGAS 4-metric runner; Haiku judge; saves JSON reports
│   └── reports/                ← generated eval reports (gitignored)
├── decisions/
│   ├── 001-pgvector-over-pinecone.md
│   ├── 002-model-selection-cost-quality.md
│   ├── 003-rss-only-v1-ingestion.md
│   ├── 004-citations-mandatory.md
│   ├── 005-google-tier1-priority.md
│   ├── 006-storage-modes.md
│   ├── 007-openrouter-gateway.md
│   ├── 008-telegram-over-slack.md
│   ├── 009-nomic-api-over-local-embedding.md
│   └── 010-prompt-caching-rag-system-prompt.md
└── tests/
    ├── test_dedup.py
    ├── test_ranker.py
    └── test_retriever.py
```

---

## Coding Conventions

- Type hints on all function signatures — always
- Pydantic models at all data boundaries (ingestion input, DB write, API response)
- `structlog` only — no `print()`
- Black + isort + ruff — CI-enforced
- All external API calls: `try/except` + structured error log
- No credentials in code — env vars via `pydantic-settings` only
- `deleted_at` soft-delete column on all content tables
- `storage_mode` field on article: `"summary_metadata"` | `"abstract_metadata"` | `"processed_discard"`

---

## Architecture Exam Concepts

Name RAG stages correctly in ADRs and code comments:
`Ingestion → Deduplication → Chunking → Embedding → Indexing → Retrieval → Reranking (v1.5) → Generation → Evaluation (v1.5)`

**Key decisions to defend:**

| Decision | Defence |
|---|---|
| pgvector over dedicated vector DB | Single DB, metadata + vector joins in SQL, no extra infra at <1M vectors |
| RSS/API-only ingestion in v1 | Legal clarity, stability, forces curation discipline |
| Gemini Flash for summarisation | Lowest hallucination rate on summarisation benchmarks, 5x cheaper than Haiku |
| Haiku for briefing composition | Writing quality matters for daily reading; Claude preferred in blind evals |
| Sonnet for RAG responses | Multi-source grounded reasoning with citation risk — quality is non-negotiable |
| Nomic API over local embedding | No RAM overhead on Railway Hobby; same model, free tier, simpler ops |
| Prompt caching on RAG system prompt | Static system prompt cached ephemeral (5-min TTL); cache reads cost 90% less than full input. Break-even at 2 queries/window. See ADR 010. |
| OpenRouter gateway | Single key, unified billing, model swaps without code changes |
| Telegram over Slack | Free, instant, no OAuth, unlimited history, personal tool fit |
| Citations mandatory from day 1 | Groundedness is the product's primary trust signal |
| Google Tier 1 boost | Product goal explicitly aligned with career/profile goal — defensible |
| 2-layer dedup | O(1) hash for known URLs; cosine similarity catches near-duplicates across sources |

**Evaluation vocabulary:**
`retrieval recall@k` · `answer faithfulness` · `answer relevance` · `groundedness` ·
`dedup precision` · `source freshness` · `dedup threshold calibration`

---

## Deployment

### Local dev
```powershell
docker compose up -d db
.venv\Scripts\alembic upgrade head
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
.venv\Scripts\python -m app.worker   # manual trigger for testing
```

### Railway (v1 platform)
- **API service:** FastAPI always-on — Telegram webhook handler + `/healthz`
- **Worker service:** APScheduler cron — 06:00 UTC ingest, 08:00 UTC briefing
- **DB:** Railway Postgres + `CREATE EXTENSION vector;` in first Alembic migration
- Env vars: set in Railway dashboard — never in source code

### GCP migration (future — same Docker images, no code changes)

| Railway | GCP Equivalent |
|---|---|
| API service | Cloud Run (min-instances=1) |
| Worker cron | Cloud Run Job + Cloud Scheduler |
| Postgres + pgvector | Cloud SQL Postgres 15 + pgvector extension |
| Env vars | Secret Manager |
| Logs | Cloud Logging (automatic with Cloud Run) |
| Docker image | Artifact Registry + Cloud Build |

---

## Hard Rules — Never Violate

- No HTML scraping of any source
- No full article body text stored in DB
- No body excerpts beyond headline or subheading stored
- No raw Mode C content written to DB
- No LangGraph, Helicone, or cross-encoder reranker in v1
- No `print()` — structlog only
- No type hint omissions on any function
- No frontend or auth system in v1
- No API key or credential in any source file
- No new source added without: (a) URL tested live, (b) ToS reviewed, (c) classification tag assigned, (d) storage mode set
- No Sonnet for batch per-article summarisation (wrong cost tier)
- No X connector enabled without `TWITTER_BEARER_TOKEN` in env
- No local embedding model loaded in v1 worker (RAM risk on Railway Hobby)

---

## Development Commands

### First-time local setup (run once after cloning)

```powershell
# 1. Create virtual environment (Windows — all Python commands use .venv, never global)
python -m venv .venv

# 2. Install project + dev dependencies into .venv
.venv\Scripts\pip install -e ".[dev]"

# 3. Copy and fill in credentials
copy .env.example .env
# Edit .env — set OPENROUTER_API_KEY, NOMIC_API_KEY, TELEGRAM_BOT_TOKEN,
# DATABASE_URL, LANGSMITH_API_KEY, LANGSMITH_TRACING, LANGSMITH_PROJECT, LANGSMITH_ENDPOINT
# DEDUP_THRESHOLD=0.92  ← set a plain number, no inline comments

# 4. Start Postgres (pgvector image — pulls on first run)
docker compose up -d db

# 5. Wait for Postgres to be ready, then apply migrations
docker exec briefcast-db-1 pg_isready -U briefcast
.venv\Scripts\alembic upgrade head

# 6. Start the API server
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 7. Verify
# GET http://localhost:8000/healthz  →  {"status": "ok"}
```

### Day-to-day (existing environment)

```powershell
# Start only the DB (use when API runs locally, not in Docker)
docker compose up -d db

# Apply DB migrations
.venv\Scripts\alembic upgrade head

# Create a new migration after model changes
.venv\Scripts\alembic revision --autogenerate -m "description"

# Run all tests
.venv\Scripts\pytest tests/ -v

# Run a single test file
.venv\Scripts\pytest tests/test_dedup.py -v

# Run a single test by name
.venv\Scripts\pytest tests/test_dedup.py::test_function_name -v

# Lint + format check
.venv\Scripts\ruff check app/ && .venv\Scripts\black --check app/ && .venv\Scripts\isort --check app/

# Auto-fix lint
.venv\Scripts\ruff check --fix app/ && .venv\Scripts\black app/ && .venv\Scripts\isort app/

# Weekly cost report
.venv\Scripts\python scripts/cost_report.py
```

---

## Session Startup Checklist

1. Open VS Code from project root — Claude Code extension reads CLAUDE.md automatically
2. Check `decisions/` for relevant ADRs before any architectural choice
3. `docker compose up -d db` → verify DB connection and `pgvector` extension active
4. `.venv\Scripts\pytest tests/ -v` before making any changes
5. Schema change → `.venv\Scripts\alembic revision --autogenerate -m "description"`
6. New source → test URL live + review ToS + assign classification tag + assign storage mode + document in source table above

---

> **v1.1 | 2026-05-18 | Prune monthly. Every line must change Claude's behaviour or be cut.**
