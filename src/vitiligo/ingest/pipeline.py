"""Ingestion pipelines.

A pipeline pulls documents from a source, upserts them into the document
store, and records an `IngestionRun` for auditability and resumability.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import select

from vitiligo.logging import get_logger
from vitiligo.sources.ctgov import DEFAULT_VITILIGO_QUERY as CTGOV_DEFAULT_QUERY
from vitiligo.sources.ctgov import CTGovClient
from vitiligo.sources.euctr import DEFAULT_VITILIGO_QUERY as EUCTR_DEFAULT_QUERY
from vitiligo.sources.euctr import EUCTRClient
from vitiligo.sources.ictrp import (
    count_ictrp_records,
    iter_ictrp_trials,
    should_skip_ictrp_record,
)
from vitiligo.sources.opentargets import (
    DEFAULT_DISEASE_QUERY as OPENTARGETS_DEFAULT_QUERY,
)
from vitiligo.sources.opentargets import (
    DEFAULT_TARGET_LIMIT,
    DEFAULT_VITILIGO_EFO_ID,
    OpenTargetsClient,
)
from vitiligo.sources.pmc import DEFAULT_VITILIGO_QUERY as PMC_DEFAULT_QUERY
from vitiligo.sources.pmc import PMCClient
from vitiligo.sources.pubmed import DEFAULT_VITILIGO_QUERY as PUBMED_DEFAULT_QUERY
from vitiligo.sources.pubmed import PubMedClient
from vitiligo.storage import (
    Document,
    IngestionRun,
    Prior,
    PriorSourceKind,
    SourceKind,
    Trial,
    TrialSourceKind,
    init_db,
    session_scope,
)

logger = get_logger(__name__)


@dataclass
class IngestionStats:
    """Summary of an ingestion run."""

    source: str
    total_found: int | None
    fetched: int
    inserted: int
    updated: int
    skipped: int = 0
    run_id: int | None = None


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
        source=SourceKind.PUBMED.value,
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
        source=SourceKind.PMC.value,
        query=query,
        factory=factory,
        commit_every=commit_every,
    )


def run_ctgov_ingestion(
    query: str = CTGOV_DEFAULT_QUERY,
    page_size: int = 100,
    limit: int | None = None,
    commit_every: int = 50,
) -> IngestionStats:
    """Search ClinicalTrials.gov and persist every matching trial."""

    def factory() -> tuple[Iterator[Trial], int | None, Callable[[], None]]:
        client = CTGovClient()
        handle = client.search(query)
        return (
            client.iter_trials(query=query, page_size=page_size, limit=limit),
            handle.total,
            client.close,
        )

    return _run_trial_ingestion(
        source=TrialSourceKind.CTGOV.value,
        query=query,
        factory=factory,
        commit_every=commit_every,
    )


def run_euctr_ingestion(
    query: str = EUCTR_DEFAULT_QUERY,
    page_size: int = 50,
    limit: int | None = None,
    commit_every: int = 25,
    with_details: bool = True,
) -> IngestionStats:
    """Search the EU CTR / CTIS public API and persist every matching trial."""

    def factory() -> tuple[Iterator[Trial], int | None, Callable[[], None]]:
        client = EUCTRClient()
        handle = client.search(query)
        return (
            client.iter_trials(
                query=query,
                page_size=page_size,
                limit=limit,
                with_details=with_details,
            ),
            handle.total,
            client.close,
        )

    return _run_trial_ingestion(
        source=TrialSourceKind.EUCTR.value,
        query=query,
        factory=factory,
        commit_every=commit_every,
    )


def run_ictrp_ingestion(
    file: Path,
    skip_duplicates: bool = True,
    limit: int | None = None,
    commit_every: int = 50,
) -> IngestionStats:
    """Import trials from a WHO ICTRP XML export file.

    Export from https://trialsearch.who.int/ (Export results to XML).
    Records already present via ctgov/euctr ingestion are skipped by default.
    """
    if not file.is_file():
        raise FileNotFoundError(f"ICTRP export not found: {file}")

    init_db()
    query = f"file:{file}"
    total_found = count_ictrp_records(file)
    if limit is not None:
        total_found = min(total_found, limit)

    run = IngestionRun(source=TrialSourceKind.ICTRP.value, query=query)
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = 0
    inserted = 0
    updated = 0
    skipped = 0

    try:
        with session_scope() as session:
            tracked = session.get(IngestionRun, run_id)
            if tracked is not None:
                tracked.total_found = total_found

            existing_keys = _load_trial_dedup_keys(session) if skip_duplicates else set()

            for trial in iter_ictrp_trials(file, limit=limit):
                fetched += 1
                if should_skip_ictrp_record(
                    trial,
                    skip_duplicates=skip_duplicates,
                    existing_keys=existing_keys,
                ):
                    skipped += 1
                    continue

                ins, upd = _upsert_trial(session, trial)
                inserted += ins
                updated += upd

                if fetched % commit_every == 0:
                    session.commit()
                    logger.info(
                        "Progress [ictrp]: fetched=%d inserted=%d updated=%d skipped=%d",
                        fetched,
                        inserted,
                        updated,
                        skipped,
                    )

            session.commit()

        _finalize_run(run_id, "completed", fetched, inserted, updated, total_found, None)
    except Exception as exc:
        logger.exception("Ingestion failed for source=ictrp")
        _finalize_run(run_id, "failed", fetched, inserted, updated, total_found, str(exc))
        raise

    return IngestionStats(
        source=TrialSourceKind.ICTRP.value,
        total_found=total_found,
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        run_id=run_id,
    )


def _load_trial_dedup_keys(session) -> set[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Load (source, source_id) keys for ctgov/euctr trials already in the store."""
    rows = session.exec(
        select(Trial.source, Trial.source_id).where(
            Trial.source.in_(  # type: ignore[attr-defined]
                [TrialSourceKind.CTGOV, TrialSourceKind.EUCTR]
            )
        )
    ).all()
    out: set[tuple[str, str]] = set()
    for source, source_id in rows:
        src = source.value if hasattr(source, "value") else str(source)
        out.add((src, source_id))
    return out


