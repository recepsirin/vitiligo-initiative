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

from sqlalchemy import JSON, Column, LargeBinary
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


class Embedding(SQLModel, table=True):
    """Vector embedding for a document, identified by model + scope.

    `scope` lets us embed different views of the same document (e.g.
    "title_abstract", "full_text", "section:methods") and pick the
    right one at query time.
    """

    __tablename__ = "embeddings"
    __table_args__ = (UniqueConstraint("document_id", "model", "scope", name="uq_doc_model_scope"),)

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    model: str = Field(
        index=True, description="Embedding model identifier (e.g. BAAI/bge-small-en-v1.5)."
    )
    scope: str = Field(default="title_abstract", index=True)
    dim: int
    vector: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_at: datetime = Field(default_factory=_utcnow)


class TrialSourceKind(StrEnum):
    """Known clinical-trial registries. Extend as new ingestion modules land."""

    CTGOV = "ctgov"
    EUCTR = "euctr"
    ICTRP = "ictrp"


class Trial(SQLModel, table=True):
    """A clinical trial record from a registry.

    Trials are stored separately from `documents` because their structure
    is fundamentally different: operational metadata (status, phase,
    locations, eligibility) drives a different set of queries than the
    text-centric document table. Search over trials is structured-first;
    semantic embedding can be layered later.
    """

    __tablename__ = "trials"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_trial_source_source_id"),)

    id: int | None = Field(default=None, primary_key=True)

    source: TrialSourceKind = Field(index=True)
    source_id: str = Field(index=True, description="Registry identifier (e.g. NCT01234567).")

    brief_title: str | None = Field(default=None)
    official_title: str | None = Field(default=None)
    summary: str | None = Field(default=None)

    status: str | None = Field(default=None, index=True, description="Overall recruitment status.")
    last_known_status: str | None = Field(default=None)
    study_type: str | None = Field(default=None, index=True)
    phases: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    conditions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    interventions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    arm_groups: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    sponsors: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    locations: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    countries: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    primary_outcomes: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    secondary_outcomes: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    enrollment_count: int | None = Field(default=None)
    enrollment_type: str | None = Field(default=None)

    eligibility_criteria: str | None = Field(default=None)
    sex: str | None = Field(default=None)
    minimum_age: str | None = Field(default=None)
    maximum_age: str | None = Field(default=None)
    healthy_volunteers: bool | None = Field(default=None)

    start_date: str | None = Field(default=None)
    primary_completion_date: str | None = Field(default=None)
    completion_date: str | None = Field(default=None)
    first_posted_date: str | None = Field(default=None)
    last_update_date: str | None = Field(default=None)

    has_results: bool = Field(default=False, index=True)

    raw_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    retrieved_at: datetime = Field(default_factory=_utcnow, index=True)


class PriorKind(StrEnum):
    """Kinds of structured biomedical priors used to ground hypothesis generation."""

    DRUG = "drug"
    TARGET = "target"


class PriorSourceKind(StrEnum):
    """Sources for drug/target priors. Extend as DrugBank and others land."""

    OPENTARGETS = "opentargets"
    DRUGBANK = "drugbank"


class Prior(SQLModel, table=True):
    """A drug or target prior linked to a disease, from a curated knowledge base.

    Priors sit alongside papers and trials: they encode mechanistic and
    clinical-stage knowledge (Open Targets associations, DrugBank mechanisms)
    that literature search alone may miss or under-weight.
    """

    __tablename__ = "priors"
    __table_args__ = (
        UniqueConstraint("source", "kind", "source_id", "disease_id", name="uq_prior_key"),
    )

    id: int | None = Field(default=None, primary_key=True)

    source: PriorSourceKind = Field(index=True)
    kind: PriorKind = Field(index=True)
    source_id: str = Field(index=True, description="Stable ID within source (e.g. CHEMBL id, Ensembl id).")

    disease_id: str = Field(index=True, description="Disease identifier (e.g. EFO_0004208).")
    disease_name: str | None = Field(default=None)

    name: str = Field(index=True)
    description: str | None = Field(default=None)

    score: float | None = Field(default=None, index=True, description="Association score for targets.")
    clinical_stage: str | None = Field(
        default=None, index=True, description="Max clinical stage for drugs (e.g. PHASE_3, APPROVAL)."
    )

    synonyms: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    mechanisms: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    linked_trial_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    linked_target_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    raw_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    retrieved_at: datetime = Field(default_factory=_utcnow, index=True)


class EntityKind(StrEnum):
    """Node types in the vitiligo knowledge graph."""

    DRUG = "drug"
    TARGET = "target"
    DISEASE = "disease"
    PATHWAY = "pathway"
    MECHANISM = "mechanism"
    BIOMARKER = "biomarker"
    INTERVENTION = "intervention"
    TRIAL = "trial"


class RelationKind(StrEnum):
    """Edge types in the vitiligo knowledge graph."""

    TREATS = "treats"
    TARGETS = "targets"
    INHIBITS = "inhibits"
    ACTIVATES = "activates"
    ASSOCIATED_WITH = "associated_with"
    TESTED_IN = "tested_in"
    INVESTIGATES = "investigates"


class GraphEntity(SQLModel, table=True):
    """A canonical entity node in the knowledge graph."""

    __tablename__ = "graph_entities"
    __table_args__ = (UniqueConstraint("kind", "key", name="uq_graph_entity_kind_key"),)

    id: int | None = Field(default=None, primary_key=True)
    kind: EntityKind = Field(index=True)
    key: str = Field(index=True, description="Normalized identifier within kind.")
    name: str = Field(index=True, description="Preferred display label.")
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    external_ids: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class GraphEdge(SQLModel, table=True):
    """A directed relation between two graph entities with provenance."""

    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint("subject_id", "predicate", "object_id", name="uq_graph_edge_triple"),
    )

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="graph_entities.id", index=True)
    predicate: RelationKind = Field(index=True)
    object_id: int = Field(foreign_key="graph_entities.id", index=True)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    extraction_method: str = Field(
        default="structured",
        index=True,
        description="structured | llm | mesh",
    )
    evidence: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class GraphExtraction(SQLModel, table=True):
    """Tracks LLM graph extraction status per document."""

    __tablename__ = "graph_extractions"
    __table_args__ = (UniqueConstraint("document_id", name="uq_graph_extraction_document"),)

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    status: str = Field(default="completed", description="completed | failed | skipped")
    entity_count: int = Field(default=0)
    edge_count: int = Field(default=0)
    error: str | None = Field(default=None)
    extracted_at: datetime = Field(default_factory=_utcnow)


class IngestionRun(SQLModel, table=True):
    """Bookkeeping for a single ingestion run, so we can resume and audit."""

    __tablename__ = "ingestion_runs"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(
        index=True,
        description="String form of the source enum value — accommodates both document and trial sources.",
    )
    query: str = Field(description="The query or filter expression used to fetch.")
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = Field(default=None)
    status: str = Field(default="running", description="running | completed | failed")
    total_found: int | None = Field(default=None)
    fetched: int = Field(default=0)
    inserted: int = Field(default=0)
    updated: int = Field(default=0)
    error: str | None = Field(default=None)
