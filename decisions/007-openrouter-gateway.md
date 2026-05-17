# ADR 007: OpenRouter as primary LLM gateway

## Status
Accepted

## Context
The pipeline uses three models from two providers. Managing separate API keys and billing is operational overhead.

## Decision
Route all LLM calls through OpenRouter. ANTHROPIC_API_KEY kept as optional direct override for RAG responses.

## Consequences
Single API key and unified billing. Model swaps require one parameter change, no code changes.
