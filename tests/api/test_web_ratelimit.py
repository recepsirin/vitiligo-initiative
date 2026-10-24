"""Rate limiting on the real FastAPI application."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_create_app_rate_limits_post_routes(api_client_rate_limited: TestClient) -> None:
    assert (
        api_client_rate_limited.post(
            "/api/trials/search",
            json={"query": "vitiligo", "limit": 5},
        ).status_code
        == 200
    )
    assert (
        api_client_rate_limited.post(
            "/api/trials/search",
            json={"query": "vitiligo", "limit": 5},
        ).status_code
        == 200
    )
    blocked = api_client_rate_limited.post(
        "/api/trials/search",
        json={"query": "vitiligo", "limit": 5},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_create_app_get_routes_bypass_rate_limit(api_client_rate_limited: TestClient) -> None:
    for _ in range(5):
        assert api_client_rate_limited.get("/api/health").status_code == 200


def test_rate_limit_disabled_when_configured_zero(
    test_db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VITILIGO_RATE_LIMIT_POST_PER_MINUTE", "0")
    import vitiligo.config as cfg
    import vitiligo.storage.db as dbmod

    cfg._settings = None
    dbmod._engine = None

    from vitiligo.web.app import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    for _ in range(5):
        assert (
            client.post(
                "/api/trials/search",
                json={"query": "vitiligo", "limit": 5},
            ).status_code
            == 200
        )


def test_candidate_report_is_cached_until_db_changes(
    api_client: TestClient, test_db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The expensive GET is rebuilt only when the corpus file changes."""
    import os

    import vitiligo.web.app as web_app
    from vitiligo.reports.candidates import CandidateReport

    builds: list[int] = []

    def fake_build(*, top_n: int) -> CandidateReport:
        builds.append(top_n)
        return CandidateReport(
            generated_at="t",
            engine_version="v",
            methodology="m",
            corpus={},
            intents=[],
            global_top=[],
        )

    monkeypatch.setattr(web_app, "build_candidate_report", fake_build)

    for _ in range(3):
        assert api_client.get("/api/report/candidates?top_n=5").status_code == 200
    assert builds == [5]

    api_client.get("/api/report/candidates?top_n=7")
    assert builds == [5, 7]

    stat = test_db_path.stat()
    os.utime(test_db_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    api_client.get("/api/report/candidates?top_n=5")
    assert builds == [5, 7, 5]
