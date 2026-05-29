"""Semantic search over the local document store.

Brute-force cosine similarity is fine at our scale (tens of thousands of
docs). Vectors are stored normalized, so cosine reduces to a single
dense matmul. The embedding matrix is cached in-process (see
``vitiligo.embed.cache``) and invalidated when the SQLite file changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import select

from vitiligo.embed.cache import get_embedding_index
from vitiligo.embed.encoder import DEFAULT_MODEL, get_encoder
from vitiligo.evidence import EvidenceLevel, classify_document
from vitiligo.logging import get_logger
from vitiligo.storage import Document, init_db, session_scope

logger = get_logger(__name__)

# Subtracted from cosine similarity so preclinical hits rank below human clinical
# evidence when embeddings are similarly relevant.
_EVIDENCE_SCORE_PENALTY: dict[EvidenceLevel, float] = {
    EvidenceLevel.MOUSE: 0.08,
    EvidenceLevel.IN_VITRO: 0.05,
}


def evidence_adjusted_score(cosine: float, document: Document) -> float:
    """Apply a small penalty for animal/in-vitro papers after cosine similarity."""
    level = classify_document(document)
    return cosine - _EVIDENCE_SCORE_PENALTY.get(level, 0.0)


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

    index = get_embedding_index(model_name=model_name, scope=scope)
    if index is None:
        logger.warning(
            "No embeddings stored for model=%s scope=%s. Run `vitiligo embed run` first.",
            model_name,
            scope,
        )
        return []

    encoder = get_encoder(model_name=model_name)
    query_vec = encoder.encode([query])[0]
    scores = index.matrix @ query_vec

    with session_scope() as session:
        documents = {
            d.id: d
            for d in session.exec(
                select(Document).where(Document.id.in_(index.doc_ids))  # type: ignore[union-attr]
            ).all()
        }

        ranked: list[tuple[float, float, int]] = []
        for i, doc_id in enumerate(index.doc_ids):
            doc = documents.get(doc_id)
            if doc is None:
                continue
            raw = float(scores[i])
            adjusted = evidence_adjusted_score(raw, doc)
            ranked.append((adjusted, raw, i))

        ranked.sort(key=lambda item: (-item[0], -item[1]))
        top_ranked = ranked[:top_k]

        hits: list[SearchHit] = []
        for adjusted, _raw, i in top_ranked:
            doc = documents.get(index.doc_ids[i])
            if doc is None:
                continue
            hits.append(SearchHit(document=doc, score=adjusted))
        return hits
