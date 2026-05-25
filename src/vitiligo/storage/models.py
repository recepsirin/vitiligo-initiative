"""Data models for the document store.

The schema is intentionally source-agnostic: every source (PubMed today,
PMC / ClinicalTrials.gov / Open Targets later) writes into the same
`documents` table, keyed by (source, source_id). Raw source-specific
metadata is preserved in `raw_metadata` so we can re-derive structured
fields without re-fetching.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, UniqueConstraint


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SourceKind(StrEnum):
    """Known document sources. Extend as new ingestion modules land."""

    PUBMED = "pubmed"
    PMC = "pmc"
    CLINICALTRIALS = "clinicaltrials"
    OPENTARGETS = "opentargets"
    DRUGBANK = "drugbank"


class Document(SQLModel, table=True):
    """A single source document (paper, trial, drug record, etc.)."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_source_source_id"),)

    id: int | None = Field(default=None, primary_key=True)

    source: SourceKind = Field(index=True)
    source_id: str = Field(
        index=True, description="Stable identifier within the source (e.g. PMID)."
    )

    # Common normalized fields. Filled where available; null otherwise.
    title: str | None = Field(default=None)
    abstract: str | None = Field(default=None)
    journal: str | None = Field(default=None)
    year: int | None = Field(default=None, index=True)
    doi: str | None = Field(default=None, index=True)
    language: str | None = Field(default=None)

    # Free-form structured payloads. Sources differ wildly; keep flexibility.
    authors: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    mesh_terms: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    publication_types: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Original source response, kept verbatim for re-parsing and auditability.
    raw_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    retrieved_at: datetime = Field(default_factory=_utcnow, index=True)


class IngestionRun(SQLModel, table=True):
    """Bookkeeping for a single ingestion run, so we can resume and audit."""

    __tablename__ = "ingestion_runs"

    id: int | None = Field(default=None, primary_key=True)
    source: SourceKind = Field(index=True)
    query: str = Field(description="The query or filter expression used to fetch.")
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = Field(default=None)
    status: str = Field(default="running", description="running | completed | failed")
    total_found: int | None = Field(default=None)
    fetched: int = Field(default=0)
    inserted: int = Field(default=0)
    updated: int = Field(default=0)
    error: str | None = Field(default=None)
