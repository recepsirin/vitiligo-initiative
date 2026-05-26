"""HTTP-level confidence tests on the regression corpus."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from tests.helpers.fake_llm import install_capturing_llm
from tests.helpers.paths import FIXTURES_DIR
from tests.helpers.rag_expectations import assert_answer_cites_only_retrieved
from tests.helpers.retrieval_expectations import (
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
        assert len(citations) == top_k, f"{case['id']}: expected {top_k} citations, got {len(citations)}"

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
