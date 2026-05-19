# Briefcast — System Design FAQ

**Audience:** Claude Architect Certification prep · design review · portfolio defence
**Last updated:** 2026-05-19

---

## 1. Ingestion & Chunking

**Q: Traditional RAG chunking splits long documents into 800-token pieces. Where does chunking happen in Briefcast?**

It largely doesn't — and that's intentional. The pipeline stores generated summaries (3–5 sentences, ~100–150 tokens) or arXiv abstracts (~200 tokens). The summary *is* the chunk. Because no full article body is ever stored, there is nothing to split. The `RecursiveCharacterTextSplitter(chunk_size=800, overlap=100)` in the tech stack is reserved for Mode C (fetch → process → discard) if a permissive-licence PDF is ever processed. In v1 that path is never triggered.

**Q: Does storing only summaries hurt retrieval quality compared to storing full text?**

For this use case, no — and arguably it improves it. A dense 3-sentence summary eliminates noise, boosts semantic signal per token, and produces a tighter embedding than a 2,000-word article would. The trade-off is that fine-grained keyword retrieval suffers: if a user asks about a specific number or quoted phrase from an article, the summary may not contain it. This is why hybrid BM25 is on the v1.5 roadmap — add BM25 once you have evidence that vector recall is the bottleneck.

**Q: arXiv articles store the raw abstract (Mode B) while blog posts store a generated summary (Mode A). Does this create embedding space inconsistency?**

Slightly, yes. Abstracts tend toward formal academic register; generated summaries are written in a consistent plain-English voice. In practice the embedding model (`nomic-embed-text-v1.5`) is robust enough to handle both registers in the same vector space. If retrieval eval shows arXiv results clustering away from blog results on semantically similar queries, the fix is to summarise arXiv abstracts through the same Gemini Flash pipeline rather than storing raw abstracts.

---

## 2. Deduplication

**Q: Why two layers — URL hash first, then cosine similarity?**

Each layer catches what the other misses at a different cost point.

- **L1 (SHA-256 of URL):** O(1), zero API cost. Catches exact re-fetches of the same article across ingestion cycles.
- **L2 (cosine similarity of title embedding vs 500 most-recent stored embeddings):** Catches the same story covered by two different sources — OpenAI posts something, then three tech blogs restate it with different URLs. Without L2, the briefing fills with semantic duplicates.

Doing L2 first would waste an embed API call on every article, including ones already in the DB by URL.

**Q: Why compare the incoming *title* embedding against stored *summary* embeddings in L2?**

This is a deliberate approximation. At dedup time, the summary doesn't exist yet — it costs an API call to generate. Comparing title-to-summary catches near-duplicates well enough because titles carry the core semantic content. If two titles are >0.92 cosine similar, they are almost certainly covering the same story. The alternative — generating the summary first, then checking — would pay for a summarisation that gets discarded, wasting ~$0.001 per duplicate.

**Q: Why DEDUP_THRESHOLD = 0.92? What breaks at 0.85 or 0.95?**

At **0.85**: too aggressive. Legitimate distinct stories (e.g. "Gemini 2.5 released" vs "Gemini 2.5 benchmark results") share enough semantic content to collide, silently dropping articles that should appear.

At **0.95**: too permissive. Near-paraphrase duplicates from syndicated sources make it through, diluting the briefing with repeated stories.

0.92 was chosen as a conservative starting point. The correct value should be calibrated against a labelled set of 50–100 duplicate/non-duplicate pairs — this is the first eval task at v1.5.

---

## 3. Ranking

**Q: The ranking formula is `tier×0.35 + recency×0.35 + novelty×0.30`. How were these weights chosen?**

By priority ordering, not optimisation. The three signals are intentionally equal-weighted between tier and recency (0.35 each) because both are load-bearing: a Tier 1 article from 13 days ago should not beat a fresh Tier 2 breakthrough. Novelty gets slightly less (0.30) because it is the noisiest signal — pairwise cosine similarity across a corpus of 100+ articles is a rough proxy for uniqueness. These weights should be treated as a starting point to be tuned against a labelled relevance set once the pipeline has two weeks of real data.

**Q: How is novelty computed, and what is its computational cost?**

```
novelty[i] = 1 - max(cosine_similarity(embedding[i], embedding[j])) for all j ≠ i
```

This is O(n²) in the number of articles. At the 14-day rolling window typical size (~200–500 articles), this is fast in NumPy (< 1 second). It becomes a concern above ~5,000 articles — at that scale, switch to approximate nearest neighbour (FAISS/ScaNN) or sample the comparison set.

**Q: Ranking runs after every ingestion cycle. The diversity cap in `_select()` runs at briefing time. Do these two systems conflict?**

