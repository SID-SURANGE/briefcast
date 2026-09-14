"""add briefings table

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-09-14

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c4d5e6f7a8b"
down_revision: str | None = "2b3c4d5e6f7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("html_content", sa.Text, nullable=False),
        sa.Column("article_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_keys", sa.ARRAY(sa.String), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_briefings_published_at", "briefings", ["published_at"])


def downgrade() -> None:
    op.drop_table("briefings")
