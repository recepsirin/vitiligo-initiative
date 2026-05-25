"""Embed documents from the store and persist their vectors."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, and_, select

from vitiligo.embed.encoder import DEFAULT_MODEL, Encoder
from vitiligo.logging import get_logger
from vitiligo.storage import Document, Embedding, init_db, session_scope

logger = get_logger(__name__)

EMBED_SCOPE_TITLE_ABSTRACT = "title_abstract"


@dataclass
class EmbeddingStats:
    model: str
    scope: str
    embedded: int
    skipped_no_text: int


def _document_text(doc: Document) -> str:
    """Compose the text we embed at scope=title_abstract.

    Models like BGE benefit from a short, focused passage. Title +
    abstract is the standard biomedical retrieval target.
    """
    parts: list[str] = []
    if doc.title:
        parts.append(doc.title.strip())
    if doc.abstract:
        parts.append(doc.abstract.strip())
    return "\n\n".join(parts).strip()


def embed_documents(
    model_name: str = DEFAULT_MODEL,
    scope: str = EMBED_SCOPE_TITLE_ABSTRACT,
    batch_size: int = 64,
    limit: int | None = None,
) -> EmbeddingStats:
    """Encode every document that doesn't yet have an embedding for (model, scope)."""
    init_db()
    encoder = Encoder(model_name=model_name)

    embedded = 0
    skipped = 0

    with session_scope() as session:
        pending = _select_pending(session, model_name=model_name, scope=scope, limit=limit)
        logger.info(
            "Embedding %d document(s) [model=%s scope=%s]",
            len(pending),
            model_name,
            scope,
        )

        for chunk_start in range(0, len(pending), batch_size):
            chunk = pending[chunk_start : chunk_start + batch_size]
            texts: list[str] = []
            chunk_docs: list[Document] = []
            for doc in chunk:
                text = _document_text(doc)
                if not text:
                    skipped += 1
                    continue
                texts.append(text)
                chunk_docs.append(doc)

            if not texts:
                continue

            vectors = encoder.encode(texts, batch_size=batch_size)
            for doc, vec in zip(chunk_docs, vectors, strict=True):
                assert doc.id is not None
                session.add(
                    Embedding(
                        document_id=doc.id,
                        model=model_name,
                        scope=scope,
                        dim=encoder.dim,
                        vector=Encoder.vector_to_bytes(vec),
                    )
                )
                embedded += 1

            session.commit()
            logger.info("Embedded %d / %d", embedded, len(pending))

    return EmbeddingStats(model=model_name, scope=scope, embedded=embedded, skipped_no_text=skipped)


def _select_pending(
    session: Session,
    model_name: str,
    scope: str,
    limit: int | None,
) -> list[Document]:
    """Return documents that don't have an embedding for (model, scope) yet."""
    sub = select(Embedding.document_id).where(
        and_(Embedding.model == model_name, Embedding.scope == scope)
    )
    statement = select(Document).where(Document.id.notin_(sub))  # type: ignore[union-attr]
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.exec(statement).all())