They operate at different layers — ranking is a global score, selection is a slot allocation. A conflict scenario: Google has 6 articles, all scoring above 0.8. The ranker correctly scores them highest. The `_select()` cap then enforces that only 4 of them enter the briefing, and the 5th slot goes to the highest-scored non-Google article. This is the desired behaviour — ranking determines *which* Google articles win their slots, not *whether* Google dominates entirely.

**Q: Why isn't the ranking score used as a retrieval signal in RAG?**

The ranking score is a *freshness + provenance* signal, not a *query relevance* signal. For RAG, what matters is semantic distance between the query embedding and the article embedding. A highly ranked article (Tier 1, just published, unique) that is semantically irrelevant to the user's query should not appear in retrieval results. The two systems serve orthogonal goals.

---

## 4. Model Selection

**Q: Why Gemini Flash for summarisation and not Claude Haiku — Haiku is already in the stack?**

Cost and hallucination profile at scale. Summarisation runs on every ingested article — potentially 50–200 calls per day. Gemini Flash at ~$0.10/M input tokens is 10× cheaper than Haiku at ~$1/M. More importantly, on extractive summarisation tasks (compress a real article into 3 accurate sentences), Gemini Flash's hallucination rate is lower than Haiku's. The output is a factual précis, not a creative composition — Gemini Flash is better suited.

**Q: Why Haiku for briefing composition instead of Gemini Flash?**

The briefing is the user-facing product — it is read daily and its tone shapes the product's personality. In blind writing quality evaluations, Claude output is preferred ~47% of the time vs Gemini's ~24%. Haiku is the cheapest Claude model. The cost delta vs Gemini Flash is ~$0.001/day at this usage volume — negligible. Writing quality is not interchangeable here.

**Q: Why Sonnet for RAG responses and not Haiku?**

RAG responses carry the highest hallucination risk in the system. The model must synthesise across multiple retrieved articles, attribute claims to specific sources, and decline to answer when evidence is insufficient. Haiku is prone to over-generating on low-evidence queries — producing confident-sounding answers that go beyond what the retrieved documents support. Sonnet's instruction-following on citation and grounding constraints is materially stronger. The higher cost (~$3/M vs $1/M) is justified because RAG is user-interactive, not batch.

**Q: Could you run the entire pipeline on a single model to simplify ops?**

Yes, technically. Using Gemini Flash everywhere cuts cost to ~$0.50/month. The real cost is quality degradation at the briefing and RAG layers where writing quality and grounding precision matter. The three-model split maps each task to its cost-quality optimum. OpenRouter makes this zero-ops — it's one API key regardless of how many models are in use.

---

## 5. Retrieval

**Q: Why cosine distance and not dot product or Euclidean (L2)?**

`nomic-embed-text-v1.5` embeddings are not normalised to unit length. Dot product is magnitude-sensitive — a longer document's embedding (higher magnitude) would score higher on dot product regardless of semantic relevance. Cosine distance normalises by magnitude, making it a pure angular similarity measure. L2 distance penalises both angular difference and magnitude difference, making it unsuitable for semantic search. Cosine is the correct choice for variable-length text embeddings.

**Q: Why k=10 retrieval? What's the failure mode if you use k=3 or k=20?**

**k=3:** Insufficient context for multi-source synthesis. If the three retrieved articles are all from one source or cover only one angle of a broad question, the generated answer will be narrow and miss relevant coverage from other sources in the corpus.

**k=20:** You hit Sonnet's context window budget faster, and the signal-to-noise ratio in the retrieved set drops. Articles 11–20 ranked by cosine similarity are often only marginally relevant. Feeding them to the LLM increases the risk of tangential content diluting the answer.

k=10 is the standard starting point for RAG systems of this corpus size. Calibrate against retrieval recall@k once you have labelled QA pairs.

**Q: Why a 14-day rolling window for both retrieval and ranking? Why not 30 days or 7 days?**

14 days is the minimum corpus depth that makes the RAG useful for follow-up questions on stories that broke over a weekend or evolved over a week. At 7 days, a story published 8 days ago becomes unretrievable even if it's still the most important development of the month. At 30 days, the corpus grows to ~1,000+ articles and cosine distance loses precision as the vector space becomes crowded with older, lower-relevance content. 14 days also aligns with Briefcast's "AI moves fast" premise — anything older than two weeks is background knowledge, not current intelligence.

**Q: What happens when a user asks about something with no relevant documents in the 14-day corpus?**

The retriever returns its top-k by cosine distance regardless — it has no "minimum relevance" floor. The responder's system prompt must instruct the model to declare when retrieved documents do not support the query. Without this instruction, the LLM will hallucinate an answer from training data. This is a prompt engineering responsibility, not a retrieval responsibility — citations are mandatory so the user can verify what was and wasn't actually in the corpus.

---

## 6. Generation & Prompting

**Q: Why temperature=0.4 for briefing composition? Why not 0.0 for full determinism?**

