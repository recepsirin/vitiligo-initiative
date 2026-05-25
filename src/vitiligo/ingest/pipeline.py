"""Ingestion pipelines.

A pipeline pulls documents from a source, upserts them into the document
store, and records an `IngestionRun` for auditability and resumability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import select

from vitiligo.logging import get_logger
from vitiligo.sources.pubmed import DEFAULT_VITILIGO_QUERY, PubMedClient
from vitiligo.storage import (
    Document,
    IngestionRun,
    SourceKind,
    init_db,
    session_scope,
)

logger = get_logger(__name__)


@dataclass
class IngestionStats:
    """Summary of an ingestion run."""

    source: SourceKind
    total_found: int | None
    fetched: int
    inserted: int
    updated: int
    run_id: int | None


def run_pubmed_ingestion(
    query: str = DEFAULT_VITILIGO_QUERY,
    batch_size: int = 200,
    limit: int | None = None,
    commit_every: int = 100,
) -> IngestionStats:
    """Search PubMed and persist every matching record.

    Args:
        query: PubMed search expression.
        batch_size: Records per efetch call.
        limit: Cap on total records (useful for smoke tests).
        commit_every: Flush + commit cadence to keep memory bounded and progress
            durable in the face of interruption.
    """
    init_db()

    run = IngestionRun(source=SourceKind.PUBMED, query=query)
    with session_scope() as session:
        session.add(run)
        session.flush()
        run_id = run.id

    fetched = 0
    inserted = 0
    updated = 0
    total_found: int | None = None

    try:
        with PubMedClient() as client, session_scope() as session:
            handle = client.search(query)
            total_found = handle.total

            with session_scope() as run_session:
                tracked = run_session.get(IngestionRun, run_id)
                if tracked is not None:
                    tracked.total_found = total_found

            for doc in client.iter_documents(query=query, batch_size=batch_size, limit=limit):
                fetched += 1
                ins, upd = _upsert_document(session, doc)
                inserted += ins
                updated += upd

                if fetched % commit_every == 0:
                    session.commit()
                    logger.info(
                        "Progress: fetched=%d inserted=%d updated=%d",
                        fetched,
                        inserted,
                        updated,
                    )

            session.commit()

        _finalize_run(run_id, "completed", fetched, inserted, updated, total_found, None)
    except Exception as exc:
        logger.exception("PubMed ingestion failed")
        _finalize_run(run_id, "failed", fetched, inserted, updated, total_found, str(exc))
        raise

    return IngestionStats(
        source=SourceKind.PUBMED,
        total_found=total_found,
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        run_id=run_id,
    )


def _upsert_document(session, doc: Document) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Insert a new document or update the existing row keyed by (source, source_id)."""
    statement = select(Document).where(
        Document.source == doc.source, Document.source_id == doc.source_id
    )
    existing = session.exec(statement).first()
    if existing is None:
        session.add(doc)
        return 1, 0

    for field in (
        "title",
        "abstract",
        "journal",
        "year",
        "doi",
        "language",
        "authors",
        "mesh_terms",
        "keywords",
        "publication_types",
        "raw_metadata",
    ):
        setattr(existing, field, getattr(doc, field))
    existing.retrieved_at = datetime.now(UTC)
    session.add(existing)
    return 0, 1


def _finalize_run(
    run_id: int | None,
    status: str,
    fetched: int,
    inserted: int,
    updated: int,
    total_found: int | None,
    error: str | None,
) -> None:
    if run_id is None:
        return
    with session_scope() as session:
        run = session.get(IngestionRun, run_id)
        if run is None:
            return
        run.status = status
        run.fetched = fetched
        run.inserted = inserted
        run.updated = updated
        run.total_found = total_found
        run.error = error
        run.completed_at = datetime.now(UTC)
        session.add(run)
