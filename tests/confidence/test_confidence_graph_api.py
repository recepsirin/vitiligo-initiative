"""HTTP-level graph confidence tests on the regression corpus."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from tests.helpers.graph_expectations import (
    assert_graph_export_expectations,
    assert_graph_neighbors_expectations,
    assert_graph_search_expectations,
)
from tests.helpers.paths import FIXTURES_DIR

MANIFEST = FIXTURES_DIR / "regression_expectations.json"
_EXPECTATIONS = json.loads(MANIFEST.read_text())
_SEARCH_CASES = [c for c in _EXPECTATIONS.get("graph", []) if "search_q" in c]
_NEIGHBOR_CASES = [c for c in _EXPECTATIONS.get("graph", []) if "neighbors_name" in c]
_EXPORT_CASES = [c for c in _EXPECTATIONS.get("graph", []) if "min_entities" in c]

pytestmark = pytest.mark.confidence


@pytest.mark.parametrize("case", _SEARCH_CASES, ids=lambda c: c["id"])
def test_graph_search_api(case: dict, regression_api_client: TestClient) -> None:
    resp = regression_api_client.get(
        "/api/graph/search",
        params={"q": case["search_q"], "limit": int(case["limit"])},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["query"] == case["search_q"]
    assert_graph_search_expectations(case, body["results"])


@pytest.mark.parametrize("case", _NEIGHBOR_CASES, ids=lambda c: c["id"])
def test_graph_neighbors_api(case: dict, regression_api_client: TestClient) -> None:
    resp = regression_api_client.get(
        "/api/graph/neighbors",
        params={
            "name": case["neighbors_name"],
            "hops": int(case.get("hops", 1)),
            "limit": int(case["limit"]),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == case["neighbors_name"]
    assert_graph_neighbors_expectations(case, body["results"])


@pytest.mark.parametrize("case", _EXPORT_CASES, ids=lambda c: c["id"])
def test_graph_export_api(case: dict, regression_api_client: TestClient) -> None:
    resp = regression_api_client.get("/api/graph/export")
    assert resp.status_code == 200, resp.text
    assert_graph_export_expectations(case, resp.json())
