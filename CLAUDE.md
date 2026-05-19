# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# Briefcast — personal AI intelligence briefing agent + RAG query-back
**CLAUDE.md · v1.3 · 2026-05-19**

Read this fully at the start of every Claude Code session before writing any code.
Lines marked `[VERIFY]` must be tested live before the connector is enabled.
This repo is open-source. Every decision must be safe for public GitHub.

---

## Project Identity

| Field | Value |
|---|---|
| What it is | Personal AI intelligence briefing pipeline + RAG query-back |
| Who uses it | Solo developer · single user · personal tool |
| Why it exists | Stay current on AI · build RAG engineering depth · strengthen Google profile |
| Delivery channel | Telegram (primary) — see delivery section |
| Open source | Yes. No scraping. No full-text storage. No credentials in code. Ever. |

**One-line description:** A self-hosted pipeline that ingests AI ecosystem updates via RSS/APIs,
deduplicates and ranks them (Google-first), delivers a daily briefing via Telegram,
and answers grounded follow-up questions over a rolling 14-day corpus.

---

## Current State & Next Steps

> **Keep this section current.** Update it at the end of every session or after every feature lands.
> Claude reads this first — an accurate status here avoids redundant codebase exploration.

### What is built and working (as of 2026-05-19)

| Layer | File(s) | Status |
|---|---|---|
| Config | `app/config.py` | ✅ pydantic-settings, all env vars, DEDUP_THRESHOLD |
| DB session | `app/db.py` | ✅ SQLAlchemy engine; normalises `postgresql://` → `postgresql+psycopg://` for Railway compat |
| Models | `app/models/article.py`, `source.py`, `base.py` | ✅ full schema with pgvector, soft-delete |
| Migrations | `alembic/versions/0001_*`, `0002_*` | ✅ applied on Railway; pgvector extension + both tables |
| API server | `app/main.py` | ✅ FastAPI + `/healthz` + `POST /telegram` webhook; deployed on Railway |
| Observability | `app/observability/logger.py` | ✅ `configure_logging()` JSON structlog; `log_llm_call()` with all required fields |
| RSS + arXiv fetcher | `app/ingestion/fetcher.py` | ✅ `fetch_rss()` feedparser+httpx; `fetch_arxiv()` Atom XML |
| Deduplication | `app/ingestion/dedup.py` | ✅ L1 SHA-256 hash; L2 cosine (numpy); `is_duplicate(url, embedding, db)` |
| Embedder | `app/processing/embedder.py` | ✅ Nomic API; `embed()` + `embed_batch()`; task_type param |
| Circuit breaker | `app/ingestion/circuit_breaker.py` | ✅ 3-strike → `degraded` on Source row; `record_success/failure/is_open(name, db)` |
| Summariser | `app/processing/summariser.py` | ✅ Gemini Flash via OpenRouter; `summarise(title, abstract, source)`; cost logged |
| Ranker | `app/ranking/ranker.py` | ✅ `score()` + `rank()`; tier/recency/novelty weights; pairwise novelty via numpy |
| Worker | `app/worker.py` | ✅ AsyncIOScheduler; `run_ingestion()` every 6h; `run_briefing()` 03:30 UTC (09:00 IST); deployed on Railway |
| Composer | `app/briefing/composer.py` | ✅ Haiku via OpenRouter; selects top 6–8 with Tier 1 guarantee; HTML for Telegram |
| Telegram bot | `app/delivery/telegram_bot.py` | ✅ `send_briefing()`, `send_alert()`; webhook registered at `@BrfCastBot` |
| RAG retriever | `app/rag/retriever.py` | ✅ pgvector `.cosine_distance()`; 14-day filter; optional tier filter; returns similarity score |
| RAG responder | `app/rag/responder.py` | ✅ Sonnet via OpenRouter; embed→retrieve→generate; inline HTML citations |
| Source registry | `app/ingestion/registry.py` | ✅ 8 sources (4 Tier 1 Google + 4 Tier 2); all URLs verified live |
| Source seeding | `scripts/seed_sources.py` | ✅ 8/8 sources seeded into Railway Postgres |
| One-shot ingestion | `scripts/run_ingestion_once.py` | ✅ first live ingestion running against Railway DB (in progress 2026-05-19) |
| Alembic env | `alembic/env.py` | ✅ URL scheme normalised; migrations run clean on Railway |
| Tests | `tests/test_dedup.py`, `test_ranker.py`, `test_retriever.py` | ✅ 32/32 passing |
| Railway deployment | API + Worker services | ✅ both deployed; API public domain active |

### Known verified feed URLs
- Meta AI Blog: `https://engineering.fb.com/feed/` (ai.meta.com/blog/rss/ returns 404)
- OpenAI News: `https://openai.com/news/rss.xml` (openai.com/news/rss/ returns 403)

