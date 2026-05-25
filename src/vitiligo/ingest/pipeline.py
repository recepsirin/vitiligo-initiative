"""Ingestion pipelines.

A pipeline pulls documents from a source, upserts them into the document
store, and records an `IngestionRun` for auditability and resumability.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import select

from vitiligo.logging import get_logger
from vitiligo.sources.pmc import DEFAULT_VITILIGO_QUERY as PMC_DEFAULT_QUERY
from vitiligo.sources.pmc import PMCClient
from vitiligo.sources.pubmed import DEFAULT_VITILIGO_QUERY as PUBMED_DEFAULT_QUERY
from vitiligo.sources.pubmed import PubMedClient
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
    query: str = PUBMED_DEFAULT_QUERY,
    batch_size: int = 200,
    limit: int | None = None,
    commit_every: int = 100,
) -> IngestionStats:
    """Search PubMed and persist every matching record."""

    def factory() -> tuple[Iterator[Document], int | None]:
        client = PubMedClient()
        handle = client.search(query)
        return client.iter_documents(query=query, batch_size=batch_size, limit=limit), handle.total

    return _run_ingestion(
        source=SourceKind.PUBMED,
        query=query,
        factory=factory,
        commit_every=commit_every,
    )


def run_pmc_ingestion(
    query: str = PMC_DEFAULT_QUERY,
    batch_size: int = 50,
    limit: int | None = None,
    commit_every: int = 25,
) -> IngestionStats:
    """Search PMC Open Access and persist every matching full-text record."""

    def factory() -> tuple[Iterator[Document], int | None]:
        client = PMCClient()
        handle = client.search(query)
        return client.iter_documents(query=query, batch_size=batch_size, limit=limit), handle.total

    return _run_ingestion(
        source=SourceKind.PMC,
        query=query,
        factory=factory,
        commit_every=commit_every,
    )


def _run_ingestion(
    source: SourceKind,
    query: str,
    factory: Callable[[], tuple[Iterator[Document], int | None]],
    commit_every: int,
) -> IngestionStats:
    """Shared ingestion loop with upsert + bookkeeping.

    `factory` returns (document_iterator, total_found_estimate). The
    iterator is consumed inside a single session so we get batched
    commits and bounded memory.
    """
    init_db()

    run = IngestionRun(source=source, query=query)
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = 0
    inserted = 0
    updated = 0
    total_found: int | None = None

    try:
        with session_scope() as session:
            doc_iter, total_found = factory()

            if total_found is not None:
                with session_scope() as run_session:
                    tracked = run_session.get(IngestionRun, run_id)
                    if tracked is not None:
                        tracked.total_found = total_found

            for doc in doc_iter:
                fetched += 1
                ins, upd = _upsert_document(session, doc)
                inserted += ins
                updated += upd

                if fetched % commit_every == 0:
                    session.commit()
                    logger.info(
                        "Progress [%s]: fetched=%d inserted=%d updated=%d",
                        source.value,
                        fetched,
                        inserted,
                        updated,
                    )

            session.commit()

        _finalize_run(run_id, "completed", fetched, inserted, updated, total_found, None)
    except Exception as exc:
        logger.exception("Ingestion failed for source=%s", source.value)
        _finalize_run(run_id, "failed", fetched, inserted, updated, total_found, str(exc))
        raise

    return IngestionStats(
        source=source,
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
