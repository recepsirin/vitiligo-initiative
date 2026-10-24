"""Storage layer: SQLite-backed document store and ingestion bookkeeping."""

from vitiligo.storage.db import get_engine, init_db, session_scope
from vitiligo.storage.models import (
    ClaimKind,
    Document,
    DocumentChunk,
    Embedding,
    GeneticAssociation,
    GeneticSourceKind,
    IngestionRun,
    Prior,
    PriorKind,
    PriorSourceKind,
    ResearchProject,
    ResearchSourceKind,
    SourceKind,
    Trial,
    TrialSourceKind,
)

__all__ = [
    "ClaimKind",
    "Document",
    "DocumentChunk",
    "Embedding",
    "GeneticAssociation",
    "GeneticSourceKind",
    "IngestionRun",
    "Prior",
    "PriorKind",
    "PriorSourceKind",
    "ResearchProject",
    "ResearchSourceKind",
    "SourceKind",
    "Trial",
    "TrialSourceKind",
    "get_engine",
    "init_db",
    "session_scope",
]
