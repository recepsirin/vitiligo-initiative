"""Storage layer: SQLite-backed document store and ingestion bookkeeping."""

from vitiligo.storage.db import get_engine, init_db, session_scope
from vitiligo.storage.models import Document, Embedding, IngestionRun, SourceKind

__all__ = [
    "Document",
    "Embedding",
    "IngestionRun",
    "SourceKind",
    "get_engine",
    "init_db",
    "session_scope",
]
