"""Tests for the in-process embedding index cache."""

from __future__ import annotations

import numpy as np
from sqlmodel import Session

from vitiligo.embed.cache import clear_embedding_index_cache, get_embedding_index
from vitiligo.embed.encoder import DEFAULT_MODEL, Encoder
from vitiligo.embed.search import semantic_search
from vitiligo.storage import Document, Embedding, SourceKind, get_engine, init_db


def _seed_two_embedded_papers(test_db_path) -> None:
    init_db()
    texts = [
        ("pmid1", "JAK inhibitors for vitiligo repigmentation", "Clinical trial of tofacitinib."),
        (
            "pmid2",
            "Mouse model of vitiligo depigmentation",
            "C57BL/6 mice with vitiligo-like lesions.",
        ),
    ]
    encoder = Encoder()
    vectors = encoder.encode([t[2] for t in texts])

    with Session(get_engine(), expire_on_commit=False) as session:
        for (source_id, title, abstract), vec in zip(texts, vectors, strict=True):
            doc = Document(
                source=SourceKind.PUBMED,
                source_id=source_id,
                title=title,
                abstract=abstract,
            )
            session.add(doc)
            session.flush()
            session.add(
                Embedding(
                    document_id=doc.id,  # type: ignore[arg-type]
                    model=DEFAULT_MODEL,
                    scope="title_abstract",
                    dim=encoder.dim,
                    vector=Encoder.vector_to_bytes(vec),
                )
            )
        session.commit()


def test_semantic_search_stable_across_cached_calls(test_db_path) -> None:
    _seed_two_embedded_papers(test_db_path)
    first = semantic_search(query="vitiligo JAK repigmentation", top_k=5)
    second = semantic_search(query="vitiligo JAK repigmentation", top_k=5)
    assert [h.document.source_id for h in first] == [h.document.source_id for h in second]
    assert [h.score for h in first] == [h.score for h in second]


def test_embedding_index_reloads_when_db_changes(test_db_path) -> None:
    _seed_two_embedded_papers(test_db_path)
    semantic_search(query="vitiligo", top_k=5)
    index_before = get_embedding_index()
    assert index_before is not None
    assert len(index_before.doc_ids) == 2

    encoder = Encoder()
    vec = encoder.encode(["narrowband UVB phototherapy vitiligo"])[0]
    with Session(get_engine(), expire_on_commit=False) as session:
        doc = Document(
            source=SourceKind.PUBMED,
            source_id="pmid3",
            title="NB-UVB for vitiligo",
            abstract="Phototherapy trial in patients.",
            publication_types=["Clinical Trial"],
        )
        session.add(doc)
        session.flush()
        session.add(
            Embedding(
                document_id=doc.id,  # type: ignore[arg-type]
                model=DEFAULT_MODEL,
                scope="title_abstract",
                dim=encoder.dim,
                vector=Encoder.vector_to_bytes(vec),
            )
        )
        session.commit()

    index_after = get_embedding_index()
    assert index_after is not None
    assert index_after is not index_before
    assert len(index_after.doc_ids) == 3

    hits = semantic_search(query="NB-UVB phototherapy", top_k=3)
    assert any(h.document.source_id == "pmid3" for h in hits)


def test_clear_embedding_index_cache_forces_reload(test_db_path) -> None:
    _seed_two_embedded_papers(test_db_path)
    before = get_embedding_index()
    assert before is not None
    old_matrix = before.matrix
    clear_embedding_index_cache()
    after = get_embedding_index()
    assert after is not None
    assert len(after.doc_ids) == 2
    assert not np.shares_memory(old_matrix, after.matrix)
