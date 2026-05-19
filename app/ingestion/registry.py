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
    # ── Tier 1: Google AI Family ─────────────────────────────────────────
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
    # ── Tier 2: Major AI Labs ────────────────────────────────────────────
    SourceDefinition(
        name="OpenAI News",
        feed_url="https://openai.com/news/rss.xml",
        feed_type="rss", tier=2,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
    SourceDefinition(
        name="Hugging Face Blog",
        feed_url="https://huggingface.co/blog/feed.xml",
        feed_type="rss", tier=2,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
    SourceDefinition(
        name="Meta AI Blog",
        feed_url="https://engineering.fb.com/feed/",
        feed_type="rss", tier=2,
        classification="verify-before-enabling",
        storage_mode="summary_metadata",
    ),
    # arXiv: feed_url stores the search query passed to fetch_arxiv()
    SourceDefinition(
        name="arXiv cs.AI + cs.LG",
        feed_url="cat:cs.AI OR cat:cs.LG",
        feed_type="arxiv_api", tier=2,
        classification="verified-official",
        storage_mode="abstract_metadata",
    ),
    SourceDefinition(
        name="Microsoft AI Blog",
        feed_url="https://blogs.microsoft.com/ai/feed/",
        feed_type="rss", tier=2,
        classification="verified-official",
        storage_mode="summary_metadata",
    ),
    SourceDefinition(
        name="NVIDIA Blog",
        feed_url="https://blogs.nvidia.com/feed/",
        feed_type="rss", tier=2,
        classification="verified-official",
        storage_mode="summary_metadata",
    ),
    # Anthropic, Mistral, Cohere: no confirmed RSS URL — add when verified
    # xAI (x.ai/blog): no RSS feed published yet — revisit when available
]

# Definition-only fields — runtime state columns are never overwritten by a sync
_DEFINITION_FIELDS = {"name", "feed_url", "feed_type", "tier", "classification", "storage_mode"}


def sync_sources(db: Session) -> tuple[int, int]:
    """Upsert SOURCES registry into the sources table.

    Only definition fields are written; runtime state (circuit_breaker_state,
    consecutive_failures, last_fetched_at) is left untouched on existing rows.
    Returns (inserted, updated).
    """
    inserted = updated = 0
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
    db.commit()
    return inserted, updated
