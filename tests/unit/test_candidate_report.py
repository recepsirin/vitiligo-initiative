"""Tests for evidence-first candidate reports."""

from __future__ import annotations

import pytest

from vitiligo.reports.candidates import (
    IntentSpec,
    ScoreBreakdown,
    _best_stage,
    _evidence_strength,
    _stage_points,
    _trial_points,
    build_candidate_report,
    load_intents,
    normalize_drug_token,
    normalize_stage,
    trial_stage,
)
from vitiligo.storage import Trial, TrialSourceKind, init_db


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


def test_normalize_stage_maps_registry_phases_to_prior_format() -> None:
    assert normalize_stage("PHASE3") == "PHASE_3"
    assert normalize_stage("phase2") == "PHASE_2"
    assert normalize_stage("EARLY_PHASE1") == "EARLY_PHASE_1"
    assert normalize_stage("PHASE_2_3") == "PHASE_2_3"
    assert normalize_stage("NA") == "NA"


def test_trial_stage_collapses_combined_phases() -> None:
    assert trial_stage(["PHASE3"]) == "PHASE_3"
    assert trial_stage(["PHASE2", "PHASE3"]) == "PHASE_2_3"
    assert trial_stage(["PHASE1", "PHASE2"]) == "PHASE_1_2"
    assert trial_stage(["NA"]) is None
    assert trial_stage([]) is None


def test_stage_points_accept_registry_labels() -> None:
    assert _stage_points("PHASE3") == _stage_points("PHASE_3") == 30
    assert _stage_points("EARLY_PHASE1") == _stage_points("EARLY_PHASE_1") == 5


def test_trial_points_credit_registry_phase_format() -> None:
    """CT.gov stores PHASE3 (no underscore); the high-signal bonus must still apply."""
    trial = Trial(
        source=TrialSourceKind.CTGOV,
        source_id="NCT00000003",
        phases=["PHASE3"],
        status="COMPLETED",
        has_results=False,
    )
    assert _trial_points([trial]) == 15


def _scored_trial(source_id: str, phases: list[str], **kwargs: object) -> Trial:
    return Trial(source=TrialSourceKind.CTGOV, source_id=source_id, phases=phases, **kwargs)


def test_trial_points_reward_best_evidence_not_count() -> None:
    """Ten small Phase 1 trials with results must not reach the 35-point cap."""
    many_small = [
        _scored_trial(f"NCT5{i:07d}", ["PHASE1"], has_results=True, status="RECRUITING")
        for i in range(10)
    ]
    # phase 3 + results (not Phase 2+) 5 + active 5 + breadth 5
    assert _trial_points(many_small) == 18


def test_trial_points_full_portfolio() -> None:
    trials = [
        _scored_trial("NCT60000001", ["PHASE3"], status="RECRUITING"),
        _scored_trial("NCT60000002", ["PHASE2"], has_results=True, status="COMPLETED"),
    ]
    # phase 15 + Phase 2+ results 10 + active 5 + breadth 1
    assert _trial_points(trials) == 31


def test_trial_points_phase_2_3_is_not_full_phase_3() -> None:
    assert _trial_points([_scored_trial("NCT70000001", ["PHASE2", "PHASE3"])]) == 10
    assert _trial_points([]) == 0
