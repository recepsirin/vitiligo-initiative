"""HTTP-level confidence tests on the regression corpus."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from tests.helpers.fake_llm import install_capturing_llm
from tests.helpers.paths import FIXTURES_DIR
from tests.helpers.rag_expectations import assert_answer_cites_only_retrieved
from tests.helpers.retrieval_expectations import (
    assert_retrieval_exclusions,
    assert_retrieval_expectations,
    hits_from_api_results,
)

MANIFEST = FIXTURES_DIR / "regression_expectations.json"
_EXPECTATIONS = json.loads(MANIFEST.read_text())

pytestmark = pytest.mark.confidence


class TestApiSearchConfidence:
    """POST /api/search must return the same pivotal papers as direct retrieval."""

    @pytest.mark.parametrize("case", _EXPECTATIONS["retrieval"], ids=lambda c: c["id"])
    def test_search_api_returns_expected_papers(
        self,
        case: dict,
        regression_api_client: TestClient,
    ) -> None:
        resp = regression_api_client.post(
            "/api/search",
            json={"query": case["query"], "top_k": int(case["top_k"])},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["query"] == case["query"]
        results = body["results"]
        assert_retrieval_expectations(case, hits_from_api_results(results), label="API")

        for rank, row in enumerate(results, start=1):
            assert row["rank"] == rank
            assert row["source"]
            assert row["source_id"]
            assert "evidence_level" in row
            assert "evidence_level_label" in row


class TestApiRetrievalNegativeConfidence:
    """Clinical queries via POST /api/search must not rank animal-only evidence at the top."""

    @pytest.mark.parametrize(
        "case",
        _EXPECTATIONS.get("retrieval_negative", []),
        ids=lambda c: c["id"],
    )
    def test_clinical_queries_are_not_animal_dominated_via_api(
        self,
        case: dict,
        regression_api_client: TestClient,
    ) -> None:
        resp = regression_api_client.post(
            "/api/search",
            json={"query": case["query"], "top_k": int(case["top_k"])},
        )
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        views = hits_from_api_results(results)
        assert views, f"{case['id']}: no results"

        if case.get("must_not_include_source_ids"):
            assert_retrieval_exclusions(case, views, label="API")

        if "max_mouse_in_top" not in case and not case.get("top_hit_must_not_be_mouse"):
            return

        top_n = int(case.get("top_n", 3))
        levels = [row["evidence_level"] for row in results[:top_n]]
        mouse_count = sum(1 for level in levels if level == "mouse")
        max_mouse = int(case.get("max_mouse_in_top", 0))
        assert mouse_count <= max_mouse, (
            f"{case['id']}: {mouse_count}/{top_n} top hits are mouse/animal "
            f"(max {max_mouse}). Levels: {levels}"
        )

        if case.get("top_hit_must_not_be_mouse"):
            assert levels[0] != "mouse", (
                f"{case['id']}: top hit is animal model: {results[0].get('title')!r}"
            )


class TestApiAskCitationConfidence:
    """POST /api/ask must retrieve the right papers and pass them to the LLM faithfully."""

    @pytest.mark.parametrize("case", _EXPECTATIONS["ask"], ids=lambda c: c["id"])
    def test_ask_api_cites_expected_papers(
        self,
        case: dict,
        regression_api_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        llm = install_capturing_llm(monkeypatch)
        top_k = int(case["top_k"])

        resp = regression_api_client.post(
            "/api/ask",
            json={"question": case["question"], "top_k": top_k},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["question"] == case["question"]
        assert body["answer"]
        assert body["model"] == "fake-confidence"
        assert_answer_cites_only_retrieved(body["answer"], top_k)

        citations = body["citations"]
        assert len(citations) == top_k, (
            f"{case['id']}: expected {top_k} citations, got {len(citations)}"
        )

        citation_ids = {c["source_id"] for c in citations}
        missing = set(case["must_include_citation_source_ids"]) - citation_ids
        assert not missing, (
            f"{case['id']} ({case['scenario']}): Ask citations missing {sorted(missing)}. "
            f"Returned: {[(c['index'], c['source_id'], (c.get('title') or '')[:50]) for c in citations[:5]]}"
        )

        for idx, citation in enumerate(citations, start=1):
            assert citation["index"] == idx
            title = citation.get("title") or ""
            assert title in llm.captured_user, (
                f"{case['id']}: citation [{idx}] title {title!r} missing from LLM prompt"
            )

        assert "RETRIEVED PAPERS" in llm.captured_user
        assert f"QUESTION: {case['question']}" in llm.captured_user
        assert "Cite with bracketed numbers like [1]" in llm.captured_user


class TestApiTrialsConfidence:
    """POST /api/trials/search must return the same registry IDs as direct trial search."""

    @pytest.mark.parametrize("case", _EXPECTATIONS["trials"], ids=lambda c: c["id"])
    def test_trials_api_finds_expected_ids(
        self,
        case: dict,
        regression_api_client: TestClient,
    ) -> None:
        resp = regression_api_client.post(
            "/api/trials/search",
            json={"query": case["query"], "limit": int(case["limit"])},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["limit"] == int(case["limit"])
        returned_ids = {row["source_id"] for row in body["results"]}
        missing = set(case["must_include_source_ids"]) - returned_ids
        assert not missing, (
            f"{case['id']} ({case['scenario']}): API missing trials {sorted(missing)}. "
            f"Returned {len(body['results'])} ids (first 10): {sorted(returned_ids)[:10]}"
        )
        for row in body["results"]:
            assert row["source"]
            assert row["source_id"]
            assert row["brief_title"]
