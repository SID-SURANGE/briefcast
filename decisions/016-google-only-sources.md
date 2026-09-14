# ADR 016 · Google-family-only source registry

## Status
Accepted

## Context
ADR 005 already boosted Google sources to Tier 1 and guaranteed them a slot
in every briefing — a deliberate career-alignment choice, not a claim that
Google content is objectively better. With Tier 2 (OpenAI, Hugging Face,
Meta, arXiv, Microsoft, NVIDIA) still ingested, the briefing was a
Google-weighted view of the whole AI ecosystem. This narrows it further:
Google is no longer just weighted first, it's the only thing ingested.

This is explicitly the same career-narrative motivation as ADR 005, taken
one step further — not a claim that a Google-only briefing is a better
product for staying current on AI broadly. It is a real trade: dropping
OpenAI/Anthropic/Meta/etc. means genuinely losing visibility into what
competitors are shipping.

## Decision
`app/ingestion/registry.py` keeps only Google AI Blog, Google Research
Blog, Google Cloud AI Blog, and Google DeepMind Blog. All other sources are
removed from the registry (not disabled — removed).

`sync_sources()` now soft-deletes any existing `Source` row whose name is
no longer in the registry, so removed sources stop being fetched rather
than lingering active in the DB. This makes the registry function as its
own docstring already claimed: the single source of truth, removals
included.

`app/briefing/composer.py`'s diversity cap moves from per-company
(`{"google": 4}` vs `2` for everyone else — a cap designed to stop one
company dominating a multi-company briefing) to per-exact-source-blog
(3 each). With only four Google blogs left, the old company-level grouping
would have collapsed all of them into one `"google"` bucket and capped the
*entire briefing* at 4 items — a bug the narrowing would otherwise have
introduced silently. `_MAX_ITEMS` drops from 10 to 8 to match the
already-stated "top 6–8" briefing size.

The ranker's `TIER_WEIGHTS` table is unchanged — with every remaining
source at tier 1, the tier term in the score becomes a constant, and
recency + novelty do the actual differentiating work. Left as-is rather
than removed, since it costs nothing and keeps the ranker correct if a
non-Google source is ever added back.

## Consequences
- Corpus and briefing are now genuinely Google-only, not Google-weighted —
  a real loss of breadth, not just emphasis.
- Composer's per-source cap fix was necessary, not optional — without it,
  narrowing the registry would have silently shrunk every briefing to 4
  items regardless of how much good content existed that day.
- `sync_sources()`'s soft-delete-on-removal is a general capability now,
  not a one-off cleanup script — any future source removal from the
  registry will automatically stop that source being fetched.
- If this trade turns out wrong (i.e. "what's Google doing" matters less
  than "what's happening in AI"), reverting means re-adding entries to
  `SOURCES` — `sync_sources()` will re-insert them on next sync, no schema
  change needed.
