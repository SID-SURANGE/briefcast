import structlog

log = structlog.get_logger()


def l1_hash(url: str) -> str:
    pass


def l2_cosine(embedding_a: list[float], embedding_b: list[float]) -> float:
    pass


def is_duplicate(url: str, title_embedding: list[float]) -> bool:
    pass
