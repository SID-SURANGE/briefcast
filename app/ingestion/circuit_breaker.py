import structlog

log = structlog.get_logger()

MAX_FAILURES = 3


def record_success(source_name: str) -> None:
    pass


def record_failure(source_name: str) -> None:
    pass


def is_open(source_name: str) -> bool:
    pass
