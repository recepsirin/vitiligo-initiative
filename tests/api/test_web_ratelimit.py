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
