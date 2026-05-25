"""
Run the RAGAS-based RAG evaluation harness.

Usage:
  python scripts/run_evals.py                      # all 20 questions
  python scripts/run_evals.py --limit 5            # first 5 (quick smoke test)
  python scripts/run_evals.py --ids q01,q05,q10    # specific question IDs
  python scripts/run_evals.py --limit 5 --no-report # skip saving JSON report

Prerequisites:
  DATABASE_URL       — Railway Postgres (or local Docker DB via .env)
  OPENROUTER_API_KEY — used for production LLM + RAGAS judge (Haiku)
  NOMIC_API_KEY      — used for embedding queries

Output:
  evals/reports/YYYY-MM-DD_HH-MM.json  — full report
  Structlog JSON lines → stdout (aggregate + per-question corpus-miss info)

Metrics (RAGAS industry standard):
  faithfulness       — does the answer stay grounded in retrieved context?
  answer_relevancy   — does the answer address the question?
  context_precision  — are the retrieved chunks relevant to the ground truth?
  context_recall     — does the retrieved context cover the key ground truth facts?

Score range: 0.0 (worst) → 1.0 (best)
Typical production targets:
  faithfulness      ≥ 0.85   (hallucination risk threshold)
  answer_relevancy  ≥ 0.80
  context_precision ≥ 0.70
  context_recall    ≥ 0.65   (harder — depends on corpus coverage)
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RAGAS RAG evaluation for Briefcast.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only evaluate the first N questions (default: all 20).",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated question IDs to evaluate, e.g. q01,q05,q10.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip saving the JSON report file (just print metrics).",
    )
    return parser.parse_args()


def _print_summary(report: dict) -> None:
    """Print a human-readable summary table to stdout."""
    agg = report.get("aggregate_scores", {})
    misses = report.get("corpus_misses", 0)
    total = report.get("questions_total", 0)
    scored = report.get("questions_scored", 0)
    elapsed = report.get("elapsed_seconds", 0)

    print("\n" + "=" * 60)
    print("  Briefcast RAG Evaluation — RAGAS Metrics")
    print("=" * 60)
    print(f"  Questions total   : {total}")
    print(f"  Questions scored  : {scored}")
    print(f"  Corpus misses     : {misses}  ({misses/max(total,1)*100:.0f}%)")
    print(f"  Elapsed           : {elapsed}s")
    print()

    metric_targets = {
        "faithfulness": 0.85,
        "answer_relevancy": 0.80,
        "context_precision": 0.70,
        "context_recall": 0.65,
    }

    if "error" in agg:
        print(f"  ⚠️  RAGAS error: {agg['error']}")
    elif not agg:
        print("  ⚠️  No questions scored (all corpus misses or empty result).")
    else:
        print(f"  {'Metric':<22} {'Score':>7}  {'Target':>7}  Status")
        print(f"  {'-'*50}")
        for metric, target in metric_targets.items():
            score = agg.get(metric, None)
            if score is None:
                print(f"  {metric:<22} {'N/A':>7}  {target:>7.2f}  –")
            else:
                status = "✅" if score >= target else "⚠️ "
                print(f"  {metric:<22} {score:>7.4f}  {target:>7.2f}  {status}")

    print()

    # Corpus-miss breakdown
    misses_list = [
        q for q in report.get("per_question", []) if q.get("corpus_miss")
    ]
    if misses_list:
        print("  Corpus-miss questions (not scored):")
        for q in misses_list:
            print(f"    [{q['id']}] {q['question'][:65]}")
        print()

    print("=" * 60)


def main() -> None:
    args = _parse_args()

    ids: list[str] | None = None
    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]

    # Import here so env is loaded first
    from evals.eval_runner import evaluate_sync  # noqa: PLC0415

    print(f"Running RAGAS evaluation — limit={args.limit}, ids={ids or 'all'}")
    report = evaluate_sync(ids=ids, limit=args.limit)

    _print_summary(report)

    if args.no_report:
        # Remove the saved report (eval_runner always saves one)
        from pathlib import Path as _Path
        import glob
        reports = sorted(
            glob.glob(str(_Path(__file__).parent.parent / "evals" / "reports" / "*.json"))
        )
        if reports:
            _Path(reports[-1]).unlink(missing_ok=True)
        print("  (report file not saved — --no-report flag set)")
    else:
        from datetime import datetime, timezone
        ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M")
        print(f"  Report saved → evals/reports/{ts}.json")


if __name__ == "__main__":
    main()
