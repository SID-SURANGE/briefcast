# ADR 004: Citations mandatory in all outputs

## Status
Accepted

## Context
The pipeline generates summaries, briefings, and RAG responses from external sources.
Groundedness is the primary trust signal for a personal intelligence tool.

## Decision
Every briefing item and every RAG response must include inline citations to source URLs.
This is enforced in prompts and validated in the eval harness.

## Consequences
Prompts must explicitly require citations. Eval harness checks citation presence.
Any model output without citations is treated as a failure.
