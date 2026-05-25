"""
RAG evaluation harness using RAGAS.

Industry-standard metrics:
  faithfulness       — answer stays grounded in retrieved context (hallucination check)
  answer_relevancy   — answer addresses the question asked (no tangents)
  context_precision  — retrieved chunks actually relevant to ground truth
  context_recall     — retrieved context covers key facts in ground truth

Usage (via scripts/run_evals.py):
  python scripts/run_evals.py                     # all 20 questions, online mode
  python scripts/run_evals.py --limit 5           # first 5 questions
  python scripts/run_evals.py --ids q01,q05,q10   # specific question IDs

Output:
  evals/reports/YYYY-MM-DD_HH-MM.json  — full per-question results
  structlog lines with aggregate metrics (picked up by cost_report.py)

Notes:
  - Online mode hits live Railway DB — set DATABASE_URL in .env
  - RAGAS uses OpenRouter/Sonnet as the judge LLM (same API key, no new cost centre)
  - Questions with no corpus articles (all corpus-miss) are logged but not scored
  - faithfulness + answer_relevancy are reference-free; precision/recall use ground_truth
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from datasets import Dataset
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI as _ChatOpenAI, OpenAIEmbeddings as _OAIEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from app.config import settings
from app.db import SessionLocal
from app.observability.logger import configure_logging
from app.processing.embedder import embed
from app.rag.responder import _CACHED_SYSTEM_MESSAGE, _build_corpus_context, _has_relevant_results, _llm
from app.rag.retriever import retrieve

configure_logging()
log = structlog.get_logger(__name__)

# ── paths ────────────────────────────────────────────────────────────────────
_EVALS_DIR = Path(__file__).parent
_QUESTIONS_PATH = _EVALS_DIR / "questions.json"
_REPORTS_DIR = _EVALS_DIR / "reports"
_REPORTS_DIR.mkdir(exist_ok=True)

# ── RAGAS judge LLM + embeddings (OpenRouter — same key as production) ───────
# RAGAS 0.2.x: inject LangchainLLMWrapper and LangchainEmbeddingsWrapper into
# each metric before calling evaluate().  We use Haiku as judge (cheap, sufficient
# for scoring) and text-embedding-3-small via OpenRouter for answer_relevancy.

_judge_llm = LangchainLLMWrapper(
    _ChatOpenAI(
        model="anthropic/claude-haiku-4-5",  # Haiku for eval judge — cheaper than Sonnet
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        max_tokens=1024,
        temperature=0.0,
        default_headers={
            "HTTP-Referer": settings.openrouter_app_referer,
        },
    )
)

# RAGAS needs embeddings for answer_relevancy (embeds the generated answer to compare
# with question).  text-embedding-3-small via OpenRouter is cheap and fast.
_judge_embeddings = LangchainEmbeddingsWrapper(
    _OAIEmbeddings(
        model="openai/text-embedding-3-small",
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
    )
)


# ── question loading ──────────────────────────────────────────────────────────

def load_questions(
    path: Path = _QUESTIONS_PATH,
    ids: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Load Q&A pairs from questions.json, optionally filtered by IDs or count."""
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)

    if ids:
        questions = [q for q in questions if q["id"] in ids]

    if limit:
        questions = questions[:limit]

    log.info("eval.questions_loaded", count=len(questions))
    return questions


# ── retrieval + generation ────────────────────────────────────────────────────

async def _retrieve_and_generate(question: str) -> dict[str, Any]:
    """
    Run the RAG pipeline for a single question.
    Returns: answer, contexts (list[str]), used_web_search, retrieved_count.
    """
    # Embed
    query_embedding = await embed(question, task_type="search_query")

    # Retrieve
    db = SessionLocal()
    try:
        articles = retrieve(query_embedding, db)
    finally:
        db.close()

    # Route
    if not _has_relevant_results(articles):
        log.info(
            "eval.corpus_miss",
            question=question[:60],
            best_similarity=articles[0]["similarity"] if articles else 0.0,
        )
        return {
            "answer": None,
            "contexts": [],
            "used_web_search": False,
            "retrieved_count": len(articles),
            "corpus_miss": True,
        }

    context_block = _build_corpus_context(articles)
    contexts = [
        f"{a['source_name']} — {a['title']}\n{a['summary']}"
        for a in articles
    ]

    messages = [
        _CACHED_SYSTEM_MESSAGE,
        HumanMessage(content=f"Context:\n{context_block}\n\nQuestion: {question}"),
    ]

    ai_message = await _llm.ainvoke(messages)
    answer: str = ai_message.content

    return {
        "answer": answer,
        "contexts": contexts,
        "used_web_search": False,
        "retrieved_count": len(articles),
        "corpus_miss": False,
    }


