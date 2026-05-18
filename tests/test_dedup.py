from unittest.mock import MagicMock

from app.ingestion.dedup import is_duplicate, l1_hash, l2_cosine


def test_l1_hash_deterministic() -> None:
    url = "https://example.com/article/1"
    assert l1_hash(url) == l1_hash(url)


def test_l1_hash_is_64_hex_chars() -> None:
    h = l1_hash("https://example.com")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_l1_hash_differs_for_different_urls() -> None:
    assert l1_hash("https://a.com") != l1_hash("https://b.com")


def test_l2_cosine_identical_vectors() -> None:
    v = [1.0, 0.0, 0.0]
    assert l2_cosine(v, v) == 1.0


def test_l2_cosine_orthogonal_vectors() -> None:
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(l2_cosine(a, b)) < 1e-6


def test_l2_cosine_opposite_vectors() -> None:
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(l2_cosine(a, b) - (-1.0)) < 1e-6


def test_l2_cosine_zero_vector_returns_zero() -> None:
    a = [0.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert l2_cosine(a, b) == 0.0


def test_l2_cosine_symmetry() -> None:
    a = [0.6, 0.8, 0.0]
    b = [0.0, 0.6, 0.8]
    assert abs(l2_cosine(a, b) - l2_cosine(b, a)) < 1e-6


def test_is_duplicate_l1_hit() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = object()  # truthy = found

    assert is_duplicate("https://example.com/a", [0.1] * 768, db) is True


def test_is_duplicate_l2_hit() -> None:
    db = MagicMock()
    # L1 misses
    db.query.return_value.filter.return_value.first.return_value = None
    # L2 returns a stored embedding identical to the query
    identical = [1.0] + [0.0] * 767
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        (identical,)
    ]

    # Query embedding is identical → similarity = 1.0 which is >= default threshold 0.92
    assert is_duplicate("https://new.com/article", identical, db) is True


def test_is_duplicate_l2_miss() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    # Stored embedding is orthogonal to query → similarity ≈ 0.0, well below threshold
    stored = [0.0, 1.0] + [0.0] * 766
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        (stored,)
    ]

    query_emb = [1.0, 0.0] + [0.0] * 766
    assert is_duplicate("https://new.com/other", query_emb, db) is False


def test_is_duplicate_empty_corpus() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    assert is_duplicate("https://new.com/unique", [0.5] * 768, db) is False
