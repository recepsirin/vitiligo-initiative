"""Confidence regression tests — curated research scenarios with expected outcomes.

These assert the engine returns **the right evidence** for real vitiligo
research questions. They run against the minimal regression corpus built from
``tests/fixtures/regression/*.json`` (CI + local).

Run: ``pytest -m confidence``
Build corpus: ``python scripts/test/build_regression_db.py``
"""

from __future__ import annotations

import json

import pytest
from tests.helpers.paths import FIXTURES_DIR
from tests.helpers.retrieval_expectations import (
    assert_retrieval_exclusions,
    assert_retrieval_expectations,
    hits_from_search,
)

from vitiligo.embed import semantic_search
from vitiligo.evidence import EvidenceLevel, classify_document
from vitiligo.trials import TrialFilter, list_trials

MANIFEST = FIXTURES_DIR / "regression_expectations.json"
_EXPECTATIONS = json.loads(MANIFEST.read_text())

pytestmark = pytest.mark.confidence


class TestRetrievalConfidence:
    """Semantic search must surface known pivotal papers for expert queries."""

    @pytest.mark.parametrize("case", _EXPECTATIONS["retrieval"], ids=lambda c: c["id"])
    def test_query_returns_expected_papers(self, case: dict, require_regression_corpus) -> None:
        hits = semantic_search(query=case["query"], top_k=int(case["top_k"]))
        assert_retrieval_expectations(case, hits_from_search(hits))


class TestRetrievalNegativeConfidence:
    """Clinical queries must not rank animal-only evidence at the top."""

    @pytest.mark.parametrize(
        "case",
        _EXPECTATIONS.get("retrieval_negative", []),
        ids=lambda c: c["id"],
    )
    def test_clinical_queries_are_not_animal_dominated(
        self, case: dict, require_regression_corpus
    ) -> None:
        hits = semantic_search(query=case["query"], top_k=int(case["top_k"]))
        views = hits_from_search(hits)
        assert views, f"{case['id']}: no results"

        if case.get("must_not_include_source_ids"):
            assert_retrieval_exclusions(case, views)

        if "max_mouse_in_top" not in case and not case.get("top_hit_must_not_be_mouse"):
            return

        top_n = int(case.get("top_n", 3))
        levels = [classify_document(h.document) for h in hits[:top_n]]
        mouse_count = sum(1 for level in levels if level == EvidenceLevel.MOUSE)
        max_mouse = int(case.get("max_mouse_in_top", 0))
        assert mouse_count <= max_mouse, (
            f"{case['id']}: {mouse_count}/{top_n} top hits are mouse/animal "
            f"(max {max_mouse}). Levels: {[level.value for level in levels]}"
        )

        if case.get("top_hit_must_not_be_mouse"):
            assert levels[0] != EvidenceLevel.MOUSE, (
                f"{case['id']}: top hit is animal model: {hits[0].document.title!r}"
            )


class TestTrialsConfidence:
    """Structured trial search must find registry IDs known to matter clinically."""

    @pytest.mark.parametrize("case", _EXPECTATIONS["trials"], ids=lambda c: c["id"])
    def test_query_finds_expected_trials(self, case: dict, require_regression_corpus) -> None:
        trials = list_trials(TrialFilter(query=case["query"], limit=int(case["limit"])))
        returned_ids = {t.source_id for t in trials}
        missing = set(case["must_include_source_ids"]) - returned_ids
        assert not missing, (
            f"{case['id']} ({case['scenario']}): missing trials {sorted(missing)}. "
            f"Returned {len(trials)} ids (first 10): {sorted(returned_ids)[:10]}"
        )


class TestCandidateReportConfidence:
    """Deterministic rankings on the regression corpus (priors + graph + trials)."""

    def test_global_top_includes_expected_drugs(self, require_regression_corpus) -> None:
        from vitiligo.reports import build_candidate_report

        spec = _EXPECTATIONS["candidates"]
        report = build_candidate_report(top_n=int(spec["top_n"]))
        tokens = {c.canonical_token for c in report.global_top}
        missing = set(spec["must_include_tokens"]) - tokens
        assert not missing, (
            f"Candidate report missing expected drugs: {sorted(missing)}. "
            f"Top-{spec['top_n']}: {[(c.rank, c.canonical_token, c.score.total) for c in report.global_top]}"
        )

    def test_rank1_is_ruxolitinib_with_strong_score(self, require_regression_corpus) -> None:
        from vitiligo.reports import build_candidate_report

        spec = _EXPECTATIONS["candidates"]
        report = build_candidate_report(top_n=int(spec["top_n"]))
        assert report.global_top, "empty candidate report"
        rank1 = report.global_top[0]
        assert rank1.canonical_token == spec["rank1_token"], (
            f"rank 1 is {rank1.canonical_token!r}, expected {spec['rank1_token']!r}"
        )
        assert rank1.score.total >= int(spec["min_rank1_score"]), (
            f"rank 1 score {rank1.score.total} below minimum {spec['min_rank1_score']}"
        )


class TestCandidateIntentConfidence:
    """Each research intent must surface intent-relevant drug candidates."""

    @pytest.mark.parametrize(
        "intent_case",
        _EXPECTATIONS["candidate_intents"]["intents"],
        ids=lambda c: c["id"],
    )
    def test_intent_rankings_include_expected_drugs(
        self,
        intent_case: dict,
        require_regression_corpus,
    ) -> None:
        from vitiligo.reports import build_candidate_report

        spec = _EXPECTATIONS["candidate_intents"]
        top_n = int(spec["top_n"])
        report = build_candidate_report(top_n=top_n)
        by_id = {ir.intent.id: ir for ir in report.intents}
        intent_report = by_id.get(intent_case["id"])
        assert intent_report is not None, f"missing intent report {intent_case['id']!r}"

        candidates = intent_report.candidates
        assert candidates, f"{intent_case['id']}: no candidates met threshold"
        tokens = {c.canonical_token for c in candidates}
        missing = set(intent_case["must_include_tokens"]) - tokens
        assert not missing, (
            f"{intent_case['id']} ({intent_case['scenario']}): missing {sorted(missing)}. "
            f"Top-{top_n}: {[(c.rank, c.canonical_token, c.score.total) for c in candidates]}"
        )
        assert candidates[0].canonical_token == intent_case["rank1_token"], (
            f"{intent_case['id']}: rank 1 is {candidates[0].canonical_token!r}, "
            f"expected {intent_case['rank1_token']!r}"
        )

        if primary_lit := intent_case.get("tacrolimus_primary_literature_source_id"):
            tac = next((c for c in candidates if c.canonical_token == "tacrolimus"), None)
            assert tac is not None, f"{intent_case['id']}: tacrolimus not in candidate list"
            assert tac.literature_refs, f"{intent_case['id']}: tacrolimus has no literature refs"
            assert tac.literature_refs[0].source_id == primary_lit, (
                f"{intent_case['id']}: tacrolimus top literature {tac.literature_refs[0].source_id!r} "
                f"!= expected {primary_lit!r}"
            )
