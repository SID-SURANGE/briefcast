"""
Integration tests for the pgvector retriever.
Requires the DB to be running: docker compose up -d db
All tests use a session-scoped rollback so no data is persisted.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.article import Article
from app.rag.retriever import retrieve


def _unit_vector(seed: int) -> list[float]:
    """Reproducible random unit vector of dim 768."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(768).astype(np.float32)
    v /= np.linalg.norm(v)
    return v.tolist()


def _article(
    url: str,
    embedding: list[float],
    published_at: datetime,
    source_tier: int = 2,
) -> Article:
    import hashlib
    return Article(
        url=url,
        title=f"Test article {url}",
        source_name="test-source",
        source_tier=source_tier,
        dedup_hash=hashlib.sha256(url.encode()).hexdigest(),
        storage_mode="summary_metadata",
        summary="Test summary.",
        embedding=embedding,
        published_at=published_at,
    )


@pytest.fixture
def db():
    try:
        from app.db import engine
        conn = engine.connect()
        trans = conn.begin()
        session = Session(bind=conn)
        session.execute(text("SELECT 1"))  # verify connectivity
        yield session
        session.close()
        trans.rollback()
        conn.close()
    except Exception as exc:
        pytest.skip(f"Database not available: {exc}")


def test_retrieval_returns_k_results(db: Session) -> None:
    now = datetime.now(tz=timezone.utc)
    for i in range(7):
        db.add(_article(f"https://test.com/{i}", _unit_vector(i), now - timedelta(hours=i)))
    db.flush()

    results = retrieve(_unit_vector(99), db, k=5)
    assert len(results) == 5


def test_retrieval_respects_14_day_window(db: Session) -> None:
    now = datetime.now(tz=timezone.utc)
    db.add(_article("https://test.com/recent", _unit_vector(1), now - timedelta(days=3)))
    db.add(_article("https://test.com/stale", _unit_vector(2), now - timedelta(days=20)))
    db.flush()

    results = retrieve(_unit_vector(1), db, k=10)
    urls = [r["url"] for r in results]
    assert "https://test.com/recent" in urls
    assert "https://test.com/stale" not in urls


def test_retrieval_top_result_is_most_similar(db: Session) -> None:
    now = datetime.now(tz=timezone.utc)
    # e1 and e2 are orthogonal unit vectors
    e1 = [1.0] + [0.0] * 767
    e2 = [0.0, 1.0] + [0.0] * 766

    db.add(_article("https://test.com/similar", e1, now - timedelta(hours=1)))
    db.add(_article("https://test.com/dissimilar", e2, now - timedelta(hours=1)))
    db.flush()

    # Query is identical to e1
    results = retrieve(e1, db, k=2)
    assert results[0]["url"] == "https://test.com/similar"


def test_retrieval_similarity_descending(db: Session) -> None:
    now = datetime.now(tz=timezone.utc)
    for i in range(5):
        db.add(_article(f"https://test.com/sim/{i}", _unit_vector(i), now - timedelta(hours=i)))
    db.flush()

    results = retrieve(_unit_vector(0), db, k=5)
    similarities = [r["similarity"] for r in results]
    assert similarities == sorted(similarities, reverse=True)


def test_retrieval_result_dict_has_required_keys(db: Session) -> None:
    now = datetime.now(tz=timezone.utc)
    db.add(_article("https://test.com/keys", _unit_vector(7), now - timedelta(hours=1)))
    db.flush()

    results = retrieve(_unit_vector(7), db, k=1)
    assert len(results) == 1
    required = {"title", "summary", "source_name", "source_tier", "url", "published_at", "similarity"}
    assert required.issubset(results[0].keys())


def test_retrieval_tier_filter(db: Session) -> None:
    now = datetime.now(tz=timezone.utc)
    db.add(_article("https://test.com/t1", _unit_vector(1), now - timedelta(hours=1), source_tier=1))
    db.add(_article("https://test.com/t2", _unit_vector(2), now - timedelta(hours=1), source_tier=2))
    db.flush()

    results = retrieve(_unit_vector(99), db, k=10, tier=1)
    assert all(r["source_tier"] == 1 for r in results)
    assert all(r["url"] != "https://test.com/t2" for r in results)


def test_retrieval_empty_corpus_returns_empty(db: Session) -> None:
    results = retrieve(_unit_vector(0), db, k=10)
    assert results == []
