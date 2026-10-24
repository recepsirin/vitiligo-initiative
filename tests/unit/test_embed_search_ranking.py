"""Unit tests for evidence-aware semantic search ranking."""

from __future__ import annotations

import numpy as np

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


# --------------------------------------------------------------- shortlisting


def test_shortlist_keeps_at_least_the_top_k() -> None:
    from vitiligo.embed.search import shortlist

    scores = np.array([0.9, 0.1, 0.5, 0.7, 0.2], dtype=np.float32)
    keep = shortlist(scores, 2)
    assert {0, 3} <= set(keep.tolist())


def test_shortlist_of_nothing_is_empty() -> None:
    from vitiligo.embed.search import shortlist

    assert shortlist(np.array([], dtype=np.float32), 5).size == 0


def test_shortlist_handles_top_k_larger_than_the_corpus() -> None:
    from vitiligo.embed.search import shortlist

    scores = np.array([0.4, 0.8], dtype=np.float32)
    assert sorted(shortlist(scores, 50).tolist()) == [0, 1]


def test_shortlist_cannot_drop_a_document_that_would_have_placed() -> None:
    """The whole point: ranking the shortlist must equal ranking everything.

    Penalties only lower a score, so anything below (k-th raw score - max
    penalty) cannot overtake the k-th. This checks that on random data with
    randomly assigned penalties.
    """
    from vitiligo.embed.search import MAX_EVIDENCE_PENALTY, shortlist

    rng = np.random.default_rng(20261024)
    for _ in range(200):
        scores = rng.random(60).astype(np.float32)
        penalties = rng.choice([0.0, 0.05, MAX_EVIDENCE_PENALTY], size=60)
        top_k = int(rng.integers(1, 10))

        adjusted = scores - penalties
        full = sorted(range(60), key=lambda i: (-adjusted[i], -scores[i]))[:top_k]

        keep = shortlist(scores, top_k).tolist()
        partial = sorted(keep, key=lambda i: (-adjusted[i], -scores[i]))[:top_k]
        assert partial == full
