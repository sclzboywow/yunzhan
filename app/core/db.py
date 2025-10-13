from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import get_settings


Base = declarative_base()


def _ensure_parent_directory(db_url: str) -> None:
    if db_url.startswith("sqlite:"):
        # sqlite:////abs/path.db
        file_path = db_url.split("sqlite:///")[-1]
        parent = Path(file_path).parent
        parent.mkdir(parents=True, exist_ok=True)


def get_engine():
    settings = get_settings()
    db_url = f"sqlite:///{settings.sqlite_path}"
    _ensure_parent_directory(db_url)
    return create_engine(db_url, connect_args={"check_same_thread": False})


engine = get_engine()

# Enable WAL and reasonable sync on each new DB connection
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):  # type: ignore[no-redef]
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()
    except Exception:
        # Best-effort; ignore if not supported
        pass
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


