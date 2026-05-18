from fastapi import Depends, FastAPI, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from telegram import Update

from app.db import get_db
from app.delivery.telegram_bot import build_application

app = FastAPI(title="briefcast")

_ptb_app = build_application()


@app.on_event("startup")
async def _startup() -> None:
    await _ptb_app.initialize()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await _ptb_app.shutdown()


@app.get("/healthz")
def healthz(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    data = await request.json()
    update = Update.de_json(data, _ptb_app.bot)
    await _ptb_app.process_update(update)
    return {"ok": "true"}
