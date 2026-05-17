from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    feed_url: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    # "verified-official" | "verify-before-enabling" | "optional-connector" | "excluded"
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    # "summary_metadata" | "abstract_metadata" | "processed_discard"
    storage_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    # "closed" | "open" | "degraded"
    circuit_breaker_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="closed"
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
