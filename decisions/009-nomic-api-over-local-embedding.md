# ADR 009 · Nomic API over local embedding model in v1

## Status
Accepted

## Context
nomic-embed-text-v1.5 can run locally via sentence-transformers or via Nomic's free API.
Railway Hobby worker service has limited RAM; loading torch (~1.5GB) causes OOM risk.

## Decision
Use Nomic API (free tier, 1M tokens/month) in v1. Local embedding is the v2 upgrade path.

## Consequences
No torch dependency in the worker. Same model, free tier, simpler ops.
Switching to local in v2 requires changing only app/processing/embedder.py.
