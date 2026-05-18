import structlog


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def log_llm_call(
    model: str,
    task: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    estimated_cost_usd: float,
    source: str,
) -> None:
    structlog.get_logger().info(
        "llm.call",
        model=model,
        task=task,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=round(latency_ms, 1),
        estimated_cost_usd=round(estimated_cost_usd, 6),
        source=source,
    )
