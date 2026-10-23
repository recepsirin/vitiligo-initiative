"""Tests for evidence-first candidate reports."""

from __future__ import annotations

import pytest

from vitiligo.embed.search import SearchHit
from vitiligo.graph.query import GraphEdgeView
from vitiligo.reports.candidates import (
    IntentSpec,
    ScoreBreakdown,
    _best_stage,
    _evidence_strength,
    _graph_points,
    _literature_for_drug,
    _literature_points,
    _stage_points,
    _trial_points,
    build_candidate_report,
    load_intents,
    normalize_drug_token,
    normalize_stage,
    trial_stage,
)
from vitiligo.storage import Document, SourceKind, Trial, TrialSourceKind, init_db


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


def test_load_intents_packaged_default() -> None:
    """Defaults load from package data, not a repo-relative docs/ path."""
    intents = load_intents()
    assert len(intents) >= 5
    assert intents[0].id
    assert intents[0].query


def test_load_intents_explicit_path(tmp_path) -> None:
    path = tmp_path / "intents.json"
    path.write_text('{"intents": [{"id": "x", "title": "X", "query": "ruxolitinib"}]}')
    [intent] = load_intents(path)
    assert (intent.id, intent.query, intent.goal) == ("x", "ruxolitinib", "general")


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


def test_markdown_shows_full_cards_once_and_intent_tables() -> None:
    from vitiligo.reports.candidates import (
        CandidateReport,
        IntentReport,
        LiteratureRef,
        RankedCandidate,
        render_candidate_report_markdown,
    )

    def cand(rank: int, name: str, paper: str | None) -> RankedCandidate:
        refs = [LiteratureRef(1, "pubmed", "1", paper, 2024, "RCT", 0.9)] if paper else []
        return RankedCandidate(
            rank=rank, name=name, canonical_token=name.lower(), clinical_stage="PHASE_3",
            evidence_strength="strong", score=ScoreBreakdown(30, 22, 35, 10), mechanisms=[],
            prior_source_id=None, graph_refs=[], trial_refs=[], literature_refs=refs,
            caveats=[], llm_rationale="Plausible." if rank == 1 else None,
        )  # fmt: skip

    intent = IntentSpec(id="x", title="Spread", query="q", goal="g")
    report = CandidateReport(
        generated_at="t", engine_version="1", methodology="m", corpus={},
        intents=[IntentReport(intent, [cand(1, "ALPHA", "A | B trial"), cand(2, "BETA", None)])],
        global_top=[cand(1, "ALPHA", "A | B trial"), cand(2, "BETA", None)],
    )  # fmt: skip
    md = render_candidate_report_markdown(report)
    assert md.count("### #1 ALPHA") == 1  # the full card appears once, in the global top
    assert "| 1 | ALPHA | 97 | 30 | 22 | 35 | 10 | [pubmed:1] A / B trial (2024) |" in md
    assert "| 2 | BETA | 97 | 30 | 22 | 35 | 10 | — |" in md
    assert "- **#1 ALPHA:** Plausible." in md


def _edge(edge_id: int, method: str, predicate: str = "treats") -> GraphEdgeView:
    return GraphEdgeView(
        id=edge_id,
        subject_kind="drug",
        subject_name="ruxolitinib",
        subject_key="ruxolitinib",
        predicate=predicate,
        object_kind="disease",
        object_name="Vitiligo",
        object_key="vitiligo",
        confidence=0.88,
        extraction_method=method,
        evidence_count=1,
    )


def test_graph_points_skip_edges_seeded_from_priors_and_trials() -> None:
    """Seeded edges restate the prior and trial components; scoring them double-counts."""
    assert _graph_points([_edge(1, "structured"), _edge(2, "structured", "investigates")]) == 0
    assert _graph_points([_edge(3, "llm")]) == 22


def test_graph_points_count_an_edge_once() -> None:
    assert _graph_points([_edge(3, "llm"), _edge(3, "llm")]) == 22


def test_literature_counts_a_pubmed_and_pmc_record_of_one_paper_once() -> None:
    title = "Repigmentation by body region with ruxolitinib cream"
    pmc = Document(
        source=SourceKind.PMC,
        source_id="PMC11851260",
        title=title,
        raw_metadata={"pmid": "39011655"},
    )
    pubmed = Document(source=SourceKind.PUBMED, source_id="39011655", title=title)
    other = Document(source=SourceKind.PMC, source_id="PMC1", title=f"{title} II")
    hits = [SearchHit(pmc, 0.90), SearchHit(pubmed, 0.89), SearchHit(other, 0.80)]
    refs = _literature_for_drug("ruxolitinib", hits)
    assert [(r.source_id, r.rank) for r in refs] == [("PMC11851260", 1), ("PMC1", 3)]
    assert _literature_points(refs) == 8
