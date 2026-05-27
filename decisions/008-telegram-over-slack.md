# ADR 008 · Telegram over Slack for delivery

## Status
Accepted

## Context
Need a delivery channel for daily briefings, alerts, and query-back. Options: Slack, Telegram, email.

## Decision
Telegram via python-telegram-bot. Slack deferred to v1.5 as an optional extension in app/delivery/slack_bot.py.

## Consequences
Zero-cost setup, no OAuth, unlimited message history, personal tool fit.
Delivery layer is abstracted — adding Slack later is one new file.
