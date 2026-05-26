"""Confidence regression tests — curated research scenarios with expected outcomes.

Unlike plumbing tests, these assert the engine returns **the right evidence**
for real vitiligo research questions. They require the full local corpus
(``data/vitiligo.db`` with embeddings) and are the authoritative quality gate.

Run locally before release: ``pytest -m confidence``
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vitiligo.embed import semantic_search
from vitiligo.reports import build_candidate_report
from vitiligo.trials import TrialFilter, list_trials

MANIFEST = Path(__file__).resolve().parent / "fixtures" / "regression_expectations.json"

pytestmark = pytest.mark.confidence


@pytest.fixture
def expectations(require_local_corpus) -> dict:
    return json.loads(MANIFEST.read_text())


class TestRetrievalConfidence:
    """Semantic search must surface known pivotal papers for expert queries."""

    @pytest.mark.parametrize("case", json.loads(MANIFEST.read_text())["retrieval"], ids=lambda c: c["id"])
    def test_query_returns_expected_papers(self, case: dict) -> None:
        hits = semantic_search(query=case["query"], top_k=int(case["top_k"]))
        assert hits, f"{case['id']}: no results for {case['query']!r}"

        returned_ids = {h.document.source_id for h in hits}
        missing = set(case["must_include_source_ids"]) - returned_ids
        assert not missing, (
            f"{case['id']} ({case['scenario']}): missing expected papers {sorted(missing)}. "
            f"Got top-{case['top_k']}: {[(h.document.source_id, (h.document.title or '')[:60]) for h in hits[:5]]}"
        )

        top = hits[0]
        title = (top.document.title or "").lower()
        keywords = [k.lower() for k in case["top_hit_title_must_contain_any"]]
        assert any(kw in title for kw in keywords), (
            f"{case['id']}: top hit title {top.document.title!r} missing any of {case['top_hit_title_must_contain_any']}"
        )

        min_score = float(case["min_top_score"])
        assert top.score >= min_score, (
            f"{case['id']}: top score {top.score:.4f} below minimum {min_score} — retrieval quality degraded"
        )


class TestTrialsConfidence:
    """Structured trial search must find registry IDs known to matter clinically."""

    @pytest.mark.parametrize("case", json.loads(MANIFEST.read_text())["trials"], ids=lambda c: c["id"])
    def test_query_finds_expected_trials(self, case: dict) -> None:
        trials = list_trials(
            TrialFilter(query=case["query"], limit=int(case["limit"]))
        )
        returned_ids = {t.source_id for t in trials}
        missing = set(case["must_include_source_ids"]) - returned_ids
        assert not missing, (
            f"{case['id']} ({case['scenario']}): missing trials {sorted(missing)}. "
            f"Returned {len(trials)} ids (first 10): {sorted(returned_ids)[:10]}"
        )


class TestCandidateReportConfidence:
    """Deterministic rankings must surface the JAK pipeline and tacrolimus."""

    def test_global_top_includes_expected_drugs(self, expectations: dict) -> None:
        spec = expectations["candidates"]
        report = build_candidate_report(top_n=int(spec["top_n"]))
        tokens = {c.canonical_token for c in report.global_top}
        missing = set(spec["must_include_tokens"]) - tokens
        assert not missing, (
            f"Candidate report missing expected drugs: {sorted(missing)}. "
            f"Top-{spec['top_n']}: {[(c.rank, c.canonical_token, c.score.total) for c in report.global_top]}"
        )

    def test_rank1_is_ruxolitinib_with_strong_score(self, expectations: dict) -> None:
        spec = expectations["candidates"]
        report = build_candidate_report(top_n=int(spec["top_n"]))
        assert report.global_top, "empty candidate report"
        rank1 = report.global_top[0]
        assert rank1.canonical_token == spec["rank1_token"], (
            f"rank 1 is {rank1.canonical_token!r}, expected {spec['rank1_token']!r}"
        )
        assert rank1.score.total >= int(spec["min_rank1_score"]), (
            f"rank 1 score {rank1.score.total} below minimum {spec['min_rank1_score']}"
        )
