"""Semantic search over the local document store.

Brute-force cosine similarity is fine at our scale (tens of thousands of
docs). Vectors are stored normalized, so cosine reduces to a single
dense matmul. The embedding matrix is cached in-process (see
``vitiligo.embed.cache``) and invalidated when the SQLite file changes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlmodel import select

from vitiligo.embed.cache import get_chunk_index, get_embedding_index
from vitiligo.embed.chunking import snippet as make_snippet
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


MAX_EVIDENCE_PENALTY = max(_EVIDENCE_SCORE_PENALTY.values())


def evidence_adjusted_score(cosine: float, document: Document) -> float:
    """Apply a small penalty for animal/in-vitro papers after cosine similarity."""
    level = classify_document(document)
    return cosine - _EVIDENCE_SCORE_PENALTY.get(level, 0.0)


def shortlist(scores: np.ndarray, top_k: int) -> np.ndarray:
    """Positions that could still reach the top ``top_k`` once the penalty is applied.

    The penalty only ever lowers a score, and never by more than
    ``MAX_EVIDENCE_PENALTY``. So anything scoring below the ``top_k``-th raw
    score minus that penalty cannot overtake it, whatever the penalties turn
    out to be. Ranking the shortlist therefore gives the same answer as
    ranking everything, while loading a handful of documents instead of the
    whole corpus.
    """
    if scores.size == 0:
        return np.empty(0, dtype=np.intp)
    keep = min(top_k, scores.size)
    leaders = np.argpartition(-scores, keep - 1)[:keep]
    cutoff = float(scores[leaders].min()) - MAX_EVIDENCE_PENALTY
    return np.flatnonzero(scores >= cutoff)


@dataclass
class SearchHit:
    document: Document
    score: float
    # Set when the hit came from a passage of the body rather than the abstract.
    section: str | None = None
    snippet: str | None = None


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

    candidates = shortlist(scores, top_k)
    candidate_ids = {index.doc_ids[int(i)] for i in candidates}

    with session_scope() as session:
        documents = {
            d.id: d
            for d in session.exec(
                select(Document).where(Document.id.in_(candidate_ids))  # type: ignore[union-attr]
            ).all()
        }

        ranked: list[tuple[float, float, int]] = []
        for position in candidates:
            i = int(position)
            doc = documents.get(index.doc_ids[i])
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


def search_full_text(
    query: str,
    top_k: int = 10,
    model_name: str = DEFAULT_MODEL,
) -> list[SearchHit]:
    """Search the body of full-text papers, returning one hit per document.

    Each passage is scored, and a document takes the score of its best
    passage. Summing or averaging would reward long papers for their length
    rather than their relevance, and a single telling paragraph is exactly
    what this search exists to find. The passage that won is returned with
    the hit, so an answer can quote it.
    """
    init_db()
    index = get_chunk_index(model_name=model_name)
    if index is None:
        logger.warning(
            "No full-text passages stored for model=%s. Run `vitiligo embed full-text` first.",
            model_name,
        )
        return []

    encoder = get_encoder(model_name=model_name)
    scores = index.matrix @ encoder.encode([query])[0]

    best: dict[int, tuple[float, int]] = {}
    for position, doc_id in enumerate(index.doc_ids):
        score = float(scores[position])
        if doc_id not in best or score > best[doc_id][0]:
            best[doc_id] = (score, position)

    # Same reasoning as semantic_search: rank the few documents that could
    # still place, rather than loading one row per paper in the corpus.
    doc_ids = list(best)
    leaders = shortlist(np.array([best[d][0] for d in doc_ids], dtype=np.float32), top_k)
    best = {doc_ids[int(i)]: best[doc_ids[int(i)]] for i in leaders}

    with session_scope() as session:
        documents = {
            d.id: d
            for d in session.exec(
                select(Document).where(Document.id.in_(list(best)))  # type: ignore[union-attr]
            ).all()
        }

        ranked = []
        for doc_id, (raw, position) in best.items():
            document = documents.get(doc_id)
            if document is None:
                continue
            ranked.append((evidence_adjusted_score(raw, document), raw, doc_id, position))
        ranked.sort(key=lambda item: (-item[0], -item[1]))

        hits: list[SearchHit] = []
        for adjusted, _raw, doc_id, position in ranked[:top_k]:
            document = documents[doc_id]
            section, start, end = index.spans[position]
            body = str((document.raw_metadata or {}).get("full_text") or "")
            hits.append(
                SearchHit(
                    document=document,
                    score=adjusted,
                    section=section,
                    snippet=make_snippet(body, start, end) if body else None,
                )
            )
        return hits
