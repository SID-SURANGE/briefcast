# ADR 006 · Three storage modes — summary, abstract, processed-discard

## Status
Accepted

## Context
Different source types have different legal and technical constraints on what can be stored.

## Decision
- Mode A (summary + metadata): default for all blog/news sources
- Mode B (abstract + metadata): arXiv only — full abstract is designed for discovery indexing
- Mode C (fetch → process → discard): permissive-licence PDFs only; raw text never written to DB

## Consequences
storage_mode field required on every Article. Source-level overrides documented in POLICY.md.
