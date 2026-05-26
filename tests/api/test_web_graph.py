"""Web API tests for graph and trials endpoints on an empty database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_graph_stats_empty_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.get("/api/graph/stats")
    assert resp.status_code == 200
    assert resp.json()["total"][0]["count"] == 0


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


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/graph/search", {"q": "vitiligo", "limit": 5}),
        ("/api/graph/search", {"q": "zzzznonexistententity", "limit": 5}),
    ],
)
def test_graph_search_returns_empty_on_empty_db(
    api_client: TestClient,
    path: str,
    params: dict,
) -> None:
    resp = api_client.get(path, params=params)
    assert resp.status_code == 200
    assert resp.json()["results"] == []


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
