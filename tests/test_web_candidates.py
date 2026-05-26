"""Web API tests for deterministic candidate report."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vitiligo.web.app import create_app


@pytest.mark.integration
def test_report_candidates_endpoint_returns_ranked_list(require_local_corpus) -> None:
    client = TestClient(create_app())
    resp = client.get("/api/report/candidates?top_n=3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["global_top"]
    assert len(data["global_top"]) <= 3
    first = data["global_top"][0]
    assert first["rank"] == 1
    assert first["score"]["total"] > 0
    assert isinstance(data["notes"], list)
    assert "intents" in data


def test_report_candidates_rejects_invalid_top_n() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/report/candidates?top_n=0")
    assert resp.status_code == 400
