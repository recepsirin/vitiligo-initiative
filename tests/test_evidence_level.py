"""Tests for evidence-level classification."""

from __future__ import annotations

from vitiligo.evidence.level import (
    EvidenceLevel,
    classify_document,
    classify_trial,
    evidence_level_label,
)
from vitiligo.storage.models import Document, SourceKind, Trial, TrialSourceKind


def test_classify_rct_from_publication_type() -> None:
    doc = Document(
        source=SourceKind.PUBMED,
        source_id="1",
        title="Topical ruxolitinib for vitiligo",
        publication_types=["Randomized Controlled Trial", "Journal Article"],
    )
    assert classify_document(doc) == EvidenceLevel.RCT


def test_classify_meta_analysis() -> None:
    doc = Document(
        source=SourceKind.PUBMED,
        source_id="2",
        title="JAK inhibitors in vitiligo",
        publication_types=["Meta-Analysis", "Journal Article"],
    )
    assert classify_document(doc) == EvidenceLevel.META_ANALYSIS


def test_classify_mouse_from_mesh() -> None:
    doc = Document(
        source=SourceKind.PUBMED,
        source_id="3",
        title="Depigmentation in C57BL/6 mice",
        publication_types=["Journal Article"],
        mesh_terms=["Mice", "Disease Models, Animal"],
        abstract="We induced vitiligo-like depigmentation in mice.",
    )
    assert classify_document(doc) == EvidenceLevel.MOUSE


def test_classify_case_report() -> None:
    doc = Document(
        source=SourceKind.PUBMED,
        source_id="4",
        title="Unexpected repigmentation",
        publication_types=["Case Reports"],
    )
    assert classify_document(doc) == EvidenceLevel.CASE_REPORT


def test_classify_interventional_trial() -> None:
    trial = Trial(
        source=TrialSourceKind.CTGOV,
        source_id="NCT00000001",
        study_type="INTERVENTIONAL",
        phases=["PHASE3"],
    )
    assert classify_trial(trial) == EvidenceLevel.CLINICAL_TRIAL


def test_evidence_level_label() -> None:
    assert evidence_level_label(EvidenceLevel.RCT) == "RCT"
    assert evidence_level_label("mouse") == "Mouse / animal"
