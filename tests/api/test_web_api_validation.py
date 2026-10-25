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


@pytest.mark.parametrize("path", ["/api/ask", "/api/hypothesize"])
def test_no_generative_route_is_served(api_client_errors: TestClient, path: str) -> None:
    """The engine calls no model API, and these paths are the ones it used to.

    Kept as a regression guard: the modules behind them are gone, so a 200 here
    would mean someone reintroduced a generative endpoint rather than merely
    renamed something.
    """
    assert api_client_errors.post(path, json={"question": "x", "intent": "x"}).status_code == 404


def test_health_reports_degraded_on_empty_db(api_client: TestClient) -> None:
    resp = api_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["ready"] is False
    assert data["corpus"]["documents"] == 0


def test_search_returns_empty_results_when_corpus_not_indexed(api_client: TestClient) -> None:
    """Semantic search degrades gracefully: an empty list, not an error."""
    resp = api_client.post("/api/search", json={"query": "vitiligo JAK", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "vitiligo JAK"
    assert data["results"] == []


def test_evidence_endpoint_serves_week_24_results(api_client_seeded: TestClient) -> None:
    """The clinician view reports the primary endpoint, with the rules it applied."""
    resp = api_client_seeded.get("/api/evidence")
    assert resp.status_code == 200
    body = resp.json()
    assert body["week"] == 24
    assert body["count"] == len(body["rows"])
    assert "which patients its figure counted" in body["note"]
    for row in body["rows"]:
        assert row["week"] == 24
        assert row["analysed"] >= 20, f"{row['agent']}: arm too small to state a rate"
        assert row["endpoint"].startswith(("F-VASI", "T-VASI"))
        if row["later"] is not None:
            assert row["later"]["week"] > 24
            assert row["later"]["started"] >= row["later"]["analysed"]


def test_served_responses_name_no_licensed_source(api_client_seeded: TestClient) -> None:
    """DrugBank's terms do not permit redistributing what an operator imported.

    NOTICE states the same rule for the repository, and a real corpus carries
    four such priors. The entity is seeded here so the assertion has something
    to find: a new graph endpoint that forgets the filter fails here rather than
    in someone's licence review.
    """
    from vitiligo.graph.store import upsert_edge, upsert_entity
    from vitiligo.storage import session_scope
    from vitiligo.storage.models import ClaimKind, EntityKind, RelationKind

    with session_scope() as session:
        drug = upsert_entity(
            session,
            kind=EntityKind.DRUG,
            name="Ruxolitinib",
            external_ids={"drugbank": "DB08877", "chembl": "CHEMBL1789941"},
        )
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        upsert_edge(
            session,
            subject=drug,
            predicate=RelationKind.TREATS,
            obj=disease,
            confidence=0.9,
            extraction_method="structured",
            evidence={"source_type": "prior", "source_id": "drugbank:DB08877"},
            claim=ClaimKind.ASSERTED,
        )
        session.commit()

    for path in (
        "/api/graph/export",
        "/api/graph/search?q=ruxolitinib",
        "/api/graph/neighbors?name=vitiligo",
    ):
        resp = api_client_seeded.get(path)
        assert resp.status_code == 200, path
        assert "drugbank" not in resp.text.lower(), f"{path} redistributes a licensed source"

    # The filter drops one cross-reference, not every cross-reference.
    assert "CHEMBL1789941" in api_client_seeded.get("/api/graph/search?q=ruxolitinib").text


def test_licensed_filters_keep_redistributable_sources() -> None:
    """Open Targets is CC0 and ChEMBL CC-BY-SA: filtering those would lose real data."""
    from vitiligo.web.app import public_evidence, public_external_ids

    assert public_external_ids(
        {"drugbank": "DB08877", "chembl": "CHEMBL1789941", "ensembl": "ENSG00000162434"}
    ) == {"chembl": "CHEMBL1789941", "ensembl": "ENSG00000162434"}
    assert public_evidence(
        [{"source_id": "drugbank:DB08877"}, {"source_id": "opentargets:EFO_0004208"}]
    ) == [{"source_id": "opentargets:EFO_0004208"}]
