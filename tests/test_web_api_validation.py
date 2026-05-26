"""Web API validation and error-path tests.

422/400/503 responses and degraded-mode behavior without the full corpus.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/search", {}),
        ("/api/search", {"query": ""}),
        ("/api/search", {"query": "vitiligo", "top_k": 0}),
        ("/api/ask", {}),
        ("/api/ask", {"question": ""}),
        ("/api/hypothesize", {}),
        ("/api/hypothesize", {"intent": "stop spread", "top_k": 3}),
        ("/api/trials/search", {"limit": 0}),
        ("/api/trials/search", {"offset": -1}),
    ],
)
def test_post_endpoints_reject_invalid_payload(
    api_client_errors: TestClient,
    path: str,
    body: dict,
) -> None:
    resp = api_client_errors.post(path, json=body)
    assert resp.status_code == 422


def test_trials_search_rejects_unknown_source(api_client_seeded: TestClient) -> None:
    resp = api_client_seeded.post(
        "/api/trials/search",
        json={"query": "vitiligo", "source": "clinicaltrials.gov", "limit": 5},
    )
    assert resp.status_code == 400
    assert "Unknown source" in resp.json()["detail"]


@pytest.mark.parametrize("bad_top_n", [0, 21, 100])
def test_report_candidates_rejects_out_of_range_top_n(
    api_client_errors: TestClient,
    bad_top_n: int,
) -> None:
    resp = api_client_errors.get(f"/api/report/candidates?top_n={bad_top_n}")
    assert resp.status_code == 400
    assert "top_n" in resp.json()["detail"]


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/graph/search", {"q": ""}),
        ("/api/graph/search", {"q": "   "}),
        ("/api/graph/neighbors", {"name": ""}),
        ("/api/graph/neighbors", {"name": "  "}),
        ("/api/graph/export", {"edge_limit": 0}),
    ],
)
def test_graph_endpoints_reject_invalid_params(
    api_client_errors: TestClient,
    path: str,
    params: dict,
) -> None:
    resp = api_client_errors.get(path, params=params)
    assert resp.status_code == 400


def test_ask_returns_503_when_llm_not_configured(
    api_client_errors: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vitiligo.reasoning import LLMUnavailable

    def _raise_llm_unavailable(**_: object) -> None:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set.")

    monkeypatch.setattr("vitiligo.web.app.ask_with_citations", _raise_llm_unavailable)

    resp = api_client_errors.post("/api/ask", json={"question": "What is vitiligo?", "top_k": 3})
    assert resp.status_code == 503
    assert "ANTHROPIC" in resp.json()["detail"].upper()


def test_hypothesize_returns_503_when_llm_not_configured(
    api_client_errors: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vitiligo.reasoning import LLMUnavailable

    def _raise_llm_unavailable(**_: object) -> None:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set.")

    monkeypatch.setattr("vitiligo.web.app.generate_hypotheses", _raise_llm_unavailable)

    resp = api_client_errors.post(
        "/api/hypothesize",
        json={"intent": "stop spread vitiligo", "top_k": 10},
    )
    assert resp.status_code == 503


def test_ask_returns_503_when_corpus_not_indexed(api_client_errors: TestClient) -> None:
    resp = api_client_errors.post(
        "/api/ask",
        json={"question": "What is vitiligo?", "top_k": 3},
    )
    assert resp.status_code == 503
    assert "embed" in resp.json()["detail"].lower()


def test_hypothesize_returns_503_when_corpus_not_indexed(api_client_errors: TestClient) -> None:
    resp = api_client_errors.post(
        "/api/hypothesize",
        json={"intent": "stop spread vitiligo", "top_k": 10},
    )
    assert resp.status_code == 503
    assert "embed" in resp.json()["detail"].lower()


def test_health_reports_degraded_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["ready"] is False
    assert data["corpus"]["documents"] == 0


def test_trials_search_returns_empty_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/trials/search",
        json={"query": "tacrolimus", "limit": 10, "offset": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_trials_stats_empty_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.get("/api/trials/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["by_source"] == []


def test_graph_search_returns_empty_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.get("/api/graph/search", params={"q": "vitiligo", "limit": 5})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_search_returns_empty_results_when_corpus_not_indexed(api_client: TestClient) -> None:
    """Semantic search degrades gracefully (empty list) unlike Ask/Hypothesize."""
    resp = api_client.post("/api/search", json={"query": "vitiligo JAK", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "vitiligo JAK"
    assert data["results"] == []
