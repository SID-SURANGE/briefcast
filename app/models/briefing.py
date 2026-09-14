from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Briefing(Base):
    __tablename__ = "briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Ordered company keys shown in this briefing (from composer.compose()) —
    # kept for a possible future drill-down view, not read by the v1 web page.
    source_keys: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
