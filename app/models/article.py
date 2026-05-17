from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
    # embedding stored via pgvector — added in Alembic migration
    score: Mapped[Optional[float]] = mapped_column(Float)
    dedup_hash: Mapped[str] = mapped_column(String, nullable=False)
    storage_mode: Mapped[str] = mapped_column(String, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