def _run_trial_ingestion(
    source: str,
    query: str,
    factory: Callable[[], tuple[Iterator[Trial], int | None, Callable[[], None]]],
    commit_every: int,
) -> IngestionStats:
    """Shared driver for trial ingestion across registries."""
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
        trial_iter, total_found, close = factory()
        try:
            if total_found is not None:
                with session_scope() as run_session:
                    tracked = run_session.get(IngestionRun, run_id)
                    if tracked is not None:
                        tracked.total_found = total_found

            with session_scope() as session:
                for trial in trial_iter:
                    fetched += 1
                    ins, upd = _upsert_trial(session, trial)
                    inserted += ins
                    updated += upd

                    if fetched % commit_every == 0:
                        session.commit()
                        logger.info(
                            "Progress [%s]: fetched=%d inserted=%d updated=%d",
                            source,
                            fetched,
                            inserted,
                            updated,
                        )

                session.commit()
        finally:
            close()

        _finalize_run(run_id, "completed", fetched, inserted, updated, total_found, None)
    except Exception as exc:
        logger.exception("Ingestion failed for source=%s", source)
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


def run_opentargets_ingestion(
    query: str = OPENTARGETS_DEFAULT_QUERY,
    efo_id: str | None = None,
    target_limit: int = DEFAULT_TARGET_LIMIT,
    commit_every: int = 50,
) -> IngestionStats:
    """Fetch drug and target priors for a disease from Open Targets."""
    init_db()

    run = IngestionRun(source=PriorSourceKind.OPENTARGETS.value, query=query)
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = 0
    inserted = 0
    updated = 0
    total_found: int | None = None

    try:
        client = OpenTargetsClient()
        try:
            handle = client.resolve_disease(query) if efo_id is None else None
            disease_efo = efo_id or (handle.efo_id if handle else DEFAULT_VITILIGO_EFO_ID)
            disease_name = handle.name if handle else query

            drug_iter = client.iter_drug_priors(disease_efo, disease_name)
            target_iter = client.iter_target_priors(
                disease_efo, disease_name, limit=target_limit
            )

            with session_scope() as session:
                for prior in _chain_priors(drug_iter, target_iter):
                    fetched += 1
                    ins, upd = _upsert_prior(session, prior)
                    inserted += ins
                    updated += upd

                    if fetched % commit_every == 0:
                        session.commit()
                        logger.info(
                            "Progress [%s]: fetched=%d inserted=%d updated=%d",
                            PriorSourceKind.OPENTARGETS.value,
                            fetched,
                            inserted,
                            updated,
                        )

                session.commit()
            total_found = fetched
        finally:
            client.close()

        _finalize_run(run_id, "completed", fetched, inserted, updated, total_found, None)
    except Exception as exc:
        logger.exception("Ingestion failed for source=%s", PriorSourceKind.OPENTARGETS.value)
        _finalize_run(run_id, "failed", fetched, inserted, updated, total_found, str(exc))
        raise

    return IngestionStats(
        source=PriorSourceKind.OPENTARGETS.value,
        total_found=total_found,
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        run_id=run_id,
    )


