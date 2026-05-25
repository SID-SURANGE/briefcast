# RAG Eval Harness

> RAGAS-based evaluation of the Briefcast RAG pipeline.  
> 4 metrics · 20 grounded Q&A pairs · online mode (hits live Railway DB)

---

## Why an eval harness?

RAG quality is invisible without measurement. The eval harness answers three questions after every significant change:

1. **Is the model staying grounded?** — faithfulness catches hallucinations
2. **Is it answering what was asked?** — answer_relevancy catches tangents
3. **Is the retriever finding the right chunks?** — context_precision + context_recall

Running evals before and after changes (e.g. a new model, a new retrieval `k`, a new similarity threshold) makes regressions visible before they reach users.

---

## Metrics

All metrics score 0.0–1.0. Higher is better.

| Metric | What it measures | Reference-free? |
|---|---|---|
| `faithfulness` | Answer stays grounded in retrieved context — every claim traceable to a retrieved article | ✅ |
| `answer_relevancy` | Answer addresses the question asked — no tangents or off-topic content | ✅ |
| `context_precision` | Retrieved chunks are actually relevant to the ground truth answer | ❌ (needs ground truth) |
| `context_recall` | Retrieved context covers the key facts in the ground truth | ❌ (needs ground truth) |

**`faithfulness` and `answer_relevancy` are the primary signals** — they catch hallucination and relevance degradation without requiring a ground truth answer. `context_precision` and `context_recall` measure retriever quality but are more sensitive to stale ground truths.

---

## Architecture

```
questions.json  →  embed query  →  pgvector retrieve  →  Claude Sonnet generate
                                                              ↓
                                              RAGAS judge (Haiku + text-embedding-3-small)
                                                              ↓
                                              evals/reports/YYYY-MM-DD_HH-MM.json
```

### Key design choices

| Choice | Rationale |
|---|---|
| **Online mode** | Hits live Railway DB — evals reflect what real users experience |
| **Haiku as judge LLM** | Cheaper than Sonnet (~10x), sufficient for RAGAS scoring tasks |
| **text-embedding-3-small for answer_relevancy** | RAGAS embeds the generated answer to compare with question; needs an embedding model |
| **Corpus miss skipped** | Questions where no article clears the similarity gate (0.35) are logged but not scored — they'd penalise retrieval for a routing decision, not a RAG failure |
| **Same OpenRouter key** | No new API cost centre — reuses production credentials |

---

## Running evals

### Prerequisites

- `.env` with `DATABASE_URL` pointing at Railway Postgres (or local pgvector DB)
- Dev dependencies installed: `.venv\Scripts\pip install -e ".[dev]"`
- DB populated — run `python scripts/run_ingestion_once.py` first if the corpus is empty

### Commands

```powershell
# Smoke test — first 5 questions (fast, ~2-3 min)
.venv\Scripts\python scripts/run_evals.py --limit 5

# Full run — all 20 questions (~8-12 min)
.venv\Scripts\python scripts/run_evals.py

# Specific questions by ID
.venv\Scripts\python scripts/run_evals.py --ids q01,q05,q10

# Skip saving a report file
.venv\Scripts\python scripts/run_evals.py --no-report
```

### Output

Each run produces two outputs:

**1. Report file** — `evals/reports/YYYY-MM-DD_HH-MM.json`
```json
{
  "run_at": "2026-05-25T09:00:00Z",
  "questions_total": 20,
  "questions_scored": 17,
  "corpus_misses": 3,
  "elapsed_seconds": 540.2,
  "aggregate_scores": {
    "faithfulness": 0.87,
    "answer_relevancy": 0.91,
    "context_precision": 0.74,
    "context_recall": 0.68
  },
  "per_question": [...]
}
```

**2. Structured log lines** — picked up by `scripts/cost_report.py`
```
eval.aggregate_metrics  questions_total=20  questions_scored=17
                        ragas_faithfulness=0.87  ragas_answer_relevancy=0.91
                        ragas_context_precision=0.74  ragas_context_recall=0.68
```

---

## Question set — `evals/questions.json`

20 Q&A pairs covering the AI ecosystem topics in the corpus:

- Model releases (GPT-5.5, Gemini 3.5, Llama 4 Scout/Maverick, Claude 4)
- Infrastructure (Blackwell B200, CUDA updates)
- Frameworks (TRL v1.0, LangChain, RAGAS)
- Research (reasoning, safety, multimodal)

Each entry:
```json
{
  "id": "q01",
  "question": "What is GPT-5.5 and how does it differ from GPT-5?",
  "ground_truth": "GPT-5.5 is ...",
  "expected_sources": ["OpenAI"]
}
```

Ground truths reflect the **May 2026 model landscape** — update them after major ecosystem shifts to keep `context_precision` and `context_recall` scores meaningful.

---

## Interpreting results

| Score | What it means | Action |
|---|---|---|
| faithfulness < 0.75 | Model is hallucinating beyond retrieved context | Tighten system prompt; lower `max_tokens`; raise similarity gate |
| answer_relevancy < 0.80 | Answers drifting off-topic | Review system prompt instructions; check `k` retrieval count |
| context_precision < 0.65 | Retriever returning irrelevant chunks | Raise `DEDUP_THRESHOLD`; lower `k`; revisit tier filter |
| context_recall < 0.60 | Retriever missing key facts | Lower similarity gate; raise `k`; check ingestion coverage |
| corpus_miss_rate > 0.20 | Too many questions falling through to web fallback | Check ingestion health; question set may be ahead of corpus |

### When to re-run

- After changing `_MIN_SIMILARITY` (similarity gate in `responder.py`)
- After changing retrieval `k` in `retriever.py`
- After upgrading the generation model (Sonnet → new version)
- After a major corpus refresh (new source tier, new ingestion period)
- Weekly during active development

---

## Files

```
evals/
├── __init__.py          # package marker
├── questions.json       # 20 Q&A pairs with ground truths + expected sources
├── eval_runner.py       # RAGAS harness: retrieve → generate → score → save report
└── reports/             # generated JSON reports (gitignored)

scripts/
└── run_evals.py         # CLI entry point: --limit / --ids / --no-report flags
```
