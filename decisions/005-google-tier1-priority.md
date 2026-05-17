# ADR 005: Google AI family as Tier 1 with ranking boost

## Status
Accepted

## Context
The project goal is to stay current on AI with a Google career-alignment focus.
Ranking must reflect this priority explicitly rather than treating all sources equally.

## Decision
Google AI Blog, Google Research, Google Cloud AI, and DeepMind are Tier 1 (tier_weight=1.0).
Ranking formula: score = (tier_weight × 0.35) + (recency × 0.35) + (novelty × 0.30).
Tier 1 must always be represented in the daily briefing if any items are available.

## Consequences
Briefing is explicitly Google-first. This is intentional and documented.
