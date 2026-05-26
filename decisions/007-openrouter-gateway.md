# ADR 007 · OpenRouter as sole LLM gateway

## Status
Accepted

## Context
The pipeline uses three models: Gemini Flash (summarisation), Claude Haiku (briefing), Claude Sonnet (RAG).
Managing separate API keys per provider adds billing and platform overhead for a personal tool.

## Decision
Route all LLM calls through OpenRouter with a single `OPENROUTER_API_KEY`.
No direct Anthropic API key — OpenRouter already provides access to Claude Sonnet.

## Consequences
Single API key, single billing account, unified model access.
Model swaps require one parameter change, no code changes.
Estimated LLM cost: ~$2–3/month at personal use volume.
