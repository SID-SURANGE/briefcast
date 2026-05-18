# Railway Deployment Guide

Deploy briefcast to Railway as two services (API + Worker) backed by a Railway Postgres database.

---

## Prerequisites

- Railway account at [railway.app](https://railway.app) — Hobby plan ($5/mo) is sufficient
- All credentials ready (see `docs/env-setup.md`)
- Code pushed to GitHub (Railway deploys from a repo)

---

## Step 1 — Create a Railway project

1. Go to [railway.app/new](https://railway.app/new)
2. Select **Deploy from GitHub repo** → authorise Railway → choose the `briefcast` repo
3. Railway creates a project and attempts an initial deploy — **cancel it** if it starts, you need to configure services first

---

## Step 2 — Add a Postgres database

1. In the project dashboard, click **+ New** → **Database** → **Add PostgreSQL**
2. Railway provisions a Postgres 16 instance automatically
3. Click the Postgres service → **Variables** tab → copy the `DATABASE_URL` value (format: `postgresql://...`) — you will need it in Step 4
4. Enable the pgvector extension — Railway Postgres does **not** enable it by default:
   - Click the Postgres service → **Query** tab (or connect via any Postgres client using the provided credentials)
   - Run: `CREATE EXTENSION IF NOT EXISTS vector;`
   - Verify: `SELECT * FROM pg_extension WHERE extname = 'vector';` — should return one row

---

## Step 3 — Configure the API service

Railway auto-created a service from the repo. Rename it:

1. Click the service → **Settings** → rename to `api`
2. **Settings → Build** — Railway will auto-detect the `Dockerfile` — leave as-is
3. **Settings → Deploy** → set **Start Command** to:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. **Settings → Networking** → click **Generate Domain** — note the public URL (e.g. `briefcast-api.up.railway.app`)

---

## Step 4 — Configure the Worker service

1. In the project dashboard, click **+ New** → **GitHub Repo** → select `briefcast` again
2. Rename to `worker`
3. **Settings → Deploy** → set **Start Command** to:
   ```
   python -m app.worker
   ```
4. No public domain needed for the worker

---

## Step 5 — Set environment variables

Set these on **both** the `api` and `worker` services. Go to each service → **Variables** tab → **Raw Editor** and paste:

```env
OPENROUTER_API_KEY=sk-or-v1-...
NOMIC_API_KEY=nk-...
TELEGRAM_BOT_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=<your numeric chat ID>
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=briefcast-prod
DEDUP_THRESHOLD=0.92
```

For `DATABASE_URL`: in each service's Variables tab, click **+ Add Variable Reference** → select the Postgres service's `DATABASE_URL`. This links it so Railway keeps it updated automatically — do not hardcode it.

> **Never paste your `.env` file directly** — it may contain comments that break pydantic-settings. Set each value as a plain key=value pair.

---

## Step 6 — Run Alembic migrations

Railway does not run migrations automatically. Do this once after the first deploy:

1. In the `api` service → **Settings** → temporarily change Start Command to:
   ```
   alembic upgrade head
   ```
2. Click **Deploy** — watch the logs until you see `INFO  [alembic.runtime.migration] Running upgrade ...`
3. Change Start Command back to `uvicorn app.main:app --host 0.0.0.0 --port 8000` and redeploy

Alternatively, connect to the Railway Postgres instance directly and run migrations from your local machine:
```powershell
# Set DATABASE_URL to the Railway value temporarily
$env:DATABASE_URL="postgresql+psycopg://..."
.venv\Scripts\alembic upgrade head
```

---

## Step 7 — Seed sources

After migrations, seed the sources table from local (point at Railway DB):

```powershell
$env:DATABASE_URL="postgresql+psycopg://<railway-db-url>"
.venv\Scripts\python scripts/seed_sources.py
```

---

## Step 8 — Register the Telegram webhook

Replace `<TOKEN>` and `<RAILWAY_DOMAIN>` with your values:

```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<RAILWAY_DOMAIN>/telegram
```

Open that URL in a browser — Telegram returns `{"ok":true,"result":true,"description":"Webhook was set"}`.

Verify it was registered:
```
https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

---

## Step 9 — Verify the deployment

```
# Health check
GET https://<RAILWAY_DOMAIN>/healthz
# Expected: {"status": "ok"}

# Trigger a one-shot briefing to verify end-to-end (from local, pointing at Railway DB)
$env:DATABASE_URL="postgresql+psycopg://<railway-db-url>"
.venv\Scripts\python -c "
import asyncio
from app.observability.logger import configure_logging
from app.worker import run_briefing
configure_logging()
asyncio.run(run_briefing())
"
```

A Telegram message should arrive in your chat within ~30 seconds.

---

## Schedule summary

| Job | UTC | IST |
|---|---|---|
| Ingestion (fetch + dedup + summarise + embed) | every 6h starting 00:00 | 05:30, 11:30, 17:30, 23:30 |
| Ranking | runs after each ingestion | same |
| Daily briefing | 03:30 | 09:00 |

---

## Redeployment

Every `git push` to the default branch triggers an automatic redeploy of both services. Migrations are **not** re-run automatically — only run `alembic upgrade head` manually after schema changes.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `/healthz` returns 502 | API service failed to start — check deploy logs for import errors |
| No briefing in Telegram | Worker logs → look for `worker.briefing_done` or `worker.briefing_no_articles` |
| 402 from OpenRouter | Account has no credits — add balance at openrouter.ai |
| Webhook not receiving updates | Run `getWebhookInfo` — check `last_error_message` field |
| `pgvector` type not found | Extension not enabled — run `CREATE EXTENSION vector;` in Railway Postgres query tab |
