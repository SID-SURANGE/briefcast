from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

EMBEDDING_DIM = 768  # nomic-embed-text-v1.5


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    source_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(EMBEDDING_DIM))
    score: Mapped[Optional[float]] = mapped_column(Float)
    # SHA-256 of the URL — fast O(1) L1 dedup lookup
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # "summary_metadata" | "abstract_metadata" | "processed_discard"
    storage_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_source_tier", "source_tier"),
    )
