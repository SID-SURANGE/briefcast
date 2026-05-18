import structlog
from sqlalchemy.orm import Session

from app.models.source import Source

log = structlog.get_logger()

MAX_FAILURES = 3


def record_success(source_name: str, db: Session) -> None:
    """Reset failure count and re-close the breaker after a successful fetch."""
    source = _get(source_name, db)
    if source is None:
        return
    source.consecutive_failures = 0
    source.circuit_breaker_state = "closed"
    db.commit()


def record_failure(source_name: str, db: Session) -> None:
    """Increment failure count; trip to 'degraded' at MAX_FAILURES and log alert."""
    source = _get(source_name, db)
    if source is None:
        return
    source.consecutive_failures += 1
    if source.consecutive_failures >= MAX_FAILURES:
        source.circuit_breaker_state = "degraded"
        log.error(
            "circuit_breaker.tripped",
            source=source_name,
            consecutive_failures=source.consecutive_failures,
        )
        # Telegram alert is sent by the worker after detecting degraded state
    db.commit()


def is_open(source_name: str, db: Session) -> bool:
    """Return True if the breaker is degraded (i.e. fetching should be skipped)."""
    source = _get(source_name, db)
    if source is None:
        return False
    return source.circuit_breaker_state == "degraded"


def _get(source_name: str, db: Session) -> Source | None:
    source = db.query(Source).filter(Source.name == source_name).first()
    if source is None:
        log.warning("circuit_breaker.source_not_found", source=source_name)
    return source