### Railway deployment details
- API service: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Worker service: `python -m app.worker`
- DB: Railway Postgres; internal host `postgres.railway.internal:5432`; public host `centerbeam.proxy.rlwy.net:11559`
- Telegram bot: `@BrfCastBot` — webhook registered, bot page live at `t.me/BrfCastBot`
- Local Docker DB: stopped — all work now targets Railway Postgres via public URL

### What remains

| Step | What it needs |
|---|---|
| Confirm first ingestion completes | `run_ingestion_once.py` running — watch for `ranker.done` in logs |
| Trigger manual briefing | Run `run_briefing()` locally pointing at Railway DB to get first Telegram message |
| Confirm scheduled briefing fires | Daily at 13:00 IST via Railway worker — check Railway worker logs |
| Monitor first week | Check Railway logs for circuit breaker trips or 402s; run `scripts/cost_report.py` |

### Recommended next step

**Trigger a manual briefing** once `run_ingestion_once.py` completes. Point `DATABASE_URL` at the Railway public URL and run `run_briefing()` to verify the full end-to-end loop: Railway DB → composer → Telegram delivery. See `docs/railway-deployment.md` Step 10.

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

---

## Certification Alignment — Claude Architect Exam

This project maps directly to the Claude Architect Certification exam domains (approximate weights):

| Exam Domain | ~Weight | How this project covers it |
|---|---|---|
| Agentic Architecture | 27% | Ingestion → dedup → summarise → rank → brief → RAG is a multi-step agentic pipeline. ADRs document every decision. |
| Prompt Engineering | 20% | Summarisation prompt (Gemini Flash), briefing composition prompt (Haiku), RAG system prompt (Sonnet) with mandatory citations. Prompts versioned in `decisions/`. |
| Claude Code | 20% | All development via Claude Code VS Code extension. CLAUDE.md is the live agent context. |
| Tool Design & MCP | 18% | Source connectors as tools. RAG retriever as a tool. Telegram delivery as a tool. MCP server for source registry planned for v2. |
| Context Management & Reliability | 15% | Circuit breakers, 14-day rolling window, dedup threshold, structured logging, CLAUDE.md context discipline. |

**Daily learning habit:** Before implementing anything, ask Claude Code to explain the design decision.
After each ADR, ask Claude Code to map the decision to an exam domain.
Weekly: ask Claude Code to summarise architectural patterns used and how they map to exam domains.

Exam resources: claudecertifications.com — free study guide, practice questions, prep plan.

---

## Source Universe — Tiered, Google-First

Classification tags: `verified-official` | `verify-before-enabling` | `optional-connector` | `excluded`

### TIER 1 — Google AI Family (highest priority, v1 required)
Briefing ranks these above all others. Alert via Telegram immediately if any Tier 1 feed breaks.

| Source | Ingestion | Feed / Endpoint | Classification | Storage Mode |
|---|---|---|---|---|
| Google AI Blog | RSS | `https://blog.google/technology/ai/rss/` | `verify-before-enabling` | Mode A |
| Google Research Blog | RSS | `https://research.google/blog/rss/` | `verify-before-enabling` | Mode A |
| Google Cloud AI Blog | RSS | `https://cloudblog.withgoogle.com/rss/` | `verify-before-enabling` — filter AI/ML tags | Mode A |
| Google DeepMind Blog | RSS | `https://deepmind.google/blog/rss.xml` | `verify-before-enabling` — path uncertain | Mode A |

All four Google feeds are believed correct based on references but must be tested live.
If a feed path is wrong, check the source page for a canonical `/feed` or `/rss` link first.

### TIER 2 — Major Western AI Labs (v1 required)

| Source | Ingestion | Feed / Endpoint | Classification | Storage Mode |
|---|---|---|---|---|
| Anthropic | RSS | No confirmed native feed. Check `anthropic.com/news` for feed link. `[VERIFY]` | `verify-before-enabling` | Mode A |
| OpenAI | RSS | `https://openai.com/news/rss/` — has changed historically `[VERIFY]` | `verify-before-enabling` | Mode A |
| Hugging Face Blog | RSS | `https://huggingface.co/blog/feed.xml` `[VERIFY live]` | `verify-before-enabling` | Mode A |
| Meta AI Blog | RSS | `https://ai.meta.com/blog/rss/` `[VERIFY]` | `verify-before-enabling` | Mode A |
| Mistral AI | RSS | Check `mistral.ai/news` for `/rss` or `/feed` path. No confirmed URL. `[VERIFY]` | `verify-before-enabling` | Mode A |
| Cohere Blog | RSS | Check `cohere.com/blog` for feed path. No confirmed URL. `[VERIFY]` | `verify-before-enabling` | Mode A |
| Microsoft AI Blog | RSS | `https://blogs.microsoft.com/ai/feed/` | `verified-official` | Mode A |
| NVIDIA Blog | RSS | `https://blogs.nvidia.com/feed/` | `verified-official` | Mode A |
| Arxiv cs.AI + cs.LG | Official API | `https://export.arxiv.org/api/query` — public, no auth needed | `verified-official` | Mode B |

