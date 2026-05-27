# ADR 001 · pgvector over a dedicated vector database

## Status
Accepted

## Context
The pipeline needs vector similarity search for deduplication and RAG retrieval.
Options considered: Pinecone, Weaviate, Qdrant, pgvector in Postgres.

## Decision
Use pgvector as a Postgres extension alongside the main relational data.

## Consequences
Single DB — metadata filters and vector search in one SQL query.
No separate vector service to operate or pay for at <1M vectors.
Migration to a dedicated vector DB is possible later without changing the retrieval interface.
