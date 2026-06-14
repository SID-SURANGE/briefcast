<p align="center">
  <img src="docs/images/Bot_logo.png" alt="BrfCastBot logo" width="80">
</p>

<h1 align="center">📡 Briefcast</h1>

<p align="center"><b>Your personal AI intelligence briefing agent</b><br>
Ingests the AI ecosystem. Ranks what matters. Delivers a daily briefing to Telegram. Answers your follow-up questions.</p>

<p align="center">
  <img src="docs/images/repo_header.png" alt="Briefcast — personal AI intelligence briefing agent" width="100%">
</p>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/pgvector-PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?style=flat-square)
![OpenRouter](https://img.shields.io/badge/OpenRouter-LLM_Gateway-FF6B35?style=flat-square)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=flat-square&logo=telegram&logoColor=white)
![Railway](https://img.shields.io/badge/Deployed_on-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 🧠 What it does

Briefcast runs a fully automated pipeline that monitors **Google AI, Google DeepMind, OpenAI, Anthropic, Meta AI, Hugging Face, Microsoft AI, NVIDIA, and arXiv** — then delivers a curated, ranked intelligence briefing to your Telegram every morning.

Ask a follow-up question directly in Telegram and it answers from a **grounded, cited 14-day rolling knowledge base** — no hallucinations, sources always shown.

```
Sources → Ingest → Deduplicate → Summarise → Rank → Brief → Answer
```

**No scraping. No paywalls. No raw article text stored. Open source.**

---

## 📱 Sample briefing

> Real output delivered to Telegram at 09:00 IST by **@BrfCastBot**

![Sample Briefcast briefing in Telegram](docs/images/Sample_brief.png)

---

## ✨ Core features

| Feature | Detail |
|---|---|
| 🥇 **Tiered source ranking** | Google AI family always surfaces first. Tier 1 → Tier 2 → arXiv. |
| 🔁 **2-layer deduplication** | SHA-256 URL hash (O(1)) + cosine similarity to catch near-duplicates across sources. |
| ✍️ **AI summarisation** | Gemini 2.5 Flash generates a tight 3–5 sentence summary per article. |
| 📰 **Daily briefing** | Claude Haiku composes a top 6–8 briefing with mandatory inline citations. Tier 1 sources always represented. Delivered at 09:00 IST. |
| 💬 **RAG query-back** | Ask anything in Telegram. Claude Sonnet answers from your 14-day corpus with citations. Tavily web search fallback on corpus miss. |
| ⚡ **Circuit breaker** | 3 consecutive feed failures → source marked degraded → Telegram alert fires immediately. |
| 💰 **Cost-conscious by design** | ~$2–3/month in LLM spend. Runs on a $5/month Railway instance. Total: ~$8/month. |

---

## 🔄 Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  📥 Sources (RSS / Official APIs)                       │
│  Google AI · DeepMind · OpenAI · Anthropic               │
│  Meta AI · Hugging Face · Microsoft · NVIDIA · arXiv    │
└────────────────────┬────────────────────────────────────┘
                     │ every 6h (APScheduler)
                     ▼
┌─────────────────────────────────────────────────────────┐
│  🔍 Ingestion + Deduplication                           │
│  feedparser + httpx → SHA-256 hash → cosine similarity  │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  ⚙️  Processing                                         │
│  Gemini Flash summary → Nomic embed → pgvector store    │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  📊 Ranking                                             │
│  score = tier(0.35) + recency(0.35) + novelty(0.30)     │
└────────────────────┬────────────────────────────────────┘
                     │ 09:00 IST daily
                     ▼
┌─────────────────────────────────────────────────────────┐
│  📬 Briefing → Telegram                                 │
│  Claude Haiku · top 10 items · citations mandatory      │
└────────────────────┬────────────────────────────────────┘
                     │ on demand
                     ▼
┌─────────────────────────────────────────────────────────┐
│  🤖 RAG Query-back                                      │
│  embed query → pgvector search → Claude Sonnet answer   │
└─────────────────────────────────────────────────────────┘
```

<video src="https://github.com/user-attachments/assets/4c163b81-144d-48e6-b487-ac9178530dac" autoplay loop muted playsinline width="100%"></video>

> 🎬 Pipeline animation generated with [**Gemini Omni Flash**](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni/) — Google's multimodal video generation model (Google I/O 2026)

---

## 🛠️ Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11 | Type hints enforced on all functions |
| Web framework | FastAPI | Telegram webhook handler + `/healthz` |
| Scheduling | APScheduler | In-process cron — no separate service needed |
| ORM + migrations | SQLAlchemy 2.x + Alembic | Schema versioned from day one |
| Vector store | pgvector (Postgres) | Single DB — metadata + vector joins in SQL |
| Embeddings | Nomic API `nomic-embed-text-v1.5` | Free tier, 1M tokens/month, zero RAM overhead |
| RAG chains | LangChain LCEL | LangSmith-native tracing built in |
| LLM gateway | OpenRouter | One API key for all models — swap with one param change |
| Delivery | python-telegram-bot ≥21 | Webhook + long-poll modes supported |
| Ingestion | feedparser + httpx | RSS/Atom + arXiv Atom API |
| Observability | structlog (JSON) + LangSmith | Structured cost logging + full RAG trace via LangChain LCEL |
| Deployment | Railway | API service + Worker service + Postgres |

---

## 🤖 Models

| Task | Model | Why |
|---|---|---|
| Per-article summary | `google/gemini-2.5-flash` | Lowest hallucination rate on summarisation benchmarks. ~$0.50/M tokens. |
| Daily briefing composition | `claude-haiku-4-5` | Claude wins blind writing quality evals. The briefing is the product — quality matters. |
| RAG query answers | `claude-sonnet-4-6` | Multi-source grounded reasoning with citation risk. Quality is non-negotiable here. |

All models are routed through **OpenRouter** — unified billing, no per-provider API keys, model swaps require one parameter change.

---

## 🔭 Observability

Two separate concerns, kept separate by design:

### LangSmith — RAG tracing
The RAG query path (`app/rag/responder.py`) is built as a **LangChain LCEL chain** (`prompt | llm | parser`). When `LANGSMITH_TRACING=true`, every query is traced end-to-end in [LangSmith](https://smith.langchain.com):

- Full prompt sent to Sonnet (including all retrieved context articles)
- Token counts and latency per call
- Retrieved document visibility — see exactly what context the model saw

LangSmith is the only layer using LangChain. The summariser and briefing composer use raw `httpx` — no overhead for batch jobs that don't need per-call trace visibility.

### structlog — cost logging
Every LLM call logs to structured JSON:
```python
log.info("llm.call", model=model, task="summarise|briefing|rag",
         input_tokens=n, output_tokens=n, latency_ms=n,
         estimated_cost_usd=n, source=source_name)
```
Run `scripts/cost_report.py` weekly to aggregate spend by model and task.

### Required env vars for tracing
```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<from smith.langchain.com>
LANGSMITH_PROJECT=briefcast-dev
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com   # APAC region
```

---

## 📁 Repo layout

```
briefcast/
├── app/
│   ├── main.py              # FastAPI — Telegram webhook + /healthz
│   ├── worker.py            # APScheduler — ingestion + briefing crons
│   ├── config.py            # pydantic-settings — all env vars, no secrets in code
│   ├── db.py                # SQLAlchemy engine + session
│   ├── models/              # Article, Source (pgvector, soft-delete)
│   ├── ingestion/           # fetcher, dedup, classifier, circuit breaker
│   ├── processing/          # summariser (Gemini Flash), embedder (Nomic)
│   ├── ranking/             # weighted ranker
│   ├── briefing/            # composer (Claude Haiku)
│   ├── rag/                 # retriever (pgvector), responder (Claude Sonnet)
│   ├── delivery/            # telegram_bot.py (primary), slack_bot.py (v1.5)
│   └── observability/       # structlog setup + cost logging helpers
├── scripts/
│   ├── init_db.py             # run migrations + seed sources (used by Docker Compose)
│   ├── seed_sources.py        # seed sources with live URL verification
│   ├── dry_run_ingestion.py   # smoke-test registry and fetcher without writing to DB
│   ├── run_ingestion_once.py  # one-shot ingestion against live DB
│   ├── run_evals.py           # CLI entry for RAGAS eval harness (--limit / --ids flags)
│   └── cost_report.py         # weekly LLM spend aggregated from logs
├── docs/
│   ├── POLICY.md              # public ingestion + storage policy
│   ├── env-setup.md           # local environment setup guide
│   ├── railway-deployment.md  # Railway deployment walkthrough
│   ├── eval-harness.md        # RAGAS eval harness — metrics, run commands, score guide
│   ├── langsmith-tracing.md   # LangSmith tracing — setup, span architecture, best practices
│   └── architecture.md        # full pipeline diagram (Mermaid)
├── decisions/               # ADRs — every architectural decision documented
├── evals/                   # RAGAS eval harness (v1.5 complete)
│   ├── eval_runner.py         # 4-metric runner; Haiku as judge; saves JSON reports
│   ├── questions.json         # 20 grounded Q&A pairs with ground truths (May 2026)
│   └── reports/               # generated eval reports (gitignored)
├── CHANGELOG.md             # keep-a-changelog format; v1.0 and v1.5 entries
├── alembic/                 # DB migrations (pgvector extension + full schema)
└── tests/                   # 32 tests — dedup, ranker, retriever
```

---

## 🚀 Run it locally

### Option A — Docker (recommended)

Postgres, migrations, source seeding, API, and worker all start with one command.

**1. Clone and configure**
```bash
git clone https://github.com/SID-SURANGE/briefcast.git
cd briefcast
cp .env.example .env   # Windows: copy .env.example .env
```

Open `.env` and fill in these four values — everything else is optional:

```env
OPENROUTER_API_KEY=sk-or-v1-...    # openrouter.ai — free account, add $5 credit
NOMIC_API_KEY=nk-...               # atlas.nomic.ai — free tier (1M tokens/month)
TELEGRAM_BOT_TOKEN=123456:ABC...   # create via @BotFather on Telegram
TELEGRAM_CHAT_ID=987654321         # send /start to @userinfobot to get yours
```

**2. Start everything**
```bash
docker compose up
```

Docker Compose will:
- Start a local Postgres + pgvector instance
- Wait for the DB to be healthy
- Run Alembic migrations and seed the source registry
- Start the API server on `http://localhost:8000`
- Start the worker (ingestion every 6h, briefing at 09:00 IST)

**3. Verify**
```
GET http://localhost:8000/healthz  →  {"status": "ok"}
```

**4. Trigger first ingestion manually**

The worker runs ingestion automatically every 6h and sends a briefing at 09:00 IST — but the DB starts empty. Run a one-off ingestion now so there's something to brief on:

```bash
docker compose exec worker python scripts/run_ingestion_once.py
```

Once articles are ingested, your Telegram bot will deliver briefings on schedule and answer questions immediately.

---

### Option B — Manual (for development)

```powershell
# 1. Clone and set up virtual environment
git clone https://github.com/SID-SURANGE/briefcast.git
cd briefcast
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

# 2. Configure credentials
copy .env.example .env
# Fill in: OPENROUTER_API_KEY, NOMIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# Also set: DATABASE_URL=postgresql+psycopg://briefcast:briefcast@localhost:5432/briefcast

# 3. Start Postgres with pgvector
docker compose up -d db

# 4. Apply migrations and seed sources
.venv\Scripts\python scripts/init_db.py

# 5. Run first ingestion
.venv\Scripts\python scripts/run_ingestion_once.py

# 6. Start the API server
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Verify: GET /healthz → {"status": "ok"}
```

---

## ☁️ Deploy on Railway

Railway runs two services from the same repo: the **API** (always-on FastAPI + Telegram webhook) and the **Worker** (APScheduler cron for ingestion + briefing). They share a Railway Postgres database.

Full walkthrough: [`docs/railway-deployment.md`](docs/railway-deployment.md)

### Prerequisites

- [Railway account](https://railway.app) (Hobby plan ~$5/month)
- Telegram bot token — create one via [@BotFather](https://t.me/BotFather)
- OpenRouter API key — [openrouter.ai](https://openrouter.ai)
- Nomic API key — [nomic.ai](https://atlas.nomic.ai) (free tier)
- LangSmith API key — [smith.langchain.com](https://smith.langchain.com) (free tier, optional)

### Steps

**1. Provision database**

Add a Railway Postgres plugin to your project. Railway injects `DATABASE_URL` automatically — the app normalises `postgresql://` → `postgresql+psycopg://` on startup.

Enable the pgvector extension (one-time, run in Railway's Postgres shell):
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**2. Deploy API service**

Create a new Railway service from this repo. Set the start command:
```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**3. Deploy Worker service**

Create a second Railway service from the same repo. Set the start command:
```
python -m app.worker
```

**4. Set environment variables** (both services)

```
OPENROUTER_API_KEY=
NOMIC_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=          # send /start to @userinfobot to get yours
DEDUP_THRESHOLD=0.92
OPENROUTER_APP_REFERER=
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=briefcast-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

**5. Run migrations and seed sources**

Point `DATABASE_URL` at your Railway public Postgres URL, then run locally:
```powershell
.venv\Scripts\alembic upgrade head
.venv\Scripts\python scripts/seed_sources.py
```

**6. Register the Telegram webhook**

Replace `<TOKEN>` and `<YOUR_RAILWAY_DOMAIN>` and call this once:
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<YOUR_RAILWAY_DOMAIN>/telegram
```

**7. Verify**

```
GET https://<your-railway-domain>/healthz  →  {"status": "ok"}
```

Trigger a manual ingestion to populate the DB, then send any message to your bot to test RAG query-back.

---

## 🛡️ Storage policy

Briefcast is built around ethical, attribution-respecting ingestion:

- **No full article body stored** — only our AI-generated summaries + metadata
- **No scraping** — RSS/Atom feeds and official APIs only
- **No paywalled sources** — ever
- **arXiv abstracts** stored directly (open programmatic access, designed for discovery indexing)
- **Soft-delete** on all content tables — nothing is hard-deleted

See [`docs/POLICY.md`](docs/POLICY.md) for the complete ingestion and storage policy.

---

## 💸 Cost breakdown

| Service | Plan | $/month |
|---|---|---|
| OpenRouter (Gemini Flash + Haiku + Sonnet) | Pay-as-you-go | ~$2–3 |
| Railway (API + Worker + Postgres) | Hobby | ~$5 |
| Nomic embeddings | Free tier (1M tokens/month) | $0 |
| LangSmith tracing | Developer free (5K traces/month) | $0 |
| Telegram | Free | $0 |
| **Total** | | **~$7–8/month** |

A fully automated personal AI intelligence pipeline for less than a coffee.

---

## 📐 Architecture

See the full interactive diagram → [`docs/architecture.md`](docs/architecture.md)
*(Mermaid — renders in GitHub, Notion, and [mermaid.live](https://mermaid.live))*

Every key design choice is documented as an ADR in [`decisions/`](decisions/).
A cross-cutting design FAQ covering chunking, model selection, ranking, and retrieval is at [`decisions/design-faq.md`](decisions/design-faq.md).

### Operational guides

| Guide | What it covers |
|---|---|
| [`docs/eval-harness.md`](docs/eval-harness.md) | RAGAS 4-metric eval harness — how to run, interpret scores, and when to re-evaluate |
| [`docs/langsmith-tracing.md`](docs/langsmith-tracing.md) | LangSmith RAG tracing — setup, span architecture, prompt cache visibility, best practices |
| [`docs/env-setup.md`](docs/env-setup.md) | Local environment setup |
| [`docs/railway-deployment.md`](docs/railway-deployment.md) | Railway deployment walkthrough |

| ADR | Decision |
|---|---|
| [`001`](decisions/001-pgvector-over-pinecone.md) | pgvector over Pinecone — single DB, SQL joins, no extra infrastructure at <1M vectors |
| [`002`](decisions/002-model-selection-cost-quality.md) | Model selection per task — cost vs quality calibrated to task risk |
| [`003`](decisions/003-rss-only-v1-ingestion.md) | RSS/API-only ingestion in v1 — legal clarity and feed stability over scraping flexibility |
| [`004`](decisions/004-citations-mandatory.md) | Citations mandatory — groundedness is the primary trust signal, not optional |
| [`005`](decisions/005-google-tier1-priority.md) | Google Tier 1 priority — explicitly aligned with career and product goals |
| [`007`](decisions/007-openrouter-gateway.md) | OpenRouter as LLM gateway — one key, unified billing, model swaps without code changes |
| [`008`](decisions/008-telegram-over-slack.md) | Telegram over Slack — free, no OAuth, unlimited history, right fit for a personal tool |
| [`009`](decisions/009-nomic-api-over-local-embedding.md) | Nomic API over local embeddings — no RAM overhead on Railway Hobby, same model quality |
| [`010`](decisions/010-prompt-caching-rag-system-prompt.md) | Prompt caching on RAG system prompt — 90% cost reduction on static token bucket at 2+ queries/window |
| [`011`](decisions/011-single-path-query-ux.md) | Single-path query UX — no /ask or /chat commands; plain message → corpus first, web fallback |
| [`012`](decisions/012-full-pipeline-langsmith-tracing.md) | Full LangSmith pipeline tracing via @traceable — end-to-end RAG visibility without LangChain overhead |
| [`FAQ`](decisions/design-faq.md) | Deep-dive: chunking, dedup thresholds, ranking weights, retrieval k, model rationale |

---

## 🗺️ Roadmap

- [x] RAG eval harness — RAGAS 4-metric harness, 20 grounded Q&A pairs, Haiku as judge
- [ ] Tier 3 sources — DeepSeek, Qwen, Kimi, Mistral
- [ ] Tier 4 newsletters — Import AI, Ahead of AI, The Gradient
- [ ] Hybrid BM25 + vector search — measure vector baseline first
- [ ] GCP migration path — Cloud Run + Cloud SQL, same Docker images, no code changes

---

## 📄 License

MIT
