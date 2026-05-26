"""Tests for corpus statistics helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from vitiligo.corpus_stats import get_corpus_stats


@pytest.mark.integration
def test_corpus_stats_empty_schema(test_db_path) -> None:
    """Schema exists but tables are empty."""
    stats = get_corpus_stats()
    assert stats["database"]["exists"] is True
    assert stats["documents"] == 0
    assert stats["trials"] == 0


@pytest.mark.integration
def test_corpus_stats_reflects_seeded_trials(seeded_trial_db) -> None:
    stats = get_corpus_stats()
    assert stats["database"]["exists"] is True
    assert stats["trials"] == 4
    assert stats["documents"] == 0


def test_corpus_stats_when_db_file_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "does-not-exist.db"
    monkeypatch.setenv("VITILIGO_DB_PATH", str(missing))
    import vitiligo.config as cfg
    import vitiligo.storage.db as dbmod

    cfg._settings = None
    dbmod._engine = None

    stats = get_corpus_stats()
    assert stats["database"]["exists"] is False
    assert stats["documents"] == 0
