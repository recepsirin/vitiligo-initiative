"""Hypothesize confidence tests on the regression corpus.

Against the library, not an HTTP route: the served app no longer offers
Hypothesize, and ``vitiligo hypothesize`` is the caller that remains.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from tests.helpers.fake_llm import install_capturing_hypothesize_llm
from tests.helpers.paths import FIXTURES_DIR
from tests.helpers.rag_expectations import assert_hypothesize_candidate_citations

MANIFEST = FIXTURES_DIR / "regression_expectations.json"
_EXPECTATIONS = json.loads(MANIFEST.read_text())

pytestmark = pytest.mark.confidence


class TestHypothesizeConfidence:
    """``generate_hypotheses`` must ground candidates in retrieved evidence."""

    @pytest.mark.parametrize("case", _EXPECTATIONS["hypothesize"], ids=lambda c: c["id"])
    def test_hypothesize_grounds_candidates_in_retrieval(
        self,
        case: dict,
        require_regression_corpus: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vitiligo.reasoning.hypothesize import generate_hypotheses

        llm = install_capturing_hypothesize_llm(
            monkeypatch,
            candidate_names=list(case["must_include_candidate_names"]),
        )
        top_k = int(case["top_k"])

        report = generate_hypotheses(intent=case["intent"], top_k=top_k)
        assert report.intent == case["intent"]
        assert report.model == "fake-confidence"

        citations = [asdict(c) for c in report.citations]
        trial_citations = [asdict(c) for c in report.trial_citations]
        prior_citations = [asdict(c) for c in report.prior_citations]
        graph_citations = [asdict(c) for c in report.graph_citations]
        candidates = [asdict(c) for c in report.candidates]

        assert len(citations) == top_k, f"{case['id']}: expected {top_k} paper citations"
        assert candidates, f"{case['id']}: empty candidate list"

        paper_ids = {c["source_id"] for c in citations}
        missing_papers = set(case["must_include_citation_source_ids"]) - paper_ids
        assert not missing_papers, (
            f"{case['id']} ({case['scenario']}): missing paper citations {sorted(missing_papers)}"
        )

        if expected_trials := case.get("must_include_trial_source_ids"):
            trial_ids = {t["source_id"] for t in trial_citations}
            missing_trials = set(expected_trials) - trial_ids
            assert not missing_trials, (
                f"{case['id']}: missing trial citations {sorted(missing_trials)}"
            )

        returned_names = {c["name"] for c in candidates}
        for name in case["must_include_candidate_names"]:
            assert name in returned_names, (
                f"{case['id']}: fake LLM candidate {name!r} missing from response"
            )

        for citation in citations:
            title = citation.get("title") or ""
            assert title in llm.captured_user, (
                f"{case['id']}: paper title {title!r} missing from Hypothesize prompt"
            )

        assert "RETRIEVED PAPERS:" in llm.captured_user
        assert f"RESEARCH INTENT: {case['intent']}" in llm.captured_user

        assert_hypothesize_candidate_citations(
            candidates,
            paper_count=len(citations),
            trial_count=len(trial_citations),
            prior_count=len(prior_citations),
            graph_count=len(graph_citations),
        )
