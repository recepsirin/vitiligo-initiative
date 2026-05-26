"""Shared pytest fixtures.

Test pyramid (Martin Fowler / Mike Cohn):
- **(default)** — pure unit tests; no real DB
- **integration** — real SQLite on a seeded temp file (fast; runs in CI)
- **corpus** — requires full local ``data/vitiligo.db`` (skip in CI)
- **smoke** — thin end-to-end checks over the full corpus (run locally)
- **confidence** — curated research scenarios on the minimal regression corpus (CI + local)
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from tests.helpers.paths import FIXTURES_DIR, PROJECT_ROOT
from vitiligo.storage import Trial, TrialSourceKind, init_db
from vitiligo.web.app import create_app

REGRESSION_DIR = FIXTURES_DIR / "regression"
REGRESSION_DB = REGRESSION_DIR / "vitiligo-regression.db"


def _corpus_path() -> Path:
    return Path(os.environ.get("VITILIGO_DB_PATH", "data/vitiligo.db"))


def _reset_engine() -> None:
    cfg._settings = None
    dbmod._engine = None


@pytest.fixture(autouse=True)
def _reset_db_engine_between_tests() -> Iterator[None]:
    """Graph/export tests swap DB paths; always drop cached engine between tests."""
    _reset_engine()
    yield
    _reset_engine()


@pytest.fixture
def require_local_corpus() -> None:
    """Skip when the full local SQLite corpus is unavailable (e.g. CI without DB upload)."""
    path = _corpus_path()
    if not path.is_file() or path.stat().st_size < 10_000_000:
        pytest.skip("requires local data/vitiligo.db corpus")
    _reset_engine()
    init_db()


@pytest.fixture
def require_regression_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimal regression corpus from ``tests/fixtures/regression/*.json``."""
    db_path = Path(os.environ.get("VITILIGO_REGRESSION_DB", REGRESSION_DB))
    build_script = PROJECT_ROOT / "scripts" / "test" / "build_regression_db.py"
    if not db_path.is_file():
        subprocess.run(
            [sys.executable, str(build_script), "--output", str(db_path)],
            check=True,
            cwd=PROJECT_ROOT,
        )
    monkeypatch.setenv("VITILIGO_DB_PATH", str(db_path))
    monkeypatch.setenv("VITILIGO_PREWARM_EMBEDDINGS", "false")
    _reset_engine()
    init_db()


@pytest.fixture
def test_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Empty SQLite schema on a temp file — for integration boundary tests."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("VITILIGO_DB_PATH", str(db_file))
    monkeypatch.setenv("VITILIGO_PREWARM_EMBEDDINGS", "false")
    monkeypatch.setenv("VITILIGO_RATE_LIMIT_POST_PER_MINUTE", "0")
    _reset_engine()
    init_db()
    return db_file


@pytest.fixture
def seeded_trial_db(test_db_path: Path) -> Path:
    """Temp DB with a small, deterministic trial set for query/filter tests."""
    from sqlmodel import Session

    from vitiligo.storage import get_engine

    trials = [
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT00000001",
            brief_title="Topical tacrolimus for vitiligo",
            summary="Phase 2 study of tacrolimus ointment.",
            status="RECRUITING",
            phases=["PHASE2"],
            conditions=["Vitiligo"],
            interventions=[{"name": "Tacrolimus 0.1% Ointment", "type": "DRUG"}],
            countries=["United States"],
            has_results=False,
            last_update_date="2024-01-15",
        ),
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT00000002",
            brief_title="Baricitinib in non-segmental vitiligo",
            summary="JAK inhibitor trial.",
            status="COMPLETED",
            phases=["PHASE3"],
            conditions=["Vitiligo"],
            interventions=[{"name": "Baricitinib", "type": "DRUG"}],
            countries=["Germany"],
            has_results=True,
            last_update_date="2024-06-01",
        ),
        Trial(
            source=TrialSourceKind.ICTRP,
            source_id="ICTRP-001",
            brief_title="Herbal compound vitiligo pilot",
            summary="Early exploratory study.",
            status="COMPLETED",
            phases=["NA"],
            conditions=["Vitiligo"],
            interventions=[{"name": "Herbal extract", "type": "OTHER"}],
            countries=["China"],
            has_results=False,
            last_update_date="2023-03-01",
        ),
        Trial(
            source=TrialSourceKind.EUCTR,
            source_id="EUCTR-2020-001",
            brief_title="Pimecrolimus cream vitiligo",
            summary="European registry entry.",
            status="AUTHORISED",
            phases=["PHASE2"],
            conditions=["Vitiligo"],
            interventions=[{"name": "Pimecrolimus", "type": "DRUG"}],
            countries=["France"],
            has_results=False,
            last_update_date="2022-11-01",
        ),
    ]
    with Session(get_engine(), expire_on_commit=False) as session:
        for trial in trials:
            session.add(trial)
        session.commit()
    return test_db_path


@pytest.fixture
def api_client(test_db_path: Path) -> TestClient:
    """FastAPI TestClient against an empty temp DB (no rate limit, no prewarm)."""
    return TestClient(create_app())


@pytest.fixture
def api_client_errors(test_db_path: Path) -> TestClient:
    """Like ``api_client`` but returns HTTP error responses instead of raising."""
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def api_client_seeded(seeded_trial_db: Path) -> TestClient:
    """TestClient backed by the seeded trial fixture."""
    return TestClient(create_app())


@pytest.fixture
def api_client_rate_limited(test_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with POST rate limiting enabled (2 req/min)."""
    monkeypatch.setenv("VITILIGO_RATE_LIMIT_POST_PER_MINUTE", "2")
    _reset_engine()
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def regression_api_client(require_regression_corpus) -> TestClient:
    """FastAPI TestClient backed by the minimal regression corpus."""
    return TestClient(create_app())
