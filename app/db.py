from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Managed Postgres providers (Neon included) hand out postgresql:// but psycopg3 requires postgresql+psycopg://
_db_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
# pool_recycle: Neon can drop idle connections more aggressively than a persistent host —
# recycle before that happens rather than surfacing a stale-connection error to the caller.
engine = create_engine(_db_url, pool_pre_ping=True, pool_recycle=280)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
