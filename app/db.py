from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Railway injects postgresql:// but psycopg3 requires postgresql+psycopg://
_db_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(_db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
