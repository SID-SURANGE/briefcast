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
    SourceDefinition(
        name="Google AI Blog",
        feed_url="https://blog.google/technology/ai/rss/",
        feed_type="rss",
        tier=1,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
]

# Definition-only fields — runtime state columns are never overwritten by a sync
_DEFINITION_FIELDS = {"name", "feed_url", "feed_type", "tier", "classification", "storage_mode"}


def sync_sources(db: Session) -> list[Source]:
    """Upsert SOURCES registry into the sources table.

    Only definition fields are written; runtime state (circuit_breaker_state,
    consecutive_failures, last_fetched_at) is left untouched on existing rows.
    """
    synced: list[Source] = []
    for defn in SOURCES:
        row = db.query(Source).filter_by(name=defn.name).first()
        if row is None:
            row = Source(**defn.model_dump())
            db.add(row)
        else:
            for field in _DEFINITION_FIELDS:
                setattr(row, field, getattr(defn, field))
        synced.append(row)
    db.commit()
    return synced
