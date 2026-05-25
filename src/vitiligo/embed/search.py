"""Semantic search over the local document store.

Brute-force cosine similarity is fine at our scale (tens of thousands of
docs). Vectors are stored normalized, so cosine reduces to a single
dense matmul.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlmodel import select

from vitiligo.embed.encoder import DEFAULT_MODEL, Encoder
from vitiligo.logging import get_logger
from vitiligo.storage import Document, Embedding, init_db, session_scope

logger = get_logger(__name__)


@dataclass
class SearchHit:
    document: Document
    score: float


def semantic_search(
    query: str,
    top_k: int = 10,
    model_name: str = DEFAULT_MODEL,
    scope: str = "title_abstract",
) -> list[SearchHit]:
    """Return the top-k documents matching `query` by cosine similarity."""
    init_db()

    with session_scope() as session:
        rows = session.exec(
            select(Embedding).where(Embedding.model == model_name, Embedding.scope == scope)
        ).all()

        if not rows:
            logger.warning(
                "No embeddings stored for model=%s scope=%s. Run `vitiligo embed run` first.",
                model_name,
                scope,
            )
            return []

        dim = rows[0].dim
        matrix = np.empty((len(rows), dim), dtype=np.float32)
        doc_ids: list[int] = []
        for idx, emb in enumerate(rows):
            matrix[idx] = Encoder.vector_from_bytes(emb.vector, dim)
            doc_ids.append(emb.document_id)

        encoder = Encoder(model_name=model_name)
        query_vec = encoder.encode([query])[0]

        scores = matrix @ query_vec  # all vectors are L2-normalized
        top_idx = np.argsort(-scores)[:top_k]

        documents = {
            d.id: d
            for d in session.exec(
                select(Document).where(Document.id.in_([doc_ids[i] for i in top_idx]))
            ).all()  # type: ignore[union-attr]
        }
        hits: list[SearchHit] = []
        for i in top_idx:
            doc = documents.get(doc_ids[i])
            if doc is None:
                continue
            hits.append(SearchHit(document=doc, score=float(scores[i])))
        return hits
