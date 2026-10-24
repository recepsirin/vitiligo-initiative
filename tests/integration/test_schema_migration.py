"""A corpus built before a column existed must still open.

SQLModel creates missing tables but never alters one that exists, so a column
added later is absent from every corpus already on disk. The first attempt
here also stored the enum by its value ('asserted') where SQLAlchemy reads it
by name ('ASSERTED'), which raised LookupError on every edge read.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.storage import init_db, session_scope
from vitiligo.storage.models import ClaimKind, GraphEdge

pytestmark = pytest.mark.integration


def _corpus_without_the_columns(path: Path) -> None:
    """A graph_edges table as it looked before claim and causal_level existed."""
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE graph_edges (
            id INTEGER NOT NULL PRIMARY KEY,
            subject_id INTEGER NOT NULL,
            predicate VARCHAR(15) NOT NULL,
            object_id INTEGER NOT NULL,
            confidence FLOAT NOT NULL,
            extraction_method VARCHAR NOT NULL,
            evidence JSON,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        INSERT INTO graph_edges VALUES
            (1, 1, 'TREATS', 2, 0.88, 'structured', '[]', '2026-01-01', '2026-01-01');
        """
    )
    con.commit()
    con.close()


def test_an_older_corpus_gains_the_columns_and_its_edges_still_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "old.db"
    _corpus_without_the_columns(db)
    monkeypatch.setenv("VITILIGO_DB_PATH", str(db))
    cfg._settings = None
    dbmod._engine = None
    try:
        init_db()
        with session_scope() as session:
            [edge] = session.exec(select(GraphEdge)).all()
        # Reading it at all is the test: a value-cased column raises LookupError.
        assert edge.claim == ClaimKind.ASSERTED
        assert edge.causal_level is None
    finally:
        cfg._settings = None
        dbmod._engine = None


def test_a_column_holding_the_enum_value_instead_of_its_name_is_repaired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "wrong.db"
    _corpus_without_the_columns(db)
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE graph_edges ADD COLUMN claim VARCHAR DEFAULT 'asserted'")
    con.execute("ALTER TABLE graph_edges ADD COLUMN causal_level VARCHAR")
    con.commit()
    con.close()

    monkeypatch.setenv("VITILIGO_DB_PATH", str(db))
    cfg._settings = None
    dbmod._engine = None
    try:
        init_db()
        with session_scope() as session:
            [edge] = session.exec(select(GraphEdge)).all()
        assert edge.claim == ClaimKind.ASSERTED
    finally:
        cfg._settings = None
        dbmod._engine = None
