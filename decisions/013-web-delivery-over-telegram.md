# ADR 013 · Web UI over Telegram for delivery

## Status
Accepted

## Context
Telegram delivery (ADR 008) required a bot token, a webhook endpoint, and an
always-on API process to receive updates. The composed briefing was never
persisted — `composer.py` produced text that went straight to `send_briefing()`
and was discarded. There was no way to view a past briefing or the RAG answer
outside the Telegram app, and circuit-breaker alerts depended on the same
Telegram bot being reachable.

Moving to Cloud Run (see ADR 014) makes an always-on webhook process
unnecessary and undesirable — Cloud Run scale-to-zero only works cleanly for
request/response HTTP, not long-poll or persistent bot sessions.

## Decision
Remove Telegram delivery entirely — no flag, no fallback path. Replace it with
a server-rendered web UI: FastAPI + Jinja2, no build step, no JS framework.

- `GET /` renders the latest persisted `Briefing`.
- `GET /ask` + `POST /api/ask` expose the existing `app/rag/responder.py`
  unchanged — the RAG pipeline was already channel-agnostic.
- A source-health panel on `/` reads `Source.circuit_breaker_state` directly
  instead of pushing a Telegram alert.
- The composed briefing is now persisted to a new `Briefing` table so `/` has
  something to render and briefings survive process restarts.

`app/delivery/telegram_bot.py`, the `/telegram` webhook, `python-telegram-bot`,
and all `TELEGRAM_*` config are deleted, not deprecated.

## Consequences
- One fewer external dependency (bot token, webhook registration, Telegram API
  availability) in the critical path.
- Briefings are now durable and queryable — enables a future "last 7 days"
  view with zero new infrastructure.
- Loses push notification — the user must visit the page instead of getting
  pinged. Acceptable for a personal tool; a future v2 could add a cron-sent
  email digest without touching the RAG/composer core.
- Loses Telegram drill-down buttons (per-company deep dive) and typing
  indicators — not reimplemented in v1 web UI; can be added as extra sections
  on `/` later if wanted.
- `app/rag/chat_responder.py` (direct-chat, no retrieval) was already dead code
  before this change (ADR 011 removed the `/chat` command) — deleted as part
  of this cleanup, not kept as a dependency of the web UI.
