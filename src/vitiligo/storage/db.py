"""SQLite engine, session, and schema management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from vitiligo.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the configured database."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def init_db() -> None:
    """Create tables if they do not exist."""
    # Import models so SQLModel.metadata sees them.
    from vitiligo.storage import models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session and commit/rollback automatically.

    `expire_on_commit=False` keeps attributes accessible on objects that
    outlive the session — important for the CLI, where we render results
    after the `with` block exits.
    """
    session = Session(get_engine(), expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
