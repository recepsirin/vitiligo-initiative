"""Storage layer: SQLite-backed document store and ingestion bookkeeping."""

from vitiligo.storage.db import get_engine, init_db, session_scope
from vitiligo.storage.models import (
    Document,
    DocumentChunk,
    Embedding,
    IngestionRun,
    Prior,
    PriorKind,
    PriorSourceKind,
    SourceKind,
    Trial,
    TrialSourceKind,
)

__all__ = [
    "Document",
    "DocumentChunk",
    "Embedding",
    "IngestionRun",
    "Prior",
    "PriorKind",
    "PriorSourceKind",
    "SourceKind",
    "Trial",
    "TrialSourceKind",
    "get_engine",
    "init_db",
    "session_scope",
]
