"""In-process cache for the embedding index used by semantic search.

Vectors are loaded from SQLite once per (database file, mtime, model, scope)
and reused for cosine search. No Redis or external cache service — same
process memory as the FastAPI worker.

Invalidate automatically when ``vitiligo.db`` mtime changes (e.g. after
``vitiligo embed run``). Call :func:`clear_embedding_index_cache` in tests
or after swapping ``VITILIGO_DB_PATH``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
from sqlmodel import select

from vitiligo.config import get_settings
from vitiligo.embed.encoder import DEFAULT_MODEL, Encoder
from vitiligo.logging import get_logger
from vitiligo.storage import Embedding, init_db, session_scope

logger = get_logger(__name__)


@dataclass(frozen=True)
class EmbeddingIndex:
    """L2-normalized embedding matrix and parallel document ids."""

    db_path: str
    db_mtime_ns: int
    model_name: str
    scope: str
    matrix: np.ndarray
    doc_ids: list[int]
    dim: int


_cache: EmbeddingIndex | None = None
_lock = threading.Lock()


def _db_fingerprint() -> tuple[str, int]:
    path = get_settings().resolved_db_path
    if not path.is_file():
        return str(path), 0
    return str(path), path.stat().st_mtime_ns


def _load_index(
    *,
    model_name: str,
    scope: str,
    db_path: str,
    db_mtime_ns: int,
) -> EmbeddingIndex | None:
    """Read all embeddings for (model, scope) from SQLite and build a matrix."""
    init_db()
    with session_scope() as session:
        rows = session.exec(
            select(Embedding).where(Embedding.model == model_name, Embedding.scope == scope)
        ).all()

    if not rows:
        return None

    dim = rows[0].dim
    matrix = np.empty((len(rows), dim), dtype=np.float32)
    doc_ids: list[int] = []
    for idx, emb in enumerate(rows):
        matrix[idx] = Encoder.vector_from_bytes(emb.vector, dim)
        doc_ids.append(emb.document_id)

    return EmbeddingIndex(
        db_path=db_path,
        db_mtime_ns=db_mtime_ns,
        model_name=model_name,
        scope=scope,
        matrix=matrix,
        doc_ids=doc_ids,
        dim=dim,
    )


def get_embedding_index(
    model_name: str = DEFAULT_MODEL,
    scope: str = "title_abstract",
) -> EmbeddingIndex | None:
    """Return a cached index, reloading when the DB file or corpus changes."""
    db_path, db_mtime_ns = _db_fingerprint()
    global _cache
    with _lock:
        if (
            _cache is not None
            and _cache.db_path == db_path
            and _cache.db_mtime_ns == db_mtime_ns
            and _cache.model_name == model_name
            and _cache.scope == scope
        ):
            return _cache

        index = _load_index(
            model_name=model_name,
            scope=scope,
            db_path=db_path,
            db_mtime_ns=db_mtime_ns,
        )
        _cache = index
        if index is not None:
            logger.debug(
                "Embedding index loaded: %d vectors model=%s scope=%s",
                len(index.doc_ids),
                model_name,
                scope,
            )
        return index


def warm_embedding_index(
    model_name: str = DEFAULT_MODEL,
    scope: str = "title_abstract",
) -> int:
    """Preload the embedding index (e.g. at web startup). Returns vector count."""
    index = get_embedding_index(model_name=model_name, scope=scope)
    return 0 if index is None else len(index.doc_ids)


def clear_embedding_index_cache() -> None:
    """Drop the in-process index (tests, DB path changes)."""
    global _cache
    with _lock:
        _cache = None