# ── RAGAS evaluation ──────────────────────────────────────────────────────────

def _run_ragas(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
) -> dict[str, float]:
    """
    Run RAGAS on a batch of Q/A/context/ground_truth tuples.
    Returns dict of metric_name → mean score (0.0–1.0).

    Metrics:
      faithfulness       — grounding check (no hallucination); uses LLM
      answer_relevancy   — does answer address the question; uses LLM + embeddings
      context_precision  — retrieved chunks relevant to ground truth; uses LLM
      context_recall     — retrieved context covers ground truth facts; uses LLM
    """
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

    # RAGAS 0.2.x: inject judge LLM and embeddings into the singleton metric objects.
    # answer_relevancy also needs embeddings to compute question↔answer similarity.
    for m in metrics:
        m.llm = _judge_llm
        if hasattr(m, "embeddings"):
            m.embeddings = _judge_embeddings

    result = evaluate(dataset, metrics=metrics, raise_exceptions=False)
    # result is a dict-like EvaluationResult; convert to plain floats
    return {k: round(float(v), 4) for k, v in result.items() if isinstance(v, (int, float))}


# ── main eval orchestrator ────────────────────────────────────────────────────

async def run_evaluation(
    ids: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Full eval pipeline:
      1. Load questions
      2. For each: retrieve + generate (online mode)
      3. Collect scoreable rows (skip corpus misses)
      4. Run RAGAS batch
      5. Save JSON report + log aggregate metrics

    Returns the full report dict.
    """
    t_start = time.monotonic()
    questions = load_questions(ids=ids, limit=limit)

    scoreable_questions: list[str] = []
    scoreable_answers: list[str] = []
    scoreable_contexts: list[list[str]] = []
    scoreable_ground_truths: list[str] = []
    per_question_results: list[dict[str, Any]] = []

    for q in questions:
        log.info("eval.running_question", id=q["id"], question=q["question"][:70])
        result = await _retrieve_and_generate(q["question"])

        row: dict[str, Any] = {
            "id": q["id"],
            "question": q["question"],
            "ground_truth": q["ground_truth"],
            "expected_sources": q.get("expected_sources", []),
            "corpus_miss": result["corpus_miss"],
            "retrieved_count": result["retrieved_count"],
            "used_web_search": result["used_web_search"],
            "answer": result["answer"],
            "contexts": result["contexts"],
            "ragas_scores": None,
        }
        per_question_results.append(row)

        if not result["corpus_miss"] and result["answer"]:
            scoreable_questions.append(q["question"])
            scoreable_answers.append(result["answer"])
            scoreable_contexts.append(result["contexts"])
            scoreable_ground_truths.append(q["ground_truth"])

    log.info(
        "eval.ragas_start",
        total=len(questions),
        scoreable=len(scoreable_questions),
        corpus_misses=len(questions) - len(scoreable_questions),
    )

    aggregate_scores: dict[str, float] = {}
    if scoreable_questions:
        try:
            aggregate_scores = _run_ragas(
                scoreable_questions,
                scoreable_answers,
                scoreable_contexts,
                scoreable_ground_truths,
            )
        except Exception as exc:
            log.error("eval.ragas_error", error=str(exc))
            aggregate_scores = {"error": str(exc)}

    elapsed_s = round(time.monotonic() - t_start, 1)

    report = {
        "run_at": datetime.now(tz=timezone.utc).isoformat(),
        "questions_total": len(questions),
        "questions_scored": len(scoreable_questions),
        "corpus_misses": len(questions) - len(scoreable_questions),
        "elapsed_seconds": elapsed_s,
        "aggregate_scores": aggregate_scores,
        "per_question": per_question_results,
    }

    # Save report
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M")
    report_path = _REPORTS_DIR / f"{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log.info("eval.report_saved", path=str(report_path))

    # Log aggregate metrics (picked up by cost_report.py)
    log.info(
        "eval.aggregate_metrics",
        questions_total=len(questions),
        questions_scored=len(scoreable_questions),
        corpus_miss_rate=round(
            (len(questions) - len(scoreable_questions)) / max(len(questions), 1), 3
        ),
        elapsed_seconds=elapsed_s,
        **{f"ragas_{k}": round(v, 4) for k, v in aggregate_scores.items()
           if isinstance(v, float)},
    )

    return report


def evaluate_sync(
    ids: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Synchronous wrapper around run_evaluation for use from scripts."""
    return asyncio.run(run_evaluation(ids=ids, limit=limit))
