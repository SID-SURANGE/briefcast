# ADR 011: Single-path query UX — remove /ask and /chat commands

## Status
Accepted — 2026-05-25

## Context
The original bot exposed three query paths:

| Command | Behaviour |
|---|---|
| plain message | Corpus first → Tavily web search fallback on miss |
| `/ask <query>` | Corpus only, no web fallback |
| `/chat <message>` | Direct LLM (Haiku), no retrieval at all |

This created a mental model burden: users had to know which command to use before
they knew what the system would find. In practice:

- `/ask` was a subset of the plain message path with no UX advantage — users who
  wanted corpus-only were a hypothetical case, not an observed one.
- `/chat` bypassed retrieval entirely and returned LLM training-knowledge answers,
  which contradict the product's core promise of grounded, cited responses.
- The Tavily web fallback was broken for non-AI topics because the corpus system
  prompt declared itself an "AI research assistant" and rejected Reliance Industries
  financial news as "off-topic" even when Tavily returned valid results.

## Decision
Remove `/ask` and `/chat`. All Telegram messages route through a single path:

```
User types anything
  ↓
embed query → pgvector cosine search (14-day corpus)
  ↓ hit (similarity ≥ 0.35)        ↓ miss
Sonnet answers from corpus      Tavily search → LLM answers from web results
(citations to ingested articles)  (⚡ web disclaimer appended)
```

Additionally, split the monolithic system prompt into two variants:
- `_SYSTEM_PROMPT_CORPUS` — AI-scoped, cached (ephemeral, 5-min TTL)
- `_SYSTEM_PROMPT_WEB` — topic-agnostic, not cached (Tavily results can be anything)

The corpus prompt is used on corpus hits. The web prompt is used when Tavily fires,
removing the false "off-topic" rejection for non-AI queries.

## Consequences
- Zero commands to remember. Users just type.
- The `/help` command remains to explain the routing behaviour.
- `corpus_only` parameter removed from `respond()` — the distinction no longer
  has a user-facing trigger.
- `chat_responder.py` stays in the codebase (not deleted) but is no longer wired
  to any Telegram handler. It is available for future programmatic use.
- Tavily web search now correctly answers any topic, not just AI topics.
- The "off-topic" LLM rejection bug is fixed as a side effect of the prompt split.

## Rejected alternatives

**Keep /ask for power users:** No evidence of demand. Plain message already does
everything /ask does plus more. Adding back /ask would reintroduce the UX split
without a clear benefit.

**Keep /chat for open-ended conversation:** Direct LLM answers without citations
contradict the product's trust model. If a user wants general LLM conversation,
they have Claude.ai, ChatGPT, etc. Briefcast's value is grounded answers from
a curated AI news corpus — /chat undermined that positioning.
