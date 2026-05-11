"""
engine.py — Unified Database Engine
====================================
Single SQLAlchemy engine serving the entire pipeline.

Configuration:
  - Default: SQLite at project_root/wise_purchaser.db
  - Override: Set DATABASE_URL environment variable
    e.g. DATABASE_URL=postgresql://user:pass@localhost:5432/wise_purchaser

Swapping to PostgreSQL requires only changing the env var
and installing psycopg2-binary. Zero code changes needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ── Database URL resolution ─────────────────────────────────────────────────
# Priority: ENV var > default SQLite
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB_PATH = _PROJECT_ROOT / "wise_purchaser.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

# ── Engine ───────────────────────────────────────────────────────────────────
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
    pool_pre_ping=True,
)

# Enable WAL mode for SQLite (better concurrent read/write performance)
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ── Session factory ──────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Base class ───────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all ORM models in the unified database."""
    pass


# ── Dependency injection for FastAPI ─────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    Automatically closes the session after the request completes.

    Usage:
        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
