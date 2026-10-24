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


# Columns added to existing tables after a corpus was first built. SQLModel
# creates missing tables but never alters one that exists, so a corpus made
# before a column existed would raise on every query that reads it.
# SQLAlchemy persists an enum by its NAME, so the default is 'ASSERTED', not
# the enum's value 'asserted'. A column filled with the value raises
# LookupError on every read.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("graph_edges", "claim", "VARCHAR DEFAULT 'ASSERTED'"),
    ("graph_edges", "causal_level", "VARCHAR"),
)

# Rows written before that was understood, and rows an ALTER left null.
_REPAIRS: tuple[str, ...] = (
    "UPDATE graph_edges SET claim = 'ASSERTED'"
    " WHERE claim IS NULL OR claim NOT IN ('ASSERTED', 'OBSERVED')",
)


def _add_missing_columns(engine: Engine) -> None:
    from sqlalchemy import text

    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        for table, column, definition in _ADDED_COLUMNS:
            if table not in tables:
                continue
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        if "graph_edges" in tables:
            for statement in _REPAIRS:
                conn.execute(text(statement))


def init_db() -> None:
    """Create tables if they do not exist, and add columns added since."""
    # Import models so SQLModel.metadata sees them.
    from vitiligo.storage import models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _add_missing_columns(engine)


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
