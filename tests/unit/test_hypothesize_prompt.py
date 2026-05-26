"""Tests for the Hypothesize prompt builder and JSON coercion.

These tests cover the pure-Python parts of `vitiligo.reasoning.hypothesize`
— building the LLM user prompt from papers + trials, and coercing the
LLM's structured response back into Candidate dataclasses. Together they
guard the trials-into-Hypothesize plumbing without needing a live LLM.
"""

from __future__ import annotations

from vitiligo.embed.search import SearchHit
from vitiligo.graph.query import GraphEdgeView
from vitiligo.reasoning.hypothesize import (
    _build_user_prompt,
    _coerce_candidate,
    _graph_to_citation,
    _prior_to_citation,
    _trial_to_citation,
)
from vitiligo.storage.models import (
    Document,
    Prior,
    PriorKind,
    PriorSourceKind,
    SourceKind,
    Trial,
    TrialSourceKind,
)


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
        study_type="INTERVENTIONAL",
        conditions=["Vitiligo"],
        keywords=[],
        interventions=[
            {"type": "DRUG", "name": "LY4005130", "description": None, "other_names": []}
        ],
        sponsors=[{"role": "lead", "name": "Eli Lilly", "class": "Pharmaceutical company"}],
        countries=["United States", "Netherlands"],
        primary_outcomes=[],
        secondary_outcomes=[],
        has_results=has_results,
    )


def _prior(
    kind: PriorKind = PriorKind.DRUG,
    source_id: str = "CHEMBL1789941",
    name: str = "RUXOLITINIB",
    clinical_stage: str | None = "APPROVAL",
    score: float | None = None,
) -> Prior:
    return Prior(
        source=PriorSourceKind.OPENTARGETS,
        kind=kind,
        source_id=source_id,
        disease_id="EFO_0004208",
        name=name,
        clinical_stage=clinical_stage,
        score=score,
        mechanisms=[{"mechanism": "JAK1 inhibitor", "targets": [{"id": "ENSG00000162434"}]}]
        if kind == PriorKind.DRUG
        else [],
        linked_trial_ids=["nct03099304"] if kind == PriorKind.DRUG else [],
        linked_target_ids=["ENSG00000162434"] if kind == PriorKind.DRUG else [source_id],
        description="Janus kinase 1" if kind == PriorKind.TARGET else None,
    )


def test_user_prompt_lists_papers_and_trials_separately() -> None:
    hit = SearchHit(document=_doc(), score=0.91)
    trial = _trial()
    prompt = _build_user_prompt(
        intent="stop spread", hits=[hit], trials=[trial], priors=[], graph_edges=[]
    )

    assert "RESEARCH INTENT: stop spread" in prompt
    assert "RETRIEVED PAPERS:" in prompt
    assert "[1] Ruxolitinib repigmentation in nonsegmental vitiligo" in prompt
    assert "REGISTERED CLINICAL TRIALS:" in prompt
    assert "[T1] ctgov:NCT07533019" in prompt
    assert "Status: RECRUITING" in prompt
    assert "Evidence: Clinical trial" in prompt
    assert "Phase: PHASE2" in prompt
    assert "Sponsors: Eli Lilly" in prompt
    assert "Interventions: LY4005130" in prompt
    assert (
        "DRUG & TARGET PRIORS: (none — run `vitiligo ingest opentargets` or `vitiligo ingest drugbank`)"
        in prompt
    )


def test_user_prompt_lists_priors() -> None:
    hit = SearchHit(document=_doc(), score=0.91)
    drug = _prior(kind=PriorKind.DRUG)
    target = _prior(
        kind=PriorKind.TARGET,
        source_id="ENSG00000162434",
        name="JAK1",
        clinical_stage=None,
        score=0.72,
    )
    prompt = _build_user_prompt(
        intent="repigmentation",
        hits=[hit],
        trials=[],
        priors=[drug, target],
        graph_edges=[],
    )
    assert "DRUG & TARGET PRIORS (Open Targets + DrugBank):" in prompt
    assert "[P1] DRUG RUXOLITINIB (opentargets:CHEMBL1789941)" in prompt
    assert "Clinical stage: APPROVAL" in prompt
    assert "[P2] TARGET JAK1 (opentargets:ENSG00000162434)" in prompt
    assert "Association score: 0.72" in prompt


def test_user_prompt_handles_no_trials() -> None:
    hit = SearchHit(document=_doc(), score=0.91)
    prompt = _build_user_prompt(
        intent="repigmentation", hits=[hit], trials=[], priors=[], graph_edges=[]
    )
    assert "REGISTERED CLINICAL TRIALS: (none retrieved for this intent)" in prompt


def test_user_prompt_truncates_long_trial_summary() -> None:
    long_summary = "x" * 1500
    trial = _trial(summary=long_summary)
    prompt = _build_user_prompt(
        intent="anything",
        hits=[SearchHit(document=_doc(), score=0.5)],
        trials=[trial],
        priors=[],
        graph_edges=[],
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
    assert citation.evidence_level == "clinical_trial"
    assert citation.evidence_level_label == "Clinical trial"
    assert "Netherlands" in citation.countries


def test_prior_to_citation_extracts_metadata() -> None:
    citation = _prior_to_citation(2, _prior())
    assert citation.index == 2
    assert citation.kind == "drug"
    assert citation.source == "opentargets"
    assert citation.source_id == "CHEMBL1789941"
    assert citation.clinical_stage == "APPROVAL"
    assert "JAK1 inhibitor" in citation.mechanisms
    assert "nct03099304" in citation.linked_trial_ids


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
            "prior_citation_indices": ["P1", 3],
            "graph_citation_indices": ["G2", 4],
        }
    )
    assert candidate.name == "ruxolitinib"
    # Evidence strength is canonicalized to lowercase.
    assert candidate.evidence_strength == "strong"
    # Both bracketed and T-prefixed forms are tolerated.
    assert candidate.citation_indices == [1, 3]
    assert candidate.trial_citation_indices == [2, 5]
    assert candidate.prior_citation_indices == [1, 3]
    assert candidate.graph_citation_indices == [2, 4]


def test_user_prompt_lists_graph_edges() -> None:
    hit = SearchHit(document=_doc(), score=0.91)
    edge = GraphEdgeView(
        id=1,
        subject_kind="drug",
        subject_name="RUXOLITINIB",
        subject_key="ruxolitinib",
        predicate="treats",
        object_kind="disease",
        object_name="Vitiligo",
        object_key="vitiligo",
        confidence=0.88,
        extraction_method="structured",
        evidence_count=1,
    )
    prompt = _build_user_prompt(
        intent="repigmentation", hits=[hit], trials=[], priors=[], graph_edges=[edge]
    )
    assert "KNOWLEDGE GRAPH (vitiligo-connected relations):" in prompt
    assert "[G1] RUXOLITINIB (drug) —[treats]→ Vitiligo (disease)" in prompt


def test_graph_to_citation() -> None:
    edge = GraphEdgeView(
        id=7,
        subject_kind="target",
        subject_name="JAK1",
        subject_key="jak1",
        predicate="associated_with",
        object_kind="disease",
        object_name="Vitiligo",
        object_key="vitiligo",
        confidence=0.72,
        extraction_method="structured",
        evidence_count=2,
    )
    citation = _graph_to_citation(2, edge)
    assert citation.index == 2
    assert citation.subject_name == "JAK1"
    assert citation.evidence_count == 2


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
    assert candidate.prior_citation_indices == []
    assert candidate.graph_citation_indices == []
