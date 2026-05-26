"""Unit tests for evidence-aware semantic search ranking."""

from __future__ import annotations

from vitiligo.embed.search import evidence_adjusted_score
from vitiligo.storage import Document, SourceKind


def test_mouse_paper_ranks_below_clinical_paper_at_similar_cosine() -> None:
    mouse = Document(
        source=SourceKind.PUBMED,
        source_id="mouse1",
        title="USP11 in vitiligo mouse model",
        abstract="C57BL/6 mice with H2O2-induced depigmentation.",
        mesh_terms=["Mice", "Animals", "Vitiligo", "Melanocytes"],
    )
    clinical = Document(
        source=SourceKind.PUBMED,
        source_id="human1",
        title="Randomized trial of tacrolimus for vitiligo",
        abstract="Randomized controlled trial in patients with vitiligo.",
        publication_types=["Randomized Controlled Trial", "Clinical Trial"],
        mesh_terms=["Humans", "Vitiligo"],
    )

    mouse_score = evidence_adjusted_score(0.88, mouse)
    clinical_score = evidence_adjusted_score(0.85, clinical)
    assert mouse_score < clinical_score


def test_in_vitro_penalty_is_smaller_than_mouse() -> None:
    in_vitro = Document(
        source=SourceKind.PUBMED,
        source_id="vitro1",
        title="Melanocyte culture oxidative stress",
        abstract="In vitro melanocyte culture under oxidative stress.",
        mesh_terms=["Cells, Cultured", "Melanocytes"],
    )
    mouse = Document(
        source=SourceKind.PUBMED,
        source_id="mouse2",
        title="Vitiligo in mice",
        abstract="Mouse model of vitiligo.",
        mesh_terms=["Mice", "Animals"],
    )

    base = 0.80
    assert evidence_adjusted_score(base, in_vitro) > evidence_adjusted_score(base, mouse)
