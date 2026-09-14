import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.delivery.sanitize import sanitize_html
from app.models.briefing import Briefing
from app.models.source import Source

log = structlog.get_logger()

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def digest(request: Request, db: Session = Depends(get_db)):
    briefing_row = db.query(Briefing).order_by(Briefing.published_at.desc()).first()
    briefing = None
    if briefing_row is not None:
        briefing = {
            "html_content": sanitize_html(briefing_row.html_content),
            "article_count": briefing_row.article_count,
            "published_at": briefing_row.published_at,
        }
    sources = db.query(Source).filter(Source.deleted_at.is_(None)).order_by(Source.name).all()
    return templates.TemplateResponse(
        "digest.html", {"request": request, "briefing": briefing, "sources": sources}
    )
