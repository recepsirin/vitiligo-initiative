"""Web API tests for trials search."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vitiligo.web.app import create_app


@pytest.mark.integration
def test_trials_search_ictrp_source_filter(require_local_corpus) -> None:
    client = TestClient(create_app())
    r = client.post(
        "/api/trials/search",
        json={"query": None, "source": "ictrp", "limit": 10, "offset": 0},
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results
    assert all(t["source"] == "ictrp" for t in results)
