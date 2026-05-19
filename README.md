# 📡 Briefcast

> **Your personal AI intelligence briefing agent.**
> Ingests the AI ecosystem. Ranks what matters. Delivers a daily briefing to Telegram. Answers your follow-up questions.

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

Briefcast runs a fully automated pipeline that monitors **Google AI, Anthropic, OpenAI, DeepMind, Hugging Face, Meta AI, and arXiv** — then delivers a curated, ranked intelligence briefing to your Telegram every morning.

Ask a follow-up question directly in Telegram and it answers from a **grounded, cited 14-day rolling knowledge base** — no hallucinations, sources always shown.

```
Sources → Ingest → Deduplicate → Summarise → Rank → Brief → Answer
```

**No scraping. No paywalls. No raw article text stored. Open source.**

---

## ✨ Core features

| Feature | Detail |
|---|---|
| 🥇 **Tiered source ranking** | Google AI family always surfaces first. Tier 1 → Tier 2 → arXiv. |
| 🔁 **2-layer deduplication** | SHA-256 URL hash (O(1)) + cosine similarity to catch near-duplicates across sources. |
| ✍️ **AI summarisation** | Gemini 2.5 Flash generates a tight 3–5 sentence summary per article. |
| 📰 **Daily briefing** | Claude Haiku composes a top 6–8 briefing with mandatory inline citations. Delivered at 13:00 IST. |
| 💬 **RAG query-back** | Ask anything in Telegram. Claude Sonnet answers from your 14-day corpus with citations. |
| ⚡ **Circuit breaker** | 3 consecutive feed failures → source marked degraded → Telegram alert fires immediately. |
| 💰 **Cost-conscious by design** | ~$2–3/month in LLM spend. Runs on a $5/month Railway instance. Total: ~$8/month. |

---

## 🔄 Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  📥 Sources (RSS / Official APIs)                       │
│  Google AI · DeepMind · OpenAI · Anthropic              │
│  Hugging Face · Meta AI · arXiv cs.AI + cs.LG           │
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
                     │ 13:00 IST daily
                     ▼
┌─────────────────────────────────────────────────────────┐
│  📬 Briefing → Telegram                                 │
│  Claude Haiku · top 6–8 items · citations mandatory     │
└────────────────────┬────────────────────────────────────┘
                     │ on demand
                     ▼
┌─────────────────────────────────────────────────────────┐
│  🤖 RAG Query-back                                      │
│  embed query → pgvector search → Claude Sonnet answer   │
└─────────────────────────────────────────────────────────┘
```

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
| Observability | structlog (JSON) + LangSmith | Structured cost logging + full RAG trace |
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

## 📁 Repo layout

```
briefcast/
├── app/
│   ├── main.py              # FastAPI — Telegram webhook + /healthz
│   ├── worker.py            # APScheduler — ingestion + briefing crons
│   ├── config.py            # pydantic-settings — all env vars, no secrets in code
│   ├── db.py                # SQLAlchemy engine + session
│   ├── models/              # Article, Source (pgvector, soft-delete)
│   ├── ingestion/           # fetcher, dedup, circuit breaker
│   ├── processing/          # summariser (Gemini Flash), embedder (Nomic)
│   ├── ranking/             # weighted ranker
│   ├── briefing/            # composer (Claude Haiku)
│   ├── rag/                 # retriever (pgvector), responder (Claude Sonnet)
│   ├── delivery/            # telegram_bot.py (primary), slack_bot.py (v1.5)
│   └── observability/       # structlog setup + cost logging helpers
├── scripts/
│   ├── seed_sources.py        # seed source registry into Postgres
│   ├── dry_run_ingestion.py   # smoke-test registry and fetcher without writing to DB
│   ├── run_ingestion_once.py  # one-shot ingestion against live DB
│   └── cost_report.py         # weekly LLM spend aggregated from logs
├── decisions/               # ADRs — every architectural decision documented
├── evals/                   # RAG eval harness scaffold (v1.5)
├── alembic/                 # DB migrations (pgvector extension + full schema)
└── tests/                   # 32 tests — dedup, ranker, retriever
```

---

## 🚀 Run it locally

```powershell
# 1. Clone and set up virtual environment
git clone https://github.com/your-username/briefcast.git
cd briefcast
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

# 2. Configure credentials
copy .env.example .env
# Fill in: OPENROUTER_API_KEY, NOMIC_API_KEY, TELEGRAM_BOT_TOKEN,
#          TELEGRAM_CHAT_ID, DATABASE_URL, LANGCHAIN_API_KEY

# 3. Start Postgres with pgvector
docker compose up -d db

# 4. Apply migrations
.venv\Scripts\alembic upgrade head

# 5. Seed sources and run first ingestion
.venv\Scripts\python scripts/seed_sources.py
.venv\Scripts\python scripts/run_ingestion_once.py

# 6. Start the API server
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Verify: GET /healthz → {"status": "ok"}
```

---

## 🛡️ Storage policy

Briefcast is built around ethical, attribution-respecting ingestion:

- **No full article body stored** — only our AI-generated summaries + metadata
- **No scraping** — RSS/Atom feeds and official APIs only
- **No paywalled sources** — ever
- **arXiv abstracts** stored directly (open programmatic access, designed for discovery indexing)
- **Soft-delete** on all content tables — nothing is hard-deleted

See [`POLICY.md`](POLICY.md) for the complete ingestion and storage policy.

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

## 📐 Architecture decisions

Every key design choice is documented as an ADR in [`decisions/`](decisions/):

| ADR | Decision |
|---|---|
| `001` | pgvector over Pinecone — single DB, SQL joins, no extra infrastructure at <1M vectors |
| `002` | Model selection per task — cost vs quality calibrated to task risk |
| `003` | RSS/API-only ingestion in v1 — legal clarity and feed stability over scraping flexibility |
| `004` | Citations mandatory — groundedness is the primary trust signal, not optional |
| `005` | Google Tier 1 priority — explicitly aligned with career and product goals |
| `007` | OpenRouter as LLM gateway — one key, unified billing, model swaps without code changes |
| `008` | Telegram over Slack — free, no OAuth, unlimited history, right fit for a personal tool |
| `009` | Nomic API over local embeddings — no RAM overhead on Railway Hobby, same model quality |

---

## 🗺️ Roadmap

- [ ] Tier 3 sources — DeepSeek, Qwen, Kimi, Mistral
- [ ] Tier 4 newsletters — Import AI, Ahead of AI, The Gradient
- [ ] RAG eval harness — 20 grounded Q&A pairs with source + citation checks
- [ ] Hybrid BM25 + vector search — measure vector baseline first
- [ ] GCP migration path — Cloud Run + Cloud SQL, same Docker images, no code changes

---

## 📄 License

MIT
