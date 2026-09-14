# ☁️ Google Cloud Deployment Guide

> Deploy Briefcast to Google Cloud Run (API, scale-to-zero) + Cloud Run Jobs +
> Cloud Scheduler, backed by a Neon Postgres database. See
> [ADR 014](../decisions/014-cloud-run-neon-over-railway.md) for why this
> replaced Railway.

---

## Prerequisites

- A Google Cloud project with billing enabled (Cloud Run/Scheduler stay inside
  their free tiers at this traffic volume, but a project needs billing
  enabled to use them at all)
- `gcloud` CLI installed and authenticated (`gcloud auth login`, then
  `gcloud config set project <PROJECT_ID>`)
- A Neon account — [neon.com](https://neon.com) — free tier, no credit card
- All other credentials ready (see `docs/env-setup.md`)

---

## Step 0 — Enable APIs and create the Artifact Registry repo

Google Container Registry (`gcr.io`) is deprecated — this uses Artifact
Registry instead. One-time setup:

```powershell
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com `
  artifactregistry.googleapis.com cloudbuild.googleapis.com iam.googleapis.com

gcloud artifacts repositories create briefcast `
  --repository-format=docker `
  --location=<REGION> `
  --description="Briefcast container images"
```

Every image reference below is `<REGION>-docker.pkg.dev/<PROJECT_ID>/briefcast/briefcast`.

---

## Step 1 — Create the Neon project and enable pgvector

1. Create a project at [console.neon.com](https://console.neon.com)
2. Open the **SQL Editor** (or connect with any Postgres client using the
   connection string from the dashboard) and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Verify: `SELECT * FROM pg_extension WHERE extname = 'vector';` — should
   return one row
4. Copy the **pooled** connection string from the dashboard — it already
   includes `?sslmode=require`. Keep that query param intact; you'll use this
   as `DATABASE_URL`.

---

## Step 2 — Build and push the image

```powershell
gcloud builds submit --tag <REGION>-docker.pkg.dev/<PROJECT_ID>/briefcast/briefcast .
```

The same image is used for the API service and both Cloud Run Jobs — only the
container command differs per resource. (This step is also what the CI/CD
workflow automates — see the **CI/CD** section below once the manual path
here works end-to-end.)

---

## Step 3 — Deploy the API service

```powershell
gcloud run deploy briefcast-api `
  --image <REGION>-docker.pkg.dev/<PROJECT_ID>/briefcast/briefcast `
  --region <REGION> `
  --min-instances 0 `
  --allow-unauthenticated `
  --set-env-vars "OPENROUTER_API_KEY=...,NOMIC_API_KEY=...,DATABASE_URL=...,DEDUP_THRESHOLD=0.92"
```

`--min-instances 0` is what makes this scale-to-zero — there's no webhook to
keep warm now that Telegram is gone (ADR 013), so idle time costs nothing.

> **Known gap**: `--allow-unauthenticated` means `/` is public on the Cloud
> Run URL. This matches the project's "no auth system" requirement
> (single-user personal tool). RAG query-back is parked (ADR 015), so the
> main cost-exposure risk this used to carry — unauthenticated requests
> triggering paid LLM/web-search calls — isn't currently live; revisit this
> gap if RAG is restored.

**Prefer Secret Manager over plaintext `--set-env-vars`** for
`DATABASE_URL`, `OPENROUTER_API_KEY`, and `NOMIC_API_KEY` in any deployment
you intend to keep running:

```powershell
echo "<value>" | gcloud secrets create briefcast-database-url --data-file=-
gcloud run deploy briefcast-api --update-secrets DATABASE_URL=briefcast-database-url:latest ...
```

Note the public URL Cloud Run prints (e.g.
`https://briefcast-api-xxxxx-uc.a.run.app`) — you'll need it below.

---

## Step 4 — Create the two Cloud Run Jobs

```powershell
gcloud run jobs create briefcast-ingest `
  --image <REGION>-docker.pkg.dev/<PROJECT_ID>/briefcast/briefcast `
  --region <REGION> `
  --command python `
  --args scripts/run_ingestion_once.py `
  --max-retries 1 `
  --task-timeout 1200 `
  --set-env-vars "OPENROUTER_API_KEY=...,NOMIC_API_KEY=...,DATABASE_URL=...,DEDUP_THRESHOLD=0.92"

gcloud run jobs create briefcast-briefing `
  --image <REGION>-docker.pkg.dev/<PROJECT_ID>/briefcast/briefcast `
  --region <REGION> `
  --command python `
  --args scripts/run_briefing_once.py `
  --max-retries 1 `
  --task-timeout 600 `
  --set-env-vars "OPENROUTER_API_KEY=...,DATABASE_URL=..."
```

These reuse the existing `scripts/run_ingestion_once.py` /
`scripts/run_briefing_once.py` one-shot scripts directly as the Job command —
no separate job-specific scripts needed, since "run once and exit" is already
their exact behavior.

---

## Step 5 — Create the Cloud Scheduler triggers

Two jobs, matching the exact cadence the in-process APScheduler worker used
to run (`hour="*/6"` for ingestion, `hour=3, minute=30` for briefing):

```powershell
gcloud scheduler jobs create http briefcast-ingest-trigger `
  --schedule "0 */6 * * *" `
  --uri "https://<REGION>-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/<PROJECT_ID>/jobs/briefcast-ingest:run" `
  --http-method POST `
  --oauth-service-account-email <SERVICE_ACCOUNT_EMAIL> `
  --time-zone "UTC"

gcloud scheduler jobs create http briefcast-briefing-trigger `
  --schedule "30 3 * * *" `
  --uri "https://<REGION>-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/<PROJECT_ID>/jobs/briefcast-briefing:run" `
  --http-method POST `
  --oauth-service-account-email <SERVICE_ACCOUNT_EMAIL> `
  --time-zone "UTC"
```

The service account needs the `roles/run.invoker` role on both Jobs.

> **Free tier note**: Cloud Scheduler gives 3 free jobs per month **per
> billing account**, not per project. If this billing account already runs
> other scheduled jobs, these 2 could tip you into the paid tier
> ($0.10/job/31-days — negligible, but not silently free). See
> [ADR 014](../decisions/014-cloud-run-neon-over-railway.md).

---

## Step 6 — Run Alembic migrations against Neon

```powershell
$env:DATABASE_URL="postgresql+psycopg://...neon.tech/...?sslmode=require"
.venv\Scripts\alembic upgrade head
```

---

## Step 7 — Seed sources

Same script as before, pointed at Neon instead of Railway:

```powershell
$env:DATABASE_URL="postgresql+psycopg://...neon.tech/...?sslmode=require"
.venv\Scripts\python scripts/seed_sources.py
```

Expected output: 4/4 sources reachable, `sources` table populated with the
Google-only registry (ADR 016).

---

## Step 8 — Run first ingestion and briefing manually

The corpus starts empty on Neon — no data is migrated from Railway (the
14-day rolling window refills automatically). Run once manually so there's
something to view before the first scheduled Job fires:

```powershell
$env:DATABASE_URL="postgresql+psycopg://...neon.tech/...?sslmode=require"
.venv\Scripts\python scripts/run_ingestion_once.py
.venv\Scripts\python scripts/run_briefing_once.py
```

---

## Step 9 — Verify end-to-end

```
# Health check
GET https://<CLOUD_RUN_URL>/healthz  →  {"status": "ok"}

# Digest page
GET https://<CLOUD_RUN_URL>/  →  renders the briefing persisted in Step 8
```

RAG query-back (`/ask`) is parked — see [ADR 015](../decisions/015-park-rag-query-back.md) — so there's nothing to verify there until it's restored.

---

## Schedule summary

| Job | UTC | IST |
|---|---|---|
| Ingestion (fetch + dedup + summarise + embed) | every 6h: 00:00, 06:00, 12:00, 18:00 | 05:30, 11:30, 17:30, 23:30 |
| Ranking | runs after each ingestion | same |
| Daily briefing | 03:30 | 09:00 |

---

## Redeployment

Manual: repeat Step 2 (`gcloud builds submit`) then Step 3's `gcloud run
deploy` with the new image tag, and `gcloud run jobs update` for the two
Jobs. Or use the CI/CD workflow below, which does exactly that on a manual
trigger. Migrations are **not** run automatically either way — run `alembic
upgrade head` yourself after a schema change (the CI/CD workflow has an
optional migration step, off by default — see below).

---

## CI/CD — GitHub Actions (manual trigger)

`.github/workflows/deploy.yml` builds the image, pushes it to Artifact
Registry, redeploys the Cloud Run service, and updates both Cloud Run Jobs
to the new image. It runs only on `workflow_dispatch` (you click "Run
workflow" in the GitHub Actions tab) — no auto-deploy on push, so nothing
ships without you choosing to ship it. Revisit that once the app has been
stable for a while, per the README roadmap.

Auth uses **Workload Identity Federation** — no long-lived GCP key is
stored in GitHub. This needs a one-time bootstrap:

### One-time GCP bootstrap (run locally, once)

```powershell
$PROJECT_ID = "<PROJECT_ID>"
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$REPO = "SID-SURANGE/briefcast"   # <owner>/<repo>, exact match required

# Pool + OIDC provider trusting only this GitHub repo
gcloud iam workload-identity-pools create "github-pool" `
  --project=$PROJECT_ID --location="global" --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "github-provider" `
  --project=$PROJECT_ID --location="global" `
  --workload-identity-pool="github-pool" `
  --display-name="GitHub Actions Provider" `
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" `
  --attribute-condition="assertion.repository=='$REPO'" `
  --issuer-uri="https://token.actions.githubusercontent.com"

# Deployer service account — this is what GitHub Actions impersonates, never a key
gcloud iam service-accounts create "github-deployer" `
  --project=$PROJECT_ID --display-name="GitHub Actions Deployer"
$DEPLOYER_SA = "github-deployer@$PROJECT_ID.iam.gserviceaccount.com"

gcloud iam service-accounts add-iam-policy-binding $DEPLOYER_SA `
  --project=$PROJECT_ID `
  --role="roles/iam.workloadIdentityUser" `
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$REPO"

# Minimum roles to build, push, and deploy
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SA" --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SA" --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SA" --role="roles/artifactregistry.writer"

# Print the provider resource name you'll need below
gcloud iam workload-identity-pools providers describe "github-provider" `
  --project=$PROJECT_ID --location="global" --workload-identity-pool="github-pool" `
  --format="value(name)"
```

### GitHub repo configuration

**Settings → Secrets and variables → Actions → Variables** (not secret — these
are identifiers, not credentials):

| Variable | Value |
|---|---|
| `GCP_PROJECT_ID` | your project ID |
| `GCP_REGION` | e.g. `us-central1` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | the full resource name printed above (`projects/.../workloadIdentityPools/github-pool/providers/github-provider`) |
| `GCP_SERVICE_ACCOUNT` | `github-deployer@<PROJECT_ID>.iam.gserviceaccount.com` |

**Settings → Secrets and variables → Actions → Secrets** (actual credentials):

| Secret | Value |
|---|---|
| `NEON_DATABASE_URL` | only needed if you ever tick the optional "run migrations" input — the pooled Neon connection string |

The service's own runtime secrets (`OPENROUTER_API_KEY`, `NOMIC_API_KEY`,
`DATABASE_URL`) live in GCP Secret Manager (Step 3) or as Cloud Run env
vars set during the first manual deploy — `gcloud run deploy` without
`--set-env-vars`/`--update-secrets` on a redeploy preserves whatever the
previous revision had, so the CI/CD workflow doesn't need to touch them at
all after that first manual deploy.

### Running it

GitHub → **Actions** tab → **Deploy to Cloud Run** → **Run workflow**. Leave
"run migrations" unchecked unless you've actually changed the schema since
the last deploy.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `/healthz` returns 502 / cold-start timeout | First request after scale-to-zero pays a cold start — retry; if it persists, check `gcloud run services logs read briefcast-api` |
| No briefing on `/` | Check `gcloud run jobs executions list --job briefcast-briefing` for the last run's logs; look for `worker.briefing_done` or `worker.briefing_no_articles` |
| 402 from OpenRouter | Account has no credits — add balance at openrouter.ai |
| DB connection errors after idle period | Neon free tier may have suspended compute (0.5GB storage / 100 CU-hour monthly cap exceeded) — check the Neon console; `pool_recycle=280` in `app/db.py` should prevent most idle-connection drops but not a full suspension |
| `pgvector` type not found | Extension not enabled — run `CREATE EXTENSION vector;` in the Neon SQL editor |
| Cloud Scheduler job not firing | Check `gcloud scheduler jobs describe <name>` for `lastAttemptTime`/errors; confirm the service account has `roles/run.invoker` |
