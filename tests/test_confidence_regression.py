"""Confidence regression tests — curated research scenarios with expected outcomes.

These assert the engine returns **the right evidence** for real vitiligo
research questions. They run against the minimal regression corpus built from
``tests/fixtures/regression/*.json`` (CI + local).

Run: ``pytest -m confidence``
Build corpus: ``python scripts/test/build_regression_db.py``
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vitiligo.embed import semantic_search
from vitiligo.evidence import EvidenceLevel, classify_document
from vitiligo.trials import TrialFilter, list_trials

MANIFEST = Path(__file__).resolve().parent / "fixtures" / "regression_expectations.json"
_EXPECTATIONS = json.loads(MANIFEST.read_text())

pytestmark = pytest.mark.confidence


class TestRetrievalConfidence:
    """Semantic search must surface known pivotal papers for expert queries."""

    @pytest.mark.parametrize("case", _EXPECTATIONS["retrieval"], ids=lambda c: c["id"])
    def test_query_returns_expected_papers(self, case: dict, require_regression_corpus) -> None:
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

        if expected_top := case.get("expected_top_source_id"):
            assert top.document.source_id == expected_top, (
                f"{case['id']}: top hit {top.document.source_id} != expected {expected_top} "
                f"({top.document.title!r})"
            )


class TestRetrievalNegativeConfidence:
    """Clinical queries must not rank animal-only evidence at the top."""

    @pytest.mark.parametrize(
        "case",
        _EXPECTATIONS.get("retrieval_negative", []),
        ids=lambda c: c["id"],
    )
    def test_clinical_queries_are_not_animal_dominated(self, case: dict, require_regression_corpus) -> None:
        hits = semantic_search(query=case["query"], top_k=int(case["top_k"]))
        assert hits, f"{case['id']}: no results"

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
        trials = list_trials(
            TrialFilter(query=case["query"], limit=int(case["limit"]))
        )
        returned_ids = {t.source_id for t in trials}
        missing = set(case["must_include_source_ids"]) - returned_ids
        assert not missing, (
            f"{case['id']} ({case['scenario']}): missing trials {sorted(missing)}. "
            f"Returned {len(trials)} ids (first 10): {sorted(returned_ids)[:10]}"
        )
