"""Lightweight corpus statistics for health checks and monitoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, func, select

from vitiligo.config import get_settings
from vitiligo.storage import Document, Embedding, Prior, Trial, get_engine


def get_corpus_stats() -> dict[str, Any]:
    """Return document/trial/prior/embedding counts for monitoring."""
    settings = get_settings()
    db_path: Path = settings.resolved_db_path
    db_exists = db_path.is_file()
    db_size_mb = round(db_path.stat().st_size / (1024 * 1024), 1) if db_exists else 0.0

    if not db_exists:
        return {
            "database": {
                "path": str(db_path),
                "exists": False,
                "size_mb": 0.0,
            },
            "documents": 0,
            "embeddings": 0,
            "trials": 0,
            "priors": 0,
        }

    with Session(get_engine(), expire_on_commit=False) as session:
        documents = int(session.exec(select(func.count()).select_from(Document)).one() or 0)
        embeddings = int(session.exec(select(func.count()).select_from(Embedding)).one() or 0)
        trials = int(session.exec(select(func.count()).select_from(Trial)).one() or 0)
        priors = int(session.exec(select(func.count()).select_from(Prior)).one() or 0)

    return {
        "database": {
            "path": str(db_path),
            "exists": True,
            "size_mb": db_size_mb,
        },
        "documents": documents,
        "embeddings": embeddings,
        "trials": trials,
        "priors": priors,
    }
