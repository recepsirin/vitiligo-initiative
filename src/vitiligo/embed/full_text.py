"""Embed the body of full-text papers, one passage at a time.

``pipeline.py`` embeds title and abstract, which is what search has always
covered. A result reported only in a paper's Results section is therefore
invisible to it, even though the text is in the corpus: PMC records carry the
parsed body in ``raw_metadata["full_text"]``.

This module cuts that body into passages (``chunking.py``) and stores one
vector per passage in ``document_chunks``. Re-running it is cheap: a document
whose text still hashes to what was recorded is skipped, and one whose text
has changed has its old passages replaced rather than added to.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from sqlmodel import Session, and_, delete, select

from vitiligo.embed.chunking import chunk_text
from vitiligo.embed.encoder import DEFAULT_MODEL, get_encoder
from vitiligo.logging import get_logger
from vitiligo.storage import Document, DocumentChunk, init_db, session_scope

logger = get_logger(__name__)

EMBED_SCOPE_FULL_TEXT = "full_text"


@dataclass
class FullTextStats:
    """What a run did."""

    model: str
    documents_embedded: int
    chunks_written: int
    documents_unchanged: int
    documents_without_text: int


def document_full_text(document: Document) -> str:
    """The parsed body a PMC ingest stored, or an empty string."""
    return str((document.raw_metadata or {}).get("full_text") or "")


def text_fingerprint(text: str) -> str:
    """Identifies the exact text a document's passages were cut from."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stored_fingerprints(session: Session, model_name: str) -> dict[int, str]:
    """Each document's recorded source hash, from any one of its passages."""
    rows = session.exec(
        select(DocumentChunk.document_id, DocumentChunk.source_sha256).where(
            DocumentChunk.model == model_name
        )
    ).all()
    return {int(doc_id): str(sha) for doc_id, sha in rows}


def embed_full_text(
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 64,
    limit: int | None = None,
) -> FullTextStats:
    """Chunk and embed every document whose stored body is new or has changed."""
    init_db()
    encoder = get_encoder(model_name=model_name)

    embedded = unchanged = without_text = written = 0
    with session_scope() as session:
        fingerprints = _stored_fingerprints(session, model_name)
        todo: list[tuple[int, str, str]] = []
        for document in session.exec(select(Document)).all():
            text = document_full_text(document)
            if not text.strip():
                without_text += 1
                continue
            fingerprint = text_fingerprint(text)
            if fingerprints.get(int(document.id or 0)) == fingerprint:
                unchanged += 1
                continue
            todo.append((int(document.id or 0), text, fingerprint))
            if limit is not None and len(todo) >= limit:
                break

    logger.info("Full-text embedding: %d document(s) to (re)chunk", len(todo))
    for position, (document_id, text, fingerprint) in enumerate(todo, start=1):
        chunks = chunk_text(text)
        if not chunks:
            without_text += 1
            continue
        vectors: list[np.ndarray] = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors.extend(encoder.encode([c.text for c in batch]))

        # One transaction per document: a long run holds no write lock for more
        # than a moment, and an interrupted one keeps the documents it finished
        # (the fingerprint check skips them next time).
        with session_scope() as session:
            # Replace rather than append: a changed paper must not keep stale passages.
            session.exec(
                delete(DocumentChunk).where(
                    and_(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.model == model_name,
                    )
                )
            )
            for chunk, vector in zip(chunks, vectors, strict=True):
                array = np.asarray(vector, dtype=np.float32)
                session.add(
                    DocumentChunk(
                        document_id=document_id,
                        model=model_name,
                        chunk_index=chunk.index,
                        section=chunk.section,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        source_sha256=fingerprint,
                        dim=int(array.shape[0]),
                        vector=array.tobytes(),
                    )
                )
            session.commit()
        embedded += 1
        written += len(chunks)
        if position % 200 == 0:
            logger.info("Full-text embedding: %d/%d documents", position, len(todo))

    return FullTextStats(
        model=model_name,
        documents_embedded=embedded,
        chunks_written=written,
        documents_unchanged=unchanged,
        documents_without_text=without_text,
    )
