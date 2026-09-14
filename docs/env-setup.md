# 🔑 Environment Variables — Setup Guide

> How to obtain every value in `.env.example`.
> Copy `.env.example` to `.env` and fill in each variable as you work through this guide.

```bash
cp .env.example .env
```

---

## Required

### `OPENROUTER_API_KEY`

OpenRouter is the single LLM gateway for both active models: Gemini Flash (summarisation) and Claude Haiku (briefing).

1. Go to [openrouter.ai](https://openrouter.ai) and create a free account.
2. Navigate to **Keys** → **Create Key**.
3. Copy the key (starts with `sk-or-...`).
4. Add credit — the pipeline costs roughly $2–3/month at normal usage.

```
OPENROUTER_API_KEY=sk-or-v1-...
```

---

### `NOMIC_API_KEY`

Used to generate vector embeddings via `nomic-embed-text-v1.5`. Free tier gives 1M tokens/month — sufficient for personal use.

1. Go to [atlas.nomic.ai](https://atlas.nomic.ai) and sign up.
2. Navigate to **Account** → **API Keys** → **Generate New Key**.
3. Copy the key.

```
NOMIC_API_KEY=nk-...
```

---

### `DATABASE_URL`

The Postgres connection string including credentials, host, port, and database name.

**Local development** (matches the `docker-compose.yml` defaults):

```
DATABASE_URL=postgresql+psycopg://briefcast:briefcast@localhost:5432/briefcast
```

Start the DB first:

```bash
docker-compose up -d db
alembic upgrade head
```

**Neon (production):** copy the pooled connection string from the Neon console — it already includes `?sslmode=require`. Unlike Railway, this is not auto-injected; set it explicitly as a Cloud Run env var or secret. See [`docs/gcp-deployment.md`](gcp-deployment.md).

---

> `LANGSMITH_*` and `TAVILY_API_KEY` are parked along with RAG query-back —
> see [ADR 015](../decisions/015-park-rag-query-back.md) and
> [`archive/rag/README.md`](../archive/rag/README.md) for setup instructions
> when that feature is restored.

---

## Tuning

### `DEDUP_THRESHOLD`

Cosine similarity cutoff for near-duplicate detection (L2 dedup). Two articles whose summary embeddings exceed this threshold are considered duplicates and the second is dropped.

- Default: `0.92` — safe starting point, catches near-identical reposts
- Raise toward `0.95` if too many legitimate similar articles are being dropped
- Lower toward `0.88` if duplicate reposts are slipping through

```
DEDUP_THRESHOLD=0.92
```

This value can be changed at any time without touching code — just update `.env` and restart.

---

## Complete `.env` for local development

```env
# Required
OPENROUTER_API_KEY=sk-or-v1-...
NOMIC_API_KEY=nk-...
DATABASE_URL=postgresql+psycopg://briefcast:briefcast@localhost:5432/briefcast

# Tuning
DEDUP_THRESHOLD=0.92
```

**Never commit `.env` to git.** It is already in `.gitignore`. Only `.env.example` (with empty values) belongs in the repo.
