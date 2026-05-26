# ADR 002 · Model selection by task — cost and quality

## Status
Accepted

## Context
Three distinct LLM tasks with different quality and cost profiles:
per-article summarisation (high volume, low stakes), daily briefing composition (low volume, quality matters),
RAG responses (low volume, grounded reasoning required).

## Decision
- Summarisation: Gemini Flash via OpenRouter (~$0.50/M input, lowest hallucination on summarisation)
- Briefing composition: Claude Haiku via OpenRouter (~$1/M, preferred in blind writing evals)
- RAG responses: Claude Sonnet direct or OpenRouter (hallucination risk is highest here; Sonnet justified)

## Consequences
Three models, one OpenRouter key. Model swaps require one parameter change.
Sonnet must never be used for batch summarisation — wrong cost tier.
