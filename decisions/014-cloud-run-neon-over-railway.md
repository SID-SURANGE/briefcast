# ADR 014 · Cloud Run + Neon over Railway

## Status
Accepted

## Context
Railway (API service + Worker service + Postgres) cost ~$7–8/month: ~$5 for
the Hobby plan covering two always-on services, plus Postgres storage, plus
~$2–3 LLM spend. The Worker service ran APScheduler in-process 24/7 just to
fire two cron jobs a day (ingest every 6h, briefing at 03:30 UTC) — most of
that uptime was idle.

Removing Telegram (ADR 013) removes the only reason the API needed to be
always-on (webhook receiver). With no webhook to keep warm, the API can be a
scale-to-zero HTTP service, and the worker can be two short-lived batch jobs
instead of a resident process.

## Decision
- **Compute**: Google Cloud Run (API service, scale-to-zero) replaces the
  Railway API service. Two Cloud Run Jobs (`briefcast-ingest`,
  `briefcast-briefing`) replace the Railway Worker service; each runs
  `run_ingestion()` / `run_briefing()` once and exits.
- **Scheduling**: Cloud Scheduler (2 jobs) triggers the two Cloud Run Jobs —
  ingest every 6h, briefing daily at 03:30 UTC. Replaces the in-process
  APScheduler loop in production. Local `docker-compose` dev keeps
  APScheduler unchanged — this is a prod-only scheduling change.
- **Database**: Neon (serverless Postgres, pgvector included) replaces
  Railway Postgres. Free tier, no credit card. Corpus starts fresh — the
  briefing corpus is a 14-day rolling window, so no data migration is
  needed; it refills automatically within 14 days of cutover.

## Consequences
- Expected cost drops from ~$7–8/month to ~$2–3/month (OpenRouter LLM spend
  only) — Cloud Run, Cloud Scheduler, and Neon all fit inside their 2026 free
  tiers at this traffic/data volume.
- Cold starts: the API scales to zero, so the first request after idle time
  pays a cold-start penalty (container boot + DB connect). Acceptable for a
  personal-traffic tool; not acceptable if this were public-facing at scale.
- Neon free tier can suspend compute (not data) if the project exceeds 100
  CU-hours or 0.5GB storage in a billing month — a request during suspension
  pays an extra cold-start-style resume delay. At this corpus size (14-day
  rolling window, single user) this is expected to be rare but is a known
  risk, not eliminated.
- Neon can drop idle connections more aggressively than Railway's proxy —
  `app/db.py`'s engine had no `pool_recycle`; one is added alongside this
  migration as a small hardening change.
- Cloud Scheduler's free tier is 3 jobs per month **per billing account**,
  not per project — if this GCP billing account already runs other scheduled
  jobs, briefcast's 2 jobs could push the account over the free allotment
  and start incurring $0.10/job/31-days. Flagged here, not silently assumed
  free.
- Two Cloud Run Jobs reuse the existing `scripts/run_ingestion_once.py` /
  `scripts/run_briefing_once.py` as their container command — same Docker
  image as the API service, different container command per Cloud Run
  resource.
