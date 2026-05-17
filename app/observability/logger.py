import structlog


def configure_logging() -> None:
    pass


def log_llm_call(
    model: str,
    task: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    estimated_cost_usd: float,
    source: str,
) -> None:
    pass
