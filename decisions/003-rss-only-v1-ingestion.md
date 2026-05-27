# ADR 003 · RSS/API-only ingestion in v1

## Status
Accepted

## Context
Sources could be ingested via RSS/official APIs or HTML scraping.

## Decision
RSS and official public APIs only. No HTML scraping in any version.

## Consequences
Legal clarity. Feed stability enforces curation discipline.
Any source without a stable feed is excluded until one exists.
