"""Integration tests for `vitiligo db repair` on a seeded temp DB."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, select

from vitiligo.ingest.repair import repair_corpus, title_from_excerpt
from vitiligo.storage import Document, Embedding, SourceKind, get_engine

pytestmark = pytest.mark.integration

_EXCERPT = (
    '<PubmedArticle><MedlineCitation><PMID Version="1">111</PMID><Article>'
    "<ArticleTitle>Lactate Enhances CD8<sup>+</sup> T Cell Cytotoxicity.</ArticleTitle>"
    "</Article></MedlineCitation></PubmedArticle>"
)


def _embedding(doc_id: int) -> Embedding:
    return Embedding(document_id=doc_id, model="m", scope="title_abstract", dim=1, vector=b"\0" * 4)


@pytest.fixture
def damaged_corpus(test_db_path: Path) -> dict[str, int]:
    docs = {
        "truncated": Document(
            source=SourceKind.PUBMED,
            source_id="111",
            title="Lactate Enhances CD8",
            raw_metadata={"pmid": "111", "pubmed_xml_excerpt": _EXCERPT},
        ),
        "intact": Document(
            source=SourceKind.PUBMED,
            source_id="222",
            title="Plain title.",
            raw_metadata={
                "pmid": "222",
                "pubmed_xml_excerpt": "<ArticleTitle>Plain title.</ArticleTitle>",
            },
        ),
        "geo_sample": Document(
            source=SourceKind.GEO,
            source_id="GSM9000001",
            title="Sample",
            raw_metadata={"accession": "GSM9000001", "entrytype": "GSM", "uid": "1"},
        ),
        "geo_series": Document(
            source=SourceKind.GEO,
            source_id="GSE326094",
            title="Series",
            raw_metadata={"accession": "GSE326094", "entrytype": "GSE", "uid": "2"},
        ),
    }
    with Session(get_engine(), expire_on_commit=False) as session:
        session.add_all(docs.values())
        session.flush()
        ids = {name: doc.id for name, doc in docs.items()}
        session.add_all(_embedding(doc_id) for doc_id in ids.values() if doc_id is not None)
        session.commit()
    return {name: doc_id for name, doc_id in ids.items() if doc_id is not None}


def _state() -> tuple[dict[str, str | None], set[int]]:
    with Session(get_engine()) as session:
        titles = {d.source_id: d.title for d in session.exec(select(Document)).all()}
        embedded = {e.document_id for e in session.exec(select(Embedding)).all()}
    return titles, embedded


def test_title_from_excerpt() -> None:
    assert title_from_excerpt(_EXCERPT) == "Lactate Enhances CD8+ T Cell Cytotoxicity."
    assert title_from_excerpt("<ArticleTitle>unterminated") is None
    assert title_from_excerpt(None) is None


def test_repair_dry_run_writes_nothing(damaged_corpus: dict[str, int]) -> None:
    before = _state()
    stats = repair_corpus(apply=False)
    assert (stats.pubmed_titles_fixed, stats.geo_documents_removed) == (1, 1)
    assert stats.embeddings_dropped == 0
    assert _state() == before


def test_repair_apply_fixes_titles_and_removes_geo_samples(
    damaged_corpus: dict[str, int],
) -> None:
    stats = repair_corpus(apply=True)
    assert (stats.pubmed_titles_fixed, stats.geo_documents_removed) == (1, 1)
    assert stats.embeddings_dropped == 2  # repaired title + removed GSM document

    titles, embedded = _state()
    assert titles["111"] == "Lactate Enhances CD8+ T Cell Cytotoxicity."
    assert "GSM9000001" not in titles
    assert titles["GSE326094"] == "Series"
    # Untouched documents keep their vectors; the repaired one awaits `embed run`.
    assert embedded == {damaged_corpus["intact"], damaged_corpus["geo_series"]}

    # Idempotent: a second run finds nothing left to fix.
    again = repair_corpus(apply=True)
    assert (again.pubmed_titles_fixed, again.geo_documents_removed) == (0, 0)
