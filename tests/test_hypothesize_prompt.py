"""Tests for the Hypothesize prompt builder and JSON coercion.

These tests cover the pure-Python parts of `vitiligo.reasoning.hypothesize`
— building the LLM user prompt from papers + trials, and coercing the
LLM's structured response back into Candidate dataclasses. Together they
guard the trials-into-Hypothesize plumbing without needing a live LLM.
"""

from __future__ import annotations

from vitiligo.embed.search import SearchHit
from vitiligo.reasoning.hypothesize import (
    _build_user_prompt,
    _coerce_candidate,
    _trial_to_citation,
)
from vitiligo.storage.models import Document, SourceKind, Trial, TrialSourceKind


def _doc() -> Document:
    return Document(
        source=SourceKind.PUBMED,
        source_id="123",
        title="Ruxolitinib repigmentation in nonsegmental vitiligo",
        abstract="A randomized trial of topical ruxolitinib for vitiligo.",
        journal="NEJM",
        year=2022,
        publication_types=["RCT"],
    )


def _trial(
    source_id: str = "NCT07533019",
    source: TrialSourceKind = TrialSourceKind.CTGOV,
    status: str = "RECRUITING",
    phases: list[str] | None = None,
    has_results: bool = False,
    summary: str | None = "Investigates LY4005130 in non-segmental vitiligo.",
) -> Trial:
    return Trial(
        source=source,
        source_id=source_id,
        brief_title="LY4005130 in non-segmental vitiligo",
        official_title="A study of LY4005130 in adults",
        summary=summary,
        status=status,
        phases=phases or ["PHASE2"],
        conditions=["Vitiligo"],
        keywords=[],
        interventions=[{"type": "DRUG", "name": "LY4005130", "description": None, "other_names": []}],
        sponsors=[{"role": "lead", "name": "Eli Lilly", "class": "Pharmaceutical company"}],
        countries=["United States", "Netherlands"],
        primary_outcomes=[],
        secondary_outcomes=[],
        has_results=has_results,
    )


def test_user_prompt_lists_papers_and_trials_separately() -> None:
    hit = SearchHit(document=_doc(), score=0.91)
    trial = _trial()
    prompt = _build_user_prompt(intent="stop spread", hits=[hit], trials=[trial])

    assert "RESEARCH INTENT: stop spread" in prompt
    assert "RETRIEVED PAPERS:" in prompt
    assert "[1] Ruxolitinib repigmentation in nonsegmental vitiligo" in prompt
    assert "REGISTERED CLINICAL TRIALS:" in prompt
    assert "[T1] ctgov:NCT07533019" in prompt
    assert "Status: RECRUITING" in prompt
    assert "Phase: PHASE2" in prompt
    assert "Sponsors: Eli Lilly" in prompt
    assert "Interventions: LY4005130" in prompt


def test_user_prompt_handles_no_trials() -> None:
    hit = SearchHit(document=_doc(), score=0.91)
    prompt = _build_user_prompt(intent="repigmentation", hits=[hit], trials=[])
    assert "REGISTERED CLINICAL TRIALS: (none retrieved for this intent)" in prompt


def test_user_prompt_truncates_long_trial_summary() -> None:
    long_summary = "x" * 1500
    trial = _trial(summary=long_summary)
    prompt = _build_user_prompt(
        intent="anything",
        hits=[SearchHit(document=_doc(), score=0.5)],
        trials=[trial],
    )
    assert " ..." in prompt
    # Make sure the verbatim 1500-character blob is NOT in the prompt.
    assert long_summary not in prompt


def test_trial_to_citation_extracts_metadata() -> None:
    citation = _trial_to_citation(3, _trial(has_results=True))
    assert citation.index == 3
    assert citation.source == "ctgov"
    assert citation.source_id == "NCT07533019"
    assert citation.title == "LY4005130 in non-segmental vitiligo"
    assert citation.has_results is True
    assert citation.sponsors == ["Eli Lilly"]
    assert "Netherlands" in citation.countries


def test_coerce_candidate_handles_both_index_lists() -> None:
    candidate = _coerce_candidate(
        {
            "name": "ruxolitinib",
            "kind": "drug",
            "mechanism": "JAK1/2 inhibition",
            "rationale": "Repigmentation per RCT",
            "evidence_strength": "Strong",
            "risks_or_caveats": "Black-box safety",
            "citation_indices": [1, "[3]"],
            "trial_citation_indices": ["T2", 5],
        }
    )
    assert candidate.name == "ruxolitinib"
    # Evidence strength is canonicalized to lowercase.
    assert candidate.evidence_strength == "strong"
    # Both bracketed and T-prefixed forms are tolerated.
    assert candidate.citation_indices == [1, 3]
    assert candidate.trial_citation_indices == [2, 5]


def test_coerce_candidate_drops_invalid_indices() -> None:
    candidate = _coerce_candidate(
        {
            "name": "x",
            "citation_indices": ["abc", None, 7, {"nope": True}],
            "trial_citation_indices": "not-a-list",
        }
    )
    assert candidate.citation_indices == [7]
    assert candidate.trial_citation_indices == []
