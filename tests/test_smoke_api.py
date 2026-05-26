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


def test_smoke_trials_intervention_regression(smoke_client: TestClient) -> None:
    """Real-corpus guard: tacrolimus findable via interventions JSON only."""
    r = smoke_client.post(
        "/api/trials/search",
        json={"query": "tacrolimus", "limit": 50, "offset": 0},
    )
    assert r.status_code == 200
    ids = {t["source_id"] for t in r.json()["results"]}
    assert "NCT03365141" in ids


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


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/ask", {"question": "What is vitiligo?", "top_k": 3}),
        ("/api/hypothesize", {"intent": "stop spread vitiligo", "top_k": 10}),
    ],
)
def test_smoke_llm_routes_do_not_500_without_key(
    smoke_client: TestClient,
    path: str,
    body: dict,
) -> None:
    r = smoke_client.post(path, json=body)
    assert r.status_code in (200, 503)
