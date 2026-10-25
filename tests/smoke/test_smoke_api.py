"""Smoke tests — thin end-to-end checks over the full local corpus.

Per the test pyramid: keep these few; they validate critical paths only.
Run locally: ``pytest -m smoke``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vitiligo.storage import init_db
from vitiligo.web.app import create_app

pytestmark = pytest.mark.smoke


@pytest.fixture
def smoke_client(require_local_corpus) -> TestClient:
    init_db()
    return TestClient(create_app())


def test_smoke_health_ready(smoke_client: TestClient) -> None:
    health = smoke_client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ready"] is True


def test_smoke_semantic_search(smoke_client: TestClient) -> None:
    r = smoke_client.post("/api/search", json={"query": "vitiligo JAK", "top_k": 3})
    assert r.status_code == 200
    assert r.json()["results"]


def test_smoke_candidate_report(smoke_client: TestClient) -> None:
    r = smoke_client.get("/api/report/candidates", params={"top_n": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["global_top"]
    assert isinstance(data["notes"], list)


@pytest.mark.parametrize("path", ["/api/ask", "/api/hypothesize"])
def test_smoke_no_generative_route_is_served(smoke_client: TestClient, path: str) -> None:
    assert smoke_client.post(path, json={"question": "x", "intent": "x"}).status_code == 404