### TIER 3 — Major Open-Weight / Global Labs (v1.5 — add after MVP is stable)
Strategic importance is high in 2026. Use only globally accessible official channels.

| Source | Ingestion | Notes | Storage Mode |
|---|---|---|---|
| DeepSeek | GitHub Releases API | `github.com/deepseek-ai` releases `[VERIFY]` | Mode A |
| Qwen / Alibaba | HuggingFace + GitHub | `github.com/QwenLM`, `huggingface.co/Qwen` `[VERIFY]` | Mode A |
| Kimi / Moonshot AI | GitHub Releases + blog | `github.com/MoonshotAI`, `kimi.com/blog` `[VERIFY access]` | Mode A |
| ERNIE / Baidu | Official blog | `ernie.baidu.com/blog` — confirm feed and terms first `[VERIFY]` | Mode A |

**Policy for global sources:** Prefer GitHub, HuggingFace model cards, official English blogs.
Do not use region-restricted endpoints or channels requiring country-specific auth.
If access pattern, terms, or feed stability are unclear: exclude from v1.

### TIER 4 — High-Signal Newsletters (v1.5 — add after MVP is stable)

| Source | Ingestion | Feed |
|---|---|---|
| Import AI (Jack Clark) | Substack RSS | `https://importai.substack.com/feed` `[VERIFY]` |
| Ahead of AI (Raschka) | Substack RSS | `https://magazine.sebastianraschka.com/feed` `[VERIFY]` |
| The Gradient | RSS | `https://thegradient.pub/rss/` `[VERIFY]` |

### OPTIONAL CONNECTORS (user-credential-gated, v2)

| Source | Notes |
|---|---|
| X / Twitter API v2 | Pay-per-use, no free tier. Disabled by default. User supplies `TWITTER_BEARER_TOKEN`. Lives in `app/connectors/twitter/` isolated from core. Store: URL, author handle, our summary — never raw tweet text. |
| GitHub Starred repos | User supplies repo list. GitHub Releases API, official. Rate limit 5,000 req/hr authenticated. |

### EXCLUDED FROM ALL VERSIONS
- HTML scraping of any source
- Paywalled sources (MIT Tech Review full text, Nature, etc.)
- Sources requiring region-restricted credentials or unstable non-public endpoints
- Any source whose ToS prohibits automated access

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
| RAG query responses | `claude-sonnet-4-6` | OpenRouter | Multi-source grounded reasoning with citation. Hallucination risk is highest here. Sonnet justified. |

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

## Delivery: Telegram

Telegram replaces Slack as the primary delivery channel.

**Why Telegram:**
- Zero-cost setup — create bot via BotFather in 2 minutes, get `TELEGRAM_BOT_TOKEN`
- No OAuth flow, no app manifest, no workspace approval, no 90-day history limit
- Unlimited message history on free accounts
- `python-telegram-bot` SDK is mature, well-documented, actively maintained
- Cleaner fit for solo personal tool; Slack makes sense for team/enterprise contexts

**Delivery modes:**
- Briefings: bot sends formatted message to your personal chat ID daily at 08:00 local
- Alerts: circuit breaker degradations and ingestion failures post to same chat
- Query-back: reply to any message; FastAPI handles Telegram webhook or long-polling

**Slack:** Not required in v1. Can be added as v1.5 delivery extension in `app/delivery/slack_bot.py`.
The delivery layer in `app/delivery/` is abstracted — adding Slack is one new file, not a refactor.
See ADR `008-telegram-over-slack.md`.

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
| Eval harness (20 questions) | v1.5 | Add week 3 — portfolio differentiator |
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
│   └── cost_report.py          ← manual weekly cost aggregation from logs
├── evals/                      ← scaffold exists; flesh out at v1.5
│   ├── questions.json          ← 20 Q&A pairs with expected sources + citation check
│   └── eval_runner.py
├── decisions/
│   ├── 001-pgvector-over-pinecone.md
│   ├── 002-model-selection-cost-quality.md
│   ├── 003-rss-only-v1-ingestion.md
│   ├── 004-citations-mandatory.md
│   ├── 005-google-tier1-priority.md
│   ├── 006-storage-modes.md
│   ├── 007-openrouter-gateway.md
│   ├── 008-telegram-over-slack.md
│   └── 009-nomic-api-over-local-embedding.md
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
# DATABASE_URL, LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT
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
