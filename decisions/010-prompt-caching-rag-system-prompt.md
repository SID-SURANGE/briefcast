# ADR 010: Prompt caching for RAG system prompt via Anthropic ephemeral cache

## Status
Accepted

## Context
Every RAG query sent to Claude Sonnet via OpenRouter includes the same static system prompt
(~150 tokens) plus a variable context block of up to 10 retrieved articles (~1,200–1,500 tokens).
Without caching, the full input token count is billed at $3.00/M on every query.

The system prompt never changes between queries — it is a fixed set of behavioural rules
(citation format, answer length, output format, hallucination guard). It is therefore a
perfect candidate for Anthropic's prompt caching API, which stores a marked prefix server-side
and returns it at a fraction of the input cost on subsequent requests.

Anthropic's pricing for cached tokens (as of May 2026):
- Cache write: $3.75/M tokens (~25% premium over normal input, paid once per 5-min TTL window)
- Cache read: $0.30/M tokens (~90% reduction vs normal input)
- Normal input: $3.00/M tokens

At ~150 system prompt tokens per query, the saving per cache-hit query is:
  (3.00 − 0.30) / 1,000,000 × 150 ≈ $0.000405 per query

Small per query, but the system prompt is always present — every cache hit captures the full saving.

## Decision
Mark the static system prompt with `cache_control: {"type": "ephemeral"}` in the LangChain
`SystemMessage` content array. Pass the `anthropic-beta: prompt-caching-2024-07-31` header
via OpenRouter to opt into the caching API.

Swap `ChatPromptTemplate` string interpolation for direct `SystemMessage` / `HumanMessage`
construction. `ChatPromptTemplate` cannot attach `cache_control` to a message's content array —
it only interpolates strings. Direct message construction is equivalent and LangSmith tracing
is unaffected (`_llm.ainvoke(messages)` on a LangChain LLM is traced identically to
`(_prompt | _llm).ainvoke(...)`).

Cache TTL is 5 minutes (Anthropic platform default for ephemeral cache). Any two RAG queries
within a 5-minute window share the same cache entry and both get the read price.

Track cache token usage separately in cost logging:
- `cache_read_tokens` billed at $0.30/M
- `cache_write_tokens` billed at $3.75/M
- Remaining `input_tokens` billed at $3.00/M
- `output_tokens` billed at $15.00/M

Both `cache_read_tokens` and `cache_write_tokens` are surfaced in the `responder.done`
structured log line so cache effectiveness is visible without opening LangSmith.

## Consequences
- RAG query cost drops ~90% on the system prompt portion for any query within the 5-min TTL window.
- First query in each 5-min window pays the 25% write premium — break-even vs uncached is
  at 2 queries per window (write cost < 2× normal input cost).
- The variable context block (retrieved articles) is not cached — it changes every query.
  Caching it would require a fixed context, which defeats the purpose of retrieval.
- `ChatPromptTemplate` is removed from `responder.py`. The `langchain_core.prompts` import
  is replaced by `langchain_core.messages`. LCEL pipe syntax (`|`) is no longer used in this
  file; `_llm.ainvoke()` is called directly. This is not a regression — LangSmith traces
  `ainvoke` calls on LangChain LLMs identically.
- If the model or system prompt changes, the cache is invalidated automatically (different
  content = different cache key). No manual invalidation needed.
- This pattern should be applied to the briefing composer (Haiku) in v1.5 if query volume grows.
