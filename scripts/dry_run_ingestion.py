"""Dry-run: prints the ingestion plan for all registered sources.

No network requests are made and no DB writes occur.
Use this to audit the source registry before enabling live fetches.

Usage:
    python scripts/dry_run_ingestion.py
"""
from app.ingestion.registry import SOURCES, SourceDefinition

_STATUS_LABELS = {
    "verified-official": "READY — confirmed feed, safe to enable",
    "verify-before-enabling": "HOLD — test feed URL live before enabling",
    "optional-connector": "DISABLED — requires user-supplied credentials",
    "excluded": "EXCLUDED — do not ingest",
}

_TIER_LABELS = {1: "Tier 1 · Google AI family", 2: "Tier 2 · Major AI labs", 3: "Tier 3 · Open-weight labs"}


def _describe(src: SourceDefinition) -> None:
    tier_label = _TIER_LABELS.get(src.tier, f"Tier {src.tier}")
    status = _STATUS_LABELS.get(src.classification, src.classification)
    print(f"  [{tier_label}] {src.name}")
    print(f"    feed_url   : {src.feed_url}")
    print(f"    feed_type  : {src.feed_type}")
    print(f"    storage    : {src.storage_mode}")
    print(f"    status     : {status}")
    print()


def main() -> None:
    print("Briefcast — ingestion dry-run")
    print("=" * 40)
    print(f"Registered sources : {len(SOURCES)}")
    ready = sum(1 for s in SOURCES if s.classification == "verified-official")
    print(f"Ready to fetch     : {ready}")
    print(f"Pending verify     : {len(SOURCES) - ready}")
    print()

    for src in SOURCES:
        _describe(src)

    print("No network requests were made.")
    print("Run `alembic upgrade head` then call sync_sources(db) to seed the DB.")


if __name__ == "__main__":
    main()
