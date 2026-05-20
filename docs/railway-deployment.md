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
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=briefcast-prod
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com
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

The seed script verifies all 8 RSS feed URLs are reachable, then upserts them
into the `sources` table. It only needs to run once after the first deploy (or
when you add new sources to `registry.py`).

### Get the public database URL

Railway gives you two database URLs:
- **Internal** (`postgres.railway.internal:5432`) — only reachable from inside Railway containers
- **Public** (`*.railway.app:<port>` or `*.proxy.rlwy.net:<port>`) — reachable from your laptop

To get the public URL:
1. In Railway dashboard → click the **Postgres** service
2. Click the **Variables** tab
3. Copy the value of `DATABASE_PUBLIC_URL` (not `DATABASE_URL`)

It will look like: `postgresql://postgres:<password>@roundhouse.proxy.rlwy.net:12345/railway`

### Run the seed from your local machine

```powershell
# Paste your DATABASE_PUBLIC_URL value here — note the +psycopg driver suffix
$env:DATABASE_URL="postgresql+psycopg://postgres:<password>@<public-host>:<port>/railway"
.venv\Scripts\python scripts/seed_sources.py
```

Expected output:
```
[OK  ] Google AI Blog  —  https://blog.google/technology/ai/rss/
[OK  ] Google Research Blog  —  https://research.google/blog/rss/
[OK  ] Google Cloud AI Blog  —  https://cloudblog.withgoogle.com/rss/
[OK  ] Google DeepMind Blog  —  https://deepmind.google/blog/rss.xml
[OK  ] OpenAI News  —  https://openai.com/news/rss.xml
[OK  ] Hugging Face Blog  —  https://huggingface.co/blog/feed.xml
[OK  ] Meta AI Blog  —  https://engineering.fb.com/feed/
[SKIP VERIFY] arXiv cs.AI + cs.LG  (verified-official API)

8/8 sources reachable

DB sync: 8 inserted, 0 updated
sources table now has 8 row(s)
```

After this, the `sources` table in your Railway Postgres has all 8 sources and
the worker can start ingesting.

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

## Step 9 — Run first ingestion against Railway DB

The Railway worker will ingest on its own schedule (every 6h), but run it
manually now so articles are in the DB before the first scheduled briefing.

```powershell
# Use the public DB URL with +psycopg driver suffix
$env:DATABASE_URL="postgresql+psycopg://postgres:<password>@<public-host>:<port>/railway"
.venv\Scripts\python scripts/run_ingestion_once.py
```

Let it run to completion — takes 5–10 minutes for all 8 sources. You'll see
`worker.source_done` log lines for each source, then `ranker.done` at the end.

---

## Step 10 — Verify end-to-end

```powershell
# 1. Health check — confirms API is up
# Open in browser: https://<RAILWAY_DOMAIN>/healthz
# Expected: {"status": "ok"}

# 2. Trigger a one-shot briefing to verify Telegram delivery
$env:DATABASE_URL="postgresql+psycopg://postgres:<password>@<public-host>:<port>/railway"
.venv\Scripts\python -c "
import asyncio
from app.observability.logger import configure_logging
from app.worker import run_briefing
configure_logging()
asyncio.run(run_briefing())
print('Done.')
"
```

A Telegram message should arrive in your chat within ~30 seconds. If you see
`worker.briefing_no_articles` in the logs, ingestion (Step 9) didn't complete
or no articles fell within the 14-day window.

---

## Schedule summary

| Job | UTC | IST |
|---|---|---|
| Ingestion (fetch + dedup + summarise + embed) | every 6h: 00:00, 06:00, 12:00, 18:00 | 05:30, 11:30, 17:30, 23:30 |
| Ranking | runs after each ingestion | same |
| Daily briefing | 07:30 | 13:00 |

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
