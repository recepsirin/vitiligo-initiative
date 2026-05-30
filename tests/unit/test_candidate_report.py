"""Tests for evidence-first candidate reports."""

from __future__ import annotations

import pytest

from vitiligo.reports.candidates import (
    IntentSpec,
    ScoreBreakdown,
    _best_stage,
    _evidence_strength,
    _stage_points,
    build_candidate_report,
    load_intents,
    normalize_drug_token,
)
from vitiligo.storage import init_db


def test_normalize_drug_token_stems_formulations() -> None:
    assert normalize_drug_token("Ruxolitinib 1.5% Cream BID") == "ruxolitinib"
    assert normalize_drug_token("POVORCITINIB PHOSPHATE") == "povorcitinib"
    assert normalize_drug_token("Upadacitinib 15 MG") == "upadacitinib"


def test_stage_and_strength_helpers() -> None:
    assert _stage_points("PHASE_3") == 30
    assert _stage_points("UNKNOWN") == 0
    assert _best_stage(["PHASE_2", "PHASE_3"]) == "PHASE_3"


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (70, "strong"),
        (69, "moderate"),
        (45, "moderate"),
        (25, "weak"),
        (24, "speculative"),
    ],
)
def test_evidence_strength_thresholds(score: int, label: str) -> None:
    assert _evidence_strength(score) == label


def test_load_intents_file() -> None:
    from tests.helpers.paths import PROJECT_ROOT

    path = PROJECT_ROOT / "docs" / "candidate-intents.json"
    intents = load_intents(path)
    assert len(intents) >= 5
    assert intents[0].id
    assert intents[0].query


@pytest.mark.corpus
def test_build_candidate_report_on_local_corpus(require_local_corpus) -> None:
    init_db()
    report = build_candidate_report(top_n=5)
    assert report.global_top
    assert report.corpus["documents"] > 0
    assert all(c.score.total > 0 for c in report.global_top)
    assert report.intents
    for ir in report.intents:
        assert isinstance(ir.intent, IntentSpec)
    # Approved JAK inhibitors should pick up registered trials via direct lookup.
    rux = next((c for c in report.global_top if c.canonical_token == "ruxolitinib"), None)
    if rux is not None:
        assert rux.score.trials > 0
        assert rux.trial_refs


def test_normalize_drug_token_empty() -> None:
    assert normalize_drug_token("") == ""


def test_score_breakdown_total() -> None:
    sb = ScoreBreakdown(prior_stage=30, graph=20, trials=10, literature=8)
    assert sb.total == 68


def test_report_to_dict_includes_score_total() -> None:
    from vitiligo.reports.candidates import RankedCandidate, _candidate_dict

    cand = RankedCandidate(
        rank=1,
        name="Test",
        canonical_token="test",
        clinical_stage="PHASE_2",
        evidence_strength="moderate",
        score=ScoreBreakdown(prior_stage=20, graph=10, trials=5, literature=4),
        mechanisms=[],
        prior_source_id=None,
        graph_refs=[],
        trial_refs=[],
        literature_refs=[],
        caveats=[],
    )
    assert _candidate_dict(cand)["score"]["total"] == 39
