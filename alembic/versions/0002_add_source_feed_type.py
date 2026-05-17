"""add feed_type to sources

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2b3c4d5e6f7a"
down_revision: str | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # nullable first so existing rows don't violate the constraint
    op.add_column("sources", sa.Column("feed_type", sa.String(16), nullable=True))
    op.execute("UPDATE sources SET feed_type = 'rss' WHERE feed_type IS NULL")
    op.alter_column("sources", "feed_type", nullable=False)


def downgrade() -> None:
    op.drop_column("sources", "feed_type")
