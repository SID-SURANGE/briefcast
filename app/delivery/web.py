import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.delivery.sanitize import sanitize_html
from app.models.briefing import Briefing
from app.models.source import Source

log = structlog.get_logger()

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_ARCHIVE_LIST_LIMIT = 60


def _briefing_view(row: Briefing) -> dict:
    return {
        "id": row.id,
        "html_content": sanitize_html(row.html_content),
        "article_count": row.article_count,
        "published_at": row.published_at,
    }


@router.get("/")
def digest(request: Request, db: Session = Depends(get_db)):
    briefing_row = db.query(Briefing).order_by(Briefing.published_at.desc()).first()
    briefing = _briefing_view(briefing_row) if briefing_row is not None else None
    sources = db.query(Source).filter(Source.deleted_at.is_(None)).order_by(Source.name).all()
    return templates.TemplateResponse(
        request, "digest.html", {"briefing": briefing, "sources": sources, "archived": False}
    )


@router.get("/archive")
def archive(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(Briefing)
        .order_by(Briefing.published_at.desc())
        .limit(_ARCHIVE_LIST_LIMIT)
        .all()
    )
    briefings = [{"id": r.id, "published_at": r.published_at, "article_count": r.article_count} for r in rows]
    return templates.TemplateResponse(request, "archive.html", {"briefings": briefings})


@router.get("/archive/{briefing_id}")
def archive_detail(briefing_id: int, request: Request, db: Session = Depends(get_db)):
    row = db.get(Briefing, briefing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Briefing not found")
    briefing = _briefing_view(row)
    return templates.TemplateResponse(
        request, "digest.html", {"briefing": briefing, "sources": [], "archived": True}
    )