Briefing composition is a formatting and writing task, not a factual recall task. At 0.0, the model becomes repetitive across consecutive days — identical sentence structures, same transitional phrases, predictable tonal patterns. A small temperature (0.3–0.5) maintains writing variety without introducing hallucination risk. The facts come from the user prompt (article titles, summaries, URLs); the model's creative latitude is only over prose style.

**Q: Citations are "mandatory" — how is this technically enforced beyond the system prompt instruction?**

In v1, it isn't — the instruction is behavioural, not structural. If Sonnet generates an answer without citations, the system won't catch it. The correct enforcement mechanism (on the v1.5 roadmap) is output validation: parse the response for `<a href>` tags and fall back to a retry or a "no answer" response if none are found. This is a known gap — the system trusts the model's instruction-following, which Sonnet is strong but not perfect at.

**Q: The system prompt is hardcoded as a Python string. When should it move to a file or database?**

When any of these are true: (a) non-engineers need to edit prompts, (b) you want to A/B test prompt variants, (c) you want version history separate from code deploys. In v1 with a single developer, inline strings are the right call — they are co-located with the code that uses them, visible in git history, and don't require a lookup at runtime. Externalising prompts prematurely adds an infrastructure dependency without adding value.

---

## 7. Architecture & Reliability

**Q: Why APScheduler (in-process) over a dedicated job queue like Celery or Redis Queue?**

At this scale (two cron jobs, one user), a separate queue service (Celery + Redis or equivalent) adds ~$10–15/month in Railway services, a separate worker process, and a broker to operate. APScheduler runs in the same Python process as the worker, costs nothing, and is sufficient for jobs that run every 6 hours and once daily. The right trigger to migrate to a proper queue: jobs start running longer than 10 minutes or the need arises to run the same job across multiple concurrent workers.

**Q: The circuit breaker trips a source to `degraded` after 3 consecutive failures. Why 3?**

1 failure is too sensitive — a transient 503 or network blip trips a healthy source. 5 failures means a broken source poisons 5 ingestion cycles (30 hours) before alerting. 3 is the minimum that filters transients without accumulating significant lag. The Telegram alert fires immediately on the third failure, so manual recovery can begin within minutes of a real outage.

**Q: Why are the API service and Worker service deployed as two separate Railway services?**

Separation of failure domains. If the worker OOMs on a large ingestion cycle (embedding 200 articles sequentially), the FastAPI webhook handler — which handles incoming Telegram messages — stays alive. If they shared a process, a runaway worker job would make the bot unresponsive. The two services also have different scaling profiles: the API needs low-latency always-on availability; the worker needs burst memory during ingestion cycles.

**Q: LangChain is in the dependencies — where is it actually used?**

Only in `app/rag/responder.py`. The RAG query path is implemented as a LangChain LCEL chain (`_prompt | _llm | StrOutputParser()`), which gives automatic LangSmith tracing of the full prompt → generation step. Everything else — summarisation, briefing composition, embedding — uses raw `httpx`. LangChain would add abstraction overhead to batch jobs (summariser runs 50–200 times per ingestion cycle) without adding any value over a direct API call. The LCEL chain is justified only where per-query trace visibility matters: seeing exactly what context was retrieved and fed to the model for a given user question.

**Q: Why not LangGraph in v1?**

LangGraph is justified when the pipeline has *real* conditional branching that requires a stateful graph — for example: query → classify intent → if retrieval-needed branch to RAG else branch to direct LLM → validate citation quality → if low quality retry with different retrieval. In v1, every path is linear and deterministic: embed → retrieve → generate. Adding LangGraph would add a dependency, a learning curve, and graph state management overhead for zero architectural benefit. It becomes the right tool when the query agent needs a validator node and retry loop.

---

## Quick Reference: Key Numbers

| Parameter | Value | Where set |
|---|---|---|
| Dedup threshold | 0.92 | `DEDUP_THRESHOLD` env var |
| L2 dedup comparison window | 500 most-recent articles | `app/ingestion/dedup.py:44` |
| Ranking weights | tier 0.35 · recency 0.35 · novelty 0.30 | `app/ranking/ranker.py:20` |
| Recency decay window | 14 days → score 0.0 | `app/ranking/ranker.py:10` |
| RAG retrieval k | 10 | `app/rag/retriever.py:14` |
| RAG window | 14 days | `app/rag/retriever.py:11` |
| Briefing items | max 10 · max 4 Google · max 2 others | `app/briefing/composer.py` |
| Briefing max_tokens | 2,000 | `app/briefing/composer.py` |
| Telegram hard limit | 4,096 chars | `app/delivery/telegram_bot.py` |
| Ingestion schedule | every 6h | `app/worker.py:250` |
| Briefing schedule | 03:30 UTC (09:00 IST) | `app/worker.py:251` |
