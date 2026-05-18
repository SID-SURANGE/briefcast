import hashlib

import numpy as np
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.models.article import Article

log = structlog.get_logger()


def l1_hash(url: str) -> str:
    """SHA-256 of the URL — fast O(1) exact-match dedup before any embedding call."""
    return hashlib.sha256(url.encode()).hexdigest()


def l2_cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; returns 0.0 if either vector is zero-norm."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def is_duplicate(url: str, title_embedding: list[float], db: Session) -> bool:
    """
    Two-layer dedup. Returns True if the article should be skipped.

    L1: URL SHA-256 hash lookup — exact match, no embedding needed.
    L2: cosine similarity of the new article's title embedding vs stored embeddings
        of the 500 most-recently ingested articles. We compare title vs summary
        embeddings — slightly approximate, but sufficient for near-duplicate detection.
        Threshold: DEDUP_THRESHOLD env var (default 0.92).
    """
    h = l1_hash(url)
    if db.query(Article).filter(Article.dedup_hash == h, Article.deleted_at.is_(None)).first():
        log.debug("dedup.l1_hit", url=url)
        return True

    recent = (
        db.query(Article.embedding)
        .filter(Article.embedding.is_not(None), Article.deleted_at.is_(None))
        .order_by(Article.ingested_at.desc())
        .limit(500)
        .all()
    )
    for (stored_embedding,) in recent:
        if l2_cosine(title_embedding, stored_embedding) >= settings.dedup_threshold:
            log.debug("dedup.l2_hit", url=url, threshold=settings.dedup_threshold)
            return True

    return False
