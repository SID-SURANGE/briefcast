"""initial schema

Revision ID: 1a2b3c4d5e6f
Revises:
Create Date: 2026-05-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.models.article import EMBEDDING_DIM

revision: str = "1a2b3c4d5e6f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("feed_url", sa.String, nullable=False),
        sa.Column("tier", sa.Integer, nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("storage_mode", sa.String(32), nullable=False),
        sa.Column("circuit_breaker_state", sa.String(16), nullable=False, server_default="closed"),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("url", sa.String, nullable=False, unique=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("author", sa.String, nullable=True),
        sa.Column("source_name", sa.String, nullable=False),
        sa.Column("source_tier", sa.Integer, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("dedup_hash", sa.String(64), nullable=False),
        sa.Column("storage_mode", sa.String(32), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_articles_dedup_hash", "articles", ["dedup_hash"])
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_source_tier", "articles", ["source_tier"])

    # Cosine similarity index — effective once rows are loaded (needs ~300+ rows for lists=100)
    op.execute(
        "CREATE INDEX ix_articles_embedding ON articles "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table("articles")
    op.drop_table("sources")
    op.execute("DROP EXTENSION IF EXISTS vector")
