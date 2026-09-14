# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# Briefcast — personal Google AI intelligence briefing agent
**CLAUDE.md · v2.0 · 2026-09-14**

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

### Recent architectural decisions
ADR 013 (web UI over Telegram) → ADR 014 (Cloud Run + Neon over Railway) → ADR 015 (park RAG) → ADR 016 (Google-only sources) — read these before touching delivery, deployment, sources, or RAG. This file was fully reconciled against them on 2026-09-14; if it drifts again, trust the ADRs over old prose here.

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

**When compacting context:** always preserve the list of modified files, the current "What is built" status table, any GCP/Neon env var names, and active test commands.

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

**Mode B — Abstract + metadata** (Arxiv only — **currently dormant**, no Mode B source is active
since arXiv was removed in ADR 016; the mechanism stays in the schema for if it's ever needed again)
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
- Circuit breaker: 3 consecutive failures → mark source `degraded` → shown on the web dashboard's source-health panel (`GET /`)
- Log every fetch: `source`, `timestamp`, `item_count`, `http_status`, `latency_ms`

---

## Architecture

```
Sources (4 Google-family RSS feeds only — ADR 016)
    ↓
Ingestion Job (APScheduler locally / Cloud Run Job + Cloud Scheduler in prod, every 6h)
    ├── feedparser + httpx
    ├── LLM relevance classifier (Gemini Flash, YES/NO, fails open)
    ├── Dedup L1: URL SHA-256 hash (O(1) before any API call)
    ├── Dedup L2: cosine similarity of title embedding > DEDUP_THRESHOLD (config)
    └── Circuit breaker per source (3-strike → degraded → shown on web dashboard)

Processing (after ingestion)
    ├── Gemini Flash via OpenRouter: 3–5 sentence summary
    ├── Embed summary: nomic-embed-text-v1.5 via Nomic API (free tier, 1M tokens/month)
    └── Write to Postgres + pgvector

Ranking Job (after every ingestion)
    └── score = (tier_weight × 0.35) + (recency × 0.35) + (novelty × 0.30)
        Every remaining source is tier 1 (weight 1.0) since ADR 016 — the tier term is now
        a constant; recency + novelty do the actual differentiating work.

Briefing Job (APScheduler locally / Cloud Run Job + Cloud Scheduler in prod, 03:30 UTC / 09:00 IST)
    ├── Select top 8 ranked items, capped 3 per source blog (ADR 016)
    ├── Claude Haiku via OpenRouter: compose briefing — citations mandatory
    └── Persist to `briefings` table (no external delivery — see below)

Web UI (FastAPI + Jinja2, Cloud Run, scale-to-zero — ADR 013)
    ├── GET / — latest briefing (sanitized via bleach before `| safe` render) + source health
    └── GET /archive, GET /archive/{id} — every past briefing, browsable

RAG query-back — parked, not active (ADR 015). Was: embed query → pgvector search (k=10,
14-day window) → Claude Sonnet grounded answer + citations. Code intact in `archive/rag/`.
```

---

## Models and LLM Gateway

### Model table

| Task | Model | Via | Rationale |
|---|---|---|---|
| Per-article summarisation | `google/gemini-2.5-flash` | OpenRouter | Lowest hallucination rate on summarisation benchmarks. ~$0.50/M input. 1M context. |
| Daily briefing composition | `claude-haiku-4-5` | OpenRouter | Writing quality and tone matter for daily reading. Haiku beats Gemini Flash in blind evals. $1/M input. |

`claude-sonnet-4-6` for RAG query responses, and the prompt-caching setup that went with it
(ADR 010), are parked along with RAG itself (ADR 015) — code and rationale preserved in
`archive/rag/` and the ADR, not deleted. Don't re-add a Sonnet call without checking whether
RAG has actually been restored first.

**Why not Gemini Flash for briefing composition:**
In blind writing quality evaluations, Claude output is preferred ~47% of the time vs Gemini's ~24%.
The daily briefing is the user-facing product — writing quality is not interchangeable with summarisation.

**Why not local embeddings:**
`nomic-embed-text-v1.5` via `sentence-transformers` requires loading `torch` (~1.5GB RAM at runtime).
This causes OOM risk on a memory-constrained worker during cron (originally Railway Hobby;
same constraint applies to Cloud Run's default memory allocation). Use Nomic's free API instead.
Local embeddings are the right upgrade only if self-hosting on a memory-rich instance.

### LLM Gateway: OpenRouter (primary)

OpenRouter provides a single API key and unified billing across all model providers.
Model swaps require one parameter change — no code changes.

**Env vars (set as Cloud Run env vars/secrets — never in source code):**
```
OPENROUTER_API_KEY        # primary LLM gateway
NOMIC_API_KEY             # embedding service (free tier)
DATABASE_URL              # Neon pooled connection string — includes ?sslmode=require; not auto-injected, set explicitly
DEDUP_THRESHOLD=0.92      # plain number only — pydantic-settings cannot parse inline comments
OPENROUTER_APP_REFERER=https://github.com/SID-SURANGE/briefcast   # shown in OpenRouter dashboard
```
`TELEGRAM_*`, `LANGSMITH_*`, `TAVILY_API_KEY` were removed from `app/config.py` — see ADR 013 (Telegram)
and ADR 015 (RAG/LangSmith/Tavily). Re-add only alongside restoring the feature that used them.

### Budget

| Account | Plan | Cost/mo |
|---|---|---|
| OpenRouter | Pay-as-you-go | ~$2–3 (Gemini Flash + Haiku only — no Sonnet while RAG is parked) |
| Cloud Run (API + 2 Jobs) | Free tier | $0 |
| Cloud Scheduler (2 triggers) | Free tier (3 jobs/mo per billing account) | $0 |
| Neon (Postgres + pgvector) | Free tier | $0 |
| Nomic API | Free | $0 (1M tokens/month) |
| GitHub | Free | $0 |

**App running cost: ~$2–3/month** (down from ~$7–8/month on Railway+Telegram — see ADR 014).
Claude Code (Claude.ai Pro, $20/month) is a development tool — cancel it once the app is stable.
Log every API call from day one. Run `scripts/cost_report.py` weekly.

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

## Observability

### 1. Application + cost logging — structlog (JSON only, no print())
Required fields on every LLM call:
```python
log.info("llm.call", model=model, task="summarise|briefing",
         input_tokens=n, output_tokens=n, latency_ms=n,
         estimated_cost_usd=n, source=source_name)
```
`scripts/cost_report.py` aggregates logs and prints daily/weekly spend. Run manually weekly.

### 2. Infrastructure — Cloud Run native + health check
- `GET /healthz` → 200
- Circuit-breaker degradations surface on the web dashboard's source-health panel
  (`GET /`) — no external alert channel; check the page or Cloud Run logs directly.

### LangSmith tracing — parked with RAG (ADR 015)
LangSmith was scoped entirely to `app/rag/responder.py`'s LangChain LCEL chain — the only
layer that ever used LangChain. It's fully removed from `app/config.py` and the active
dependency tree. Setup instructions are preserved in `archive/rag/docs/langsmith-tracing.md`
for when/if RAG is restored. Do not re-add `LANGSMITH_*` config without restoring the RAG
module it traced.

### Not planned
Langfuse or Helicone for a richer cost dashboard — structlog + `cost_report.py` remains
sufficient at this scale.

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Web framework | FastAPI + Jinja2 | `GET /`, `GET /archive`, `GET /archive/{id}`, `/healthz` — no build step, no JS framework |
| ORM | SQLAlchemy 2.x + Alembic | Migrations from day 1 |
| Scheduling | APScheduler (local dev) · Cloud Run Jobs + Cloud Scheduler (prod, ADR 014) | Same 6h/03:30 UTC cadence either way |
| LLM gateway | OpenRouter | Single key for all active models (Gemini Flash + Haiku) |
| Embeddings | Nomic API — `nomic-embed-text-v1.5` | Free tier (1M tokens/month). Local embedding not planned — see rationale above. |
| Vector store | pgvector in Neon Postgres | Powers L2 near-dup detection; single DB, no separate vector service |
| Delivery | FastAPI + Jinja2 web UI | Telegram (`python-telegram-bot`) removed — ADR 013 |
| Ingestion | feedparser + httpx | 4 Google-family RSS feeds — ADR 016 |
| Containers | Docker + docker-compose (local) | Same image also runs as the two Cloud Run Jobs, different container command |
| Deployment | Google Cloud Run + Cloud Scheduler + Neon | ADR 014 — `docs/gcp-deployment.md` |

**Not active:** LangChain/LangChain LCEL, RAG retrieval, RAG eval harness (RAGAS), LangSmith
tracing, Tavily web search — all parked together in `archive/rag/`, ADR 015.
**Not planned:** LangGraph · Helicone · cross-encoder reranker · hybrid BM25 · query rewriting ·
user auth · Slack delivery (unwired stub exists, `app/delivery/slack_bot.py`) · non-Google
sources (ADR 016 — this is a decision, not a gap).

---

## Decision Table (superseded by ADRs 013–016 where they conflict — trust the ADRs)

| Feature | Status | Key reason |
|---|---|---|
| Google-only sources | ✅ shipped | ADR 016 — deliberate narrowing from 8 sources, career-alignment motivated, not "better product" |
| Web UI delivery | ✅ shipped | ADR 013 — replaces Telegram, which nobody was checking |
| Digest archive (`GET /archive`) | ✅ shipped | Every past briefing browsable, reuses existing `Briefing` data |
| Citations in briefing | ✅ shipped | Non-negotiable trust signal — ADR 004 |
| Semantic deduplication (2-layer) | ✅ shipped | Core value proposition |
| Structured cost logging | ✅ shipped | Replaces Helicone |
| OpenRouter gateway | ✅ shipped | Model flexibility + unified billing |
| Nomic API embeddings | ✅ shipped | Free, no RAM overhead |
| Cloud Run + Cloud Scheduler + Neon | ✅ shipped | ADR 014 — cost dropped ~$7–8/mo → ~$2–3/mo |
| RAG query-back | ⏸ parked | ADR 015 — usage never measured, infra was disproportionate; code intact in `archive/rag/` |
| RAGAS eval harness | ⏸ parked with RAG | Same ADR — only meaningful once RAG is restored |
| Flashcards from digest content | 💡 candidate, not started | Cheaper than RAG (no vector infra), matches "recall, don't ask" usage pattern — no ADR yet |
| Non-Google sources (Tier 2/3/4, newsletters) | ❌ rejected | ADR 016 — explicitly decided against, not merely deferred; don't re-add without the user asking |
| Slack delivery | ❌ not planned | Unwired stub exists (`slack_bot.py`) but nothing points to building it out |
| Hybrid BM25, cross-encoder reranker, query rewriting | ❌ moot | All were RAG-quality improvements; RAG itself is parked (ADR 015) |
| LangGraph | ❌ not planned | No conditional branching exists to justify it, and RAG (the only place it might apply) is parked |
| Local embedding model | ❌ not planned | RAM risk on a memory-constrained worker; Nomic API free tier is sufficient |
| X/Twitter connector | ❌ not planned | Expensive, optional, not core |

---

## File Structure

```
briefcast/
├── CLAUDE.md                   ← this file
├── docs/
│   ├── POLICY.md               ← public ingestion + storage policy for GitHub readers
│   ├── env-setup.md            ← local environment setup guide
│   ├── gcp-deployment.md       ← Cloud Run + Cloud Scheduler + Neon deployment walkthrough
│   └── architecture.md         ← full pipeline diagram (Mermaid)
├── README.md
├── docker-compose.yml
├── Dockerfile                  ← CMD respects Cloud Run's $PORT
├── pyproject.toml
├── alembic/
│   └── versions/                0001 (initial schema) · 0002 (source feed_type) · 0003 (briefings table)
├── app/
│   ├── main.py                 ← FastAPI, mounts app/delivery/web.py's router + /healthz. No webhook.
│   ├── worker.py                ← run_ingestion(), run_ranking(), run_briefing(); APScheduler entry locally
│   ├── config.py                ← pydantic-settings; RAG/Telegram settings removed
│   ├── db.py                    ← SQLAlchemy engine + SessionLocal + get_db(); pool_recycle for Neon
│   ├── models/
│   │   ├── base.py              ← DeclarativeBase
│   │   ├── __init__.py          ← re-exports Article, Briefing, Source
│   │   ├── article.py           ← url, title, summary, embedding, score, dedup_hash, storage_mode, deleted_at
│   │   ├── briefing.py          ← html_content, article_count, source_keys, published_at (no soft-delete — append-only)
│   │   └── source.py            ← tier, classification, storage_mode, circuit_breaker_state, deleted_at
│   ├── ingestion/
│   │   ├── fetcher.py           ← fetch_rss() (feedparser+httpx); fetch_arxiv() present but unused
│   │   ├── registry.py          ← SOURCES (4 Google feeds, ADR 016); sync_sources() upserts + soft-deletes stale rows
│   │   ├── classifier.py        ← LLM relevance filter (Gemini Flash, YES/NO, fails open)
│   │   ├── dedup.py             ← L1 URL hash + L2 cosine (DEDUP_THRESHOLD from config)
│   │   └── circuit_breaker.py
│   ├── processing/
│   │   ├── summariser.py        ← Gemini Flash via OpenRouter
│   │   └── embedder.py          ← Nomic API client
│   ├── ranking/
│   │   └── ranker.py            ← weighted scorer; tier term is now constant (ADR 016)
│   ├── briefing/
│   │   └── composer.py          ← Haiku via OpenRouter; per-source-blog diversity cap (ADR 016)
│   ├── delivery/
│   │   ├── web.py               ← GET /, GET /archive, GET /archive/{id}
│   │   ├── sanitize.py          ← bleach allowlist — sanitizes LLM HTML before `| safe` render
│   │   └── slack_bot.py         ← unwired stub, not connected to main.py/worker.py, not planned
│   ├── templates/                base.html, digest.html (handles both live + archived view), archive.html
│   ├── static/                   style.css
│   ├── connectors/twitter/       ← empty stub, v2, not started
│   └── observability/
│       └── logger.py            ← structlog setup + cost calculation helpers
├── scripts/
│   ├── init_db.py               ← migrations + seed sources, used by docker-compose
│   ├── seed_sources.py          ← verify feed URLs live, upsert registry into Postgres
│   ├── dry_run_ingestion.py     ← smoke-test registry and fetcher without writing to DB
│   ├── run_ingestion_once.py    ← one-shot ingestion — also the Cloud Run Job command
│   ├── run_ranking_once.py      ← one-shot ranking pass over existing articles
│   ├── run_briefing_once.py     ← one-shot compose + persist — also the Cloud Run Job command
│   └── cost_report.py           ← manual weekly cost aggregation from logs
├── archive/rag/                 ← parked RAG (retriever, responder, eval harness, tests) — ADR 015, restore guide in README.md there
├── decisions/                    001 through 016 — see decisions/ dir; 013–016 are the ones that changed most of this file
└── tests/
    ├── test_dedup.py
    └── test_ranker.py
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

RAG stage vocabulary (historical — RAG is parked, ADR 015, but this is still the correct
vocabulary if it's restored or discussed in an interview):
`Ingestion → Deduplication → Chunking → Embedding → Indexing → Retrieval → Reranking → Generation → Evaluation`

**Key decisions to defend — live ones first, then parked/historical ones (still worth knowing, since
this project's explicit goal includes career narrative, not just what's currently running):**

| Decision | Defence |
|---|---|
| Google-only source registry | Deliberate narrowing (ADR 016), same career-alignment motivation as the earlier tier boost, taken further — a real trade-off (loses competitor visibility), not a free win |
| pgvector over dedicated vector DB | Single DB, metadata + vector joins in SQL, no extra infra at <1M vectors — still used for L2 dedup even with RAG parked |
| RSS/API-only ingestion | Legal clarity, stability, forces curation discipline |
| Gemini Flash for summarisation | Lowest hallucination rate on summarisation benchmarks, 5x cheaper than Haiku |
| Haiku for briefing composition | Writing quality matters for daily reading; Claude preferred in blind evals |
| Nomic API over local embedding | No RAM overhead on a memory-constrained worker; same model, free tier, simpler ops |
| OpenRouter gateway | Single key, unified billing, model swaps without code changes |
| Web UI over Telegram (ADR 013) | A page you open has no "stopped checking it" failure mode; a push channel does |
| Cloud Run + Neon over Railway (ADR 014) | Scale-to-zero once there's no webhook to keep warm; free-tier Postgres; cost dropped ~$7–8/mo → ~$2–3/mo |
| Citations mandatory from day 1 | Groundedness is the product's primary trust signal |
| 2-layer dedup | O(1) hash for known URLs; cosine similarity catches near-duplicates across sources |
| *(parked)* Sonnet for RAG responses | Multi-source grounded reasoning with citation risk — quality is non-negotiable when it's live; not running now |
| *(parked)* Prompt caching on RAG system prompt | Cache reads cost 90% less than full input at 2+ queries/5-min window (ADR 010) — real technique, currently unused since RAG is parked |
| *(reversed)* Telegram over Slack (ADR 008) | Was the original delivery decision; superseded by ADR 013 — good example of a decision that was right at the time and wrong later, not a mistake |

**Evaluation vocabulary** (RAG-era, still correct terminology if discussed):
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

### Google Cloud (current platform — ADR 014, superseding Railway)
- **API service:** Cloud Run, `--min-instances 0` (scale-to-zero — no webhook to keep warm since Telegram removal) — `/healthz`, `GET /`, `GET /archive*`
- **Batch jobs:** two Cloud Run Jobs (`briefcast-ingest`, `briefcast-briefing`) reusing `scripts/run_ingestion_once.py` / `scripts/run_briefing_once.py` directly as their container command
- **Scheduling:** Cloud Scheduler triggers the two Jobs — `0 */6 * * *` (ingest), `30 3 * * *` UTC (briefing) — replaces the in-process APScheduler loop in prod only; local docker-compose dev still uses APScheduler
- **DB:** Neon (pgvector included, free tier) — connection string is NOT auto-injected like Railway's was; set `DATABASE_URL` explicitly as a Cloud Run env var/secret
- Env vars: prefer Secret Manager over plaintext `--set-env-vars` for anything sensitive
- Full walkthrough with exact `gcloud` commands: [`docs/gcp-deployment.md`](docs/gcp-deployment.md)
- **Known gap:** `--allow-unauthenticated` means `GET /` and `GET /archive*` are public — acceptable per the explicit "no auth system" requirement (single-user tool), documented as a trade-off, not an oversight

---

## Hard Rules — Never Violate

- No HTML scraping of any source
- No full article body text stored in DB
- No body excerpts beyond headline or subheading stored
- No raw Mode C content written to DB
- No LangGraph, Helicone, or cross-encoder reranker
- No `print()` — structlog only
- No type hint omissions on any function
- No auth system (single-user personal tool, by design) — but note a minimal web frontend
  (`app/delivery/web.py`, Jinja2, no build step) IS in scope now, unlike the earlier "no frontend"
  rule this superseded (ADR 013)
- No API key or credential in any source file
- No new source added without: (a) URL tested live, (b) ToS reviewed, (c) classification tag
  assigned, (d) storage mode set, (e) explicit user confirmation — the registry is Google-only
  by decision (ADR 016), not by omission; don't "helpfully" add a source back
- No Sonnet calls for batch per-article summarisation (wrong cost tier) — moot while RAG is
  parked (no active Sonnet usage at all), but the rule still applies if RAG is restored
- No X connector enabled without `TWITTER_BEARER_TOKEN` in env
- No local embedding model loaded in the worker (RAM risk on a memory-constrained instance)
- Don't recreate Telegram delivery, don't re-add `LANGSMITH_*`/`TAVILY_API_KEY`/`langchain`
  without the user explicitly asking — these are considered removals (ADR 013, ADR 015), not gaps

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
# Edit .env — set OPENROUTER_API_KEY, NOMIC_API_KEY, DATABASE_URL
# DEDUP_THRESHOLD=0.92  ← set a plain number, no inline comments
# (TELEGRAM_*/LANGSMITH_*/TAVILY_API_KEY no longer exist in app/config.py — ADR 013, ADR 015)

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

> **v2.0 | 2026-09-14 | Full reconciliation pass against ADRs 013–016 (web delivery, Cloud Run + Neon, RAG parked, Google-only sources). Prune monthly. Every line must change Claude's behaviour or be cut.**
