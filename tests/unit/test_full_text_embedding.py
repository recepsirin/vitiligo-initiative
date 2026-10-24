"""Tests for embedding paper bodies and searching them.

These use a temporary SQLite file and a fake encoder, so no model is loaded.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.embed.cache import clear_embedding_index_cache, get_chunk_index
from vitiligo.embed.full_text import (
    document_full_text,
    embed_full_text,
    text_fingerprint,
)
from vitiligo.storage import Document, DocumentChunk, SourceKind, init_db, session_scope

BODY = (
    "## Introduction\n\n"
    + ("Vitiligo is an autoimmune disease of the skin. " * 12)
    + "\n\n## Results\n\n"
    + ("F-VASI75 was reached by fourteen of thirty-eight patients at week 52. " * 12)
)


class FakeEncoder:
    """Deterministic vectors: direction depends only on the text, so search is stable."""

    def encode(self, texts: list[str]) -> list[np.ndarray]:
        out = []
        for text in texts:
            vector = np.zeros(8, dtype=np.float32)
            vector[0] = text.lower().count("vasi") + 0.1
            vector[1] = text.lower().count("autoimmune") + 0.1
            vector[2] = len(text) / 1000.0
            out.append(vector / np.linalg.norm(vector))
        return out


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "corpus.db"
    monkeypatch.setenv("VITILIGO_DB_PATH", str(db))
    cfg._settings = None
    dbmod._engine = None
    clear_embedding_index_cache()
    init_db()
    monkeypatch.setattr("vitiligo.embed.full_text.get_encoder", lambda model_name: FakeEncoder())
    yield db
    cfg._settings = None
    dbmod._engine = None
    clear_embedding_index_cache()


def _add(source_id: str, body: str | None, title: str = "A paper") -> None:
    with session_scope() as session:
        session.add(
            Document(
                source=SourceKind.PMC,
                source_id=source_id,
                title=title,
                abstract="Short abstract.",
                raw_metadata={"full_text": body} if body is not None else {},
            )
        )
        session.commit()


def test_document_full_text_reads_the_parsed_body() -> None:
    doc = Document(source=SourceKind.PMC, source_id="PMC1", raw_metadata={"full_text": "body"})
    assert document_full_text(doc) == "body"
    assert document_full_text(Document(source=SourceKind.PMC, source_id="PMC2")) == ""


def test_embedding_writes_one_row_per_passage(corpus: Path) -> None:
    _add("PMC1", BODY)
    stats = embed_full_text()
    assert stats.documents_embedded == 1
    assert stats.chunks_written > 1
    with session_scope() as session:
        chunks = session.exec(select(DocumentChunk)).all()
    assert len(chunks) == stats.chunks_written
    assert {c.chunk_index for c in chunks} == set(range(len(chunks)))
    assert all(c.dim == 8 and len(c.vector) == 8 * 4 for c in chunks)


def test_offsets_still_locate_the_passage_in_the_source(corpus: Path) -> None:
    """The passage text is not stored, so the offsets have to be right."""
    _add("PMC1", BODY)
    embed_full_text()
    with session_scope() as session:
        chunks = session.exec(select(DocumentChunk)).all()
        document = session.exec(select(Document)).one()
    body = document_full_text(document)
    for chunk in chunks:
        assert body[chunk.char_start : chunk.char_end].strip()


def test_documents_without_a_body_are_counted_not_embedded(corpus: Path) -> None:
    _add("PMC1", None)
    _add("PMC2", "   ")
    stats = embed_full_text()
    assert (stats.documents_embedded, stats.documents_without_text) == (0, 2)


def test_rerunning_skips_documents_whose_text_has_not_changed(corpus: Path) -> None:
    _add("PMC1", BODY)
    first = embed_full_text()
    second = embed_full_text()
    assert second.documents_embedded == 0
    assert second.documents_unchanged == 1
    assert second.chunks_written == 0
    with session_scope() as session:
        assert len(session.exec(select(DocumentChunk)).all()) == first.chunks_written


def test_changed_text_replaces_its_passages_rather_than_adding(corpus: Path) -> None:
    """Stale passages would keep pointing at offsets that no longer mean anything."""
    _add("PMC1", BODY)
    embed_full_text()
    with session_scope() as session:
        document = session.exec(select(Document)).one()
        document.raw_metadata = {"full_text": "## Results\n\n" + ("A shorter body. " * 30)}
        session.add(document)
        session.commit()

    stats = embed_full_text()
    assert stats.documents_embedded == 1
    with session_scope() as session:
        chunks = session.exec(select(DocumentChunk)).all()
        document = session.exec(select(Document)).one()
    assert len(chunks) == stats.chunks_written
    expected = text_fingerprint(document_full_text(document))
    assert {c.source_sha256 for c in chunks} == {expected}


def test_limit_caps_the_work(corpus: Path) -> None:
    for i in range(4):
        _add(f"PMC{i}", BODY)
    assert embed_full_text(limit=2).documents_embedded == 2


def test_search_returns_one_hit_per_document_with_its_best_passage(corpus: Path) -> None:
    from vitiligo.embed import search as search_module

    _add("PMC1", BODY, title="Trial report")
    _add("PMC2", "## Introduction\n\n" + ("Unrelated dermatology background. " * 30), "Review")
    embed_full_text()
    clear_embedding_index_cache()

    import vitiligo.embed.search as s

    original = s.get_encoder
    s.get_encoder = lambda model_name: FakeEncoder()  # type: ignore[assignment]
    try:
        hits = search_module.search_full_text("VASI response rate", top_k=5)
    finally:
        s.get_encoder = original

    assert hits[0].document.source_id == "PMC1"
    assert len({h.document.source_id for h in hits}) == len(hits)  # one hit per document
    top = hits[0]
    assert top.section == "Results"
    assert top.snippet and "VASI" in top.snippet


def test_search_without_any_passages_returns_nothing(corpus: Path) -> None:
    from vitiligo.embed.search import search_full_text

    _add("PMC1", None)
    clear_embedding_index_cache()
    assert search_full_text("anything") == []


def test_chunk_index_is_cached_and_cleared(corpus: Path) -> None:
    _add("PMC1", BODY)
    embed_full_text()
    clear_embedding_index_cache()
    index = get_chunk_index()
    assert index is not None
    assert index.matrix.shape[0] == len(index.doc_ids) == len(index.spans)
    assert get_chunk_index() is index  # served from cache
    clear_embedding_index_cache()
