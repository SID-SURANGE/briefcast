# 🔑 Environment Variables — Setup Guide

> How to obtain every value in `.env.example`.
> Copy `.env.example` to `.env` and fill in each variable as you work through this guide.

```bash
cp .env.example .env
```

---

## Required

### `OPENROUTER_API_KEY`

OpenRouter is the single LLM gateway for all three models: Gemini Flash (summarisation), Claude Haiku (briefing), and Claude Sonnet (RAG).

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

### `TELEGRAM_BOT_TOKEN`

The bot token is used to send daily briefings, alerts, and query-back replies to your personal Telegram chat.

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts (choose any name and username).
3. BotFather replies with a token in the format `123456789:ABCdef...`.
4. Copy that token.

**Find your personal chat ID** (needed to receive messages):

1. Search for **@userinfobot** on Telegram.
2. Send it `/start` — it replies with your numeric chat ID (e.g. `987654321`).
3. Store it somewhere handy — you will hardcode it in `app/delivery/telegram_bot.py` or add it as a separate env var when you implement delivery.

```
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
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

**Railway (production):** Railway injects this automatically when you link a Postgres service. Copy it from **Variables** tab of your Railway project — do not set it manually there.

---

## LangSmith tracing

LangSmith traces every LangChain LCEL call (RAG chains). Free tier gives 5,000 traces/month — enough for personal use. All three variables are needed together; leave all unset to disable tracing entirely.

### `LANGSMITH_TRACING`

```
LANGSMITH_TRACING=true
```

Set to `true` to enable. Omit or set to `false` to disable (no traces sent, no API key needed).

---

### `LANGSMITH_API_KEY`

1. Go to [smith.langchain.com](https://smith.langchain.com) and sign up.
2. Navigate to **Settings** → **API Keys** → **Create API Key**.
3. Copy the key (starts with `lsv2_...`).

```
LANGSMITH_API_KEY=lsv2_pt_...
```

---

### `LANGSMITH_PROJECT`

The project name that groups traces in the LangSmith UI. Use any string — `briefcast-dev` is a sensible default.

```
LANGSMITH_PROJECT=briefcast-dev
```

---

### `LANGSMITH_ENDPOINT`

The regional API endpoint for your LangSmith account. Check your LangSmith portal for the correct URL.

```
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com   # APAC
# or
LANGSMITH_ENDPOINT=https://api.smith.langchain.com        # US (default)
```

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
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
DATABASE_URL=postgresql+psycopg://briefcast:briefcast@localhost:5432/briefcast

# LangSmith
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=briefcast-dev
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com

# Tuning
DEDUP_THRESHOLD=0.92
```

**Never commit `.env` to git.** It is already in `.gitignore`. Only `.env.example` (with empty values) belongs in the repo.
