"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod


def _corpus_path() -> Path:
    return Path(os.environ.get("VITILIGO_DB_PATH", "data/vitiligo.db"))


@pytest.fixture(autouse=True)
def _reset_db_engine_between_tests() -> None:
    """Graph/export tests swap DB paths; always drop cached engine between tests."""
    cfg._settings = None
    dbmod._engine = None
    yield
    cfg._settings = None
    dbmod._engine = None


@pytest.fixture
def require_local_corpus() -> None:
    """Skip when the full local SQLite corpus is unavailable (e.g. CI without DB upload)."""
    path = _corpus_path()
    if not path.is_file() or path.stat().st_size < 10_000_000:
        pytest.skip("requires local data/vitiligo.db corpus")
    cfg._settings = None
    dbmod._engine = None
    from vitiligo.storage import init_db

    init_db()
