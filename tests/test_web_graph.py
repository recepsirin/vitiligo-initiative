"""Web API tests for graph endpoints on an empty database."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_graph_stats_empty_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.get("/api/graph/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"][0]["count"] == 0


def test_graph_neighbors_unknown_entity_returns_empty(api_client: TestClient) -> None:
    resp = api_client.get(
        "/api/graph/neighbors",
        params={"name": "definitely-not-in-graph-xyz", "limit": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_graph_export_empty_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.get("/api/graph/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entities"] == []
    assert data["edges"] == []


def test_graph_search_no_match_returns_empty(api_client: TestClient) -> None:
    resp = api_client.get(
        "/api/graph/search",
        params={"q": "zzzznonexistententity", "limit": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []
