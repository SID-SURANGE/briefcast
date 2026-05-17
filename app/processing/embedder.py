import structlog

log = structlog.get_logger()


async def embed(text: str) -> list[float]:
    pass


async def embed_batch(texts: list[str]) -> list[list[float]]:
    pass
