from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.source import Source


class SourceDefinition(BaseModel):
    name: str
    feed_url: str
    feed_type: str          # "rss" | "arxiv_api"
    tier: int
    classification: str     # "verified-official" | "verify-before-enabling" | "optional-connector" | "excluded"
    storage_mode: str       # "summary_metadata" | "abstract_metadata" | "processed_discard"


# Single source of truth for all registered sources.
# Add new sources here; sync_sources() propagates them to the DB.
SOURCES: list[SourceDefinition] = [
    # ── Google AI Family (all active sources — see ADR 016) ──────────────
    SourceDefinition(
        name="Google AI Blog",
        feed_url="https://blog.google/technology/ai/rss/",
        feed_type="rss", tier=1,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
    SourceDefinition(
        name="Google Research Blog",
        feed_url="https://research.google/blog/rss/",
        feed_type="rss", tier=1,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
    SourceDefinition(
        name="Google Cloud AI Blog",
        feed_url="https://cloudblog.withgoogle.com/rss/",
        feed_type="rss", tier=1,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
    SourceDefinition(
        name="Google DeepMind Blog",
        feed_url="https://deepmind.google/blog/rss.xml",
        feed_type="rss", tier=1,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
    # Non-Google sources (OpenAI, Hugging Face, Meta, arXiv, Microsoft, NVIDIA)
    # were removed in ADR 016 — Briefcast is now Google-family-only by design,
    # not because those feeds went dead. See decisions/016-google-only-sources.md.
]

# Definition-only fields — runtime state columns are never overwritten by a sync
_DEFINITION_FIELDS = {"name", "feed_url", "feed_type", "tier", "classification", "storage_mode"}


def sync_sources(db: Session) -> tuple[int, int, int]:
    """Upsert SOURCES registry into the sources table.

    Only definition fields are written; runtime state (circuit_breaker_state,
    consecutive_failures, last_fetched_at) is left untouched on existing rows.
    Any existing active source whose name is no longer in SOURCES is soft-deleted
    (deleted_at set) rather than left behind to keep being fetched — the registry
    is the single source of truth for what's active, removals included.
    Returns (inserted, updated, soft_deleted).
    """
    inserted = updated = soft_deleted = 0
    registry_names = {defn.name for defn in SOURCES}

    for defn in SOURCES:
        row = db.query(Source).filter_by(name=defn.name).first()
        if row is None:
            row = Source(**defn.model_dump())
            db.add(row)
            inserted += 1
        else:
            for field in _DEFINITION_FIELDS:
                setattr(row, field, getattr(defn, field))
            updated += 1

    stale_rows = (
        db.query(Source)
        .filter(Source.deleted_at.is_(None), ~Source.name.in_(registry_names))
        .all()
    )
    for row in stale_rows:
        row.deleted_at = datetime.now(tz=timezone.utc)
        soft_deleted += 1

    db.commit()
    return inserted, updated, soft_deleted