def _chain_priors(*iters: Iterator[Prior]) -> Iterator[Prior]:
    for it in iters:
        yield from it


_PRIOR_UPSERT_FIELDS = (
    "disease_id",
    "disease_name",
    "name",
    "description",
    "score",
    "clinical_stage",
    "synonyms",
    "mechanisms",
    "linked_trial_ids",
    "linked_target_ids",
    "raw_metadata",
)


def _upsert_prior(session, prior: Prior) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    statement = select(Prior).where(
        Prior.source == prior.source,
        Prior.kind == prior.kind,
        Prior.source_id == prior.source_id,
        Prior.disease_id == prior.disease_id,
    )
    existing = session.exec(statement).first()
    if existing is None:
        session.add(prior)
        return 1, 0

    for field in _PRIOR_UPSERT_FIELDS:
        setattr(existing, field, getattr(prior, field))
    existing.retrieved_at = datetime.now(UTC)
    session.add(existing)
    return 0, 1


_TRIAL_UPSERT_FIELDS = (
    "brief_title",
    "official_title",
    "summary",
    "status",
    "last_known_status",
    "study_type",
    "phases",
    "conditions",
    "keywords",
    "interventions",
    "arm_groups",
    "sponsors",
    "locations",
    "countries",
    "primary_outcomes",
    "secondary_outcomes",
    "enrollment_count",
    "enrollment_type",
    "eligibility_criteria",
    "sex",
    "minimum_age",
    "maximum_age",
    "healthy_volunteers",
    "start_date",
    "primary_completion_date",
    "completion_date",
    "first_posted_date",
    "last_update_date",
    "has_results",
    "raw_metadata",
)


def _upsert_trial(session, trial: Trial) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Insert a new trial or update the existing row keyed by (source, source_id)."""
    statement = select(Trial).where(
        Trial.source == trial.source, Trial.source_id == trial.source_id
    )
    existing = session.exec(statement).first()
    if existing is None:
        session.add(trial)
        return 1, 0

    for field in _TRIAL_UPSERT_FIELDS:
        setattr(existing, field, getattr(trial, field))
    existing.retrieved_at = datetime.now(UTC)
    session.add(existing)
    return 0, 1


def _run_ingestion(
    source: str,
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
                        source,
                        fetched,
                        inserted,
                        updated,
                    )

            session.commit()

        _finalize_run(run_id, "completed", fetched, inserted, updated, total_found, None)
    except Exception as exc:
        logger.exception("Ingestion failed for source=%s", source)
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
