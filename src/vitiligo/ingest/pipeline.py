"""Ingestion pipelines.

A pipeline pulls documents from a source, upserts them into the document
store, and records an `IngestionRun` for auditability and resumability.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import and_, select

from vitiligo.logging import get_logger
from vitiligo.sources.ctgov import DEFAULT_VITILIGO_QUERY as CTGOV_DEFAULT_QUERY
from vitiligo.sources.ctgov import CTGovClient
from vitiligo.sources.drugbank import (
    DEFAULT_VITILIGO_QUERY as DRUGBANK_DEFAULT_QUERY,
)
from vitiligo.sources.drugbank import (
    count_drugbank_drugs,
    iter_drugbank_priors,
    normalize_drug_name,
)
from vitiligo.sources.euctr import DEFAULT_VITILIGO_QUERY as EUCTR_DEFAULT_QUERY
from vitiligo.sources.euctr import EUCTRClient
from vitiligo.sources.geo import DEFAULT_VITILIGO_QUERY as GEO_DEFAULT_QUERY
from vitiligo.sources.geo import GEOClient
from vitiligo.sources.gwas import (
    ASSOCIATIONS_FILE,
    associations_url,
    fetch_associations,
    filtered_payload,
    records_from_rows,
    rows_from_payload,
)
from vitiligo.sources.gwas import DEFAULT_TRAIT_QUERY as GWAS_DEFAULT_QUERY
from vitiligo.sources.ictrp import (
    count_ictrp_records,
    iter_ictrp_trials,
    should_skip_ictrp_record,
)
from vitiligo.sources.isrctn import DEFAULT_VITILIGO_QUERY as ISRCTN_DEFAULT_QUERY
from vitiligo.sources.isrctn import ISRCTNClient
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
from vitiligo.sources.raw_cache import load_payload, save_payload
from vitiligo.sources.reporter import DEFAULT_VITILIGO_QUERY as REPORTER_DEFAULT_QUERY
from vitiligo.sources.reporter import SEARCH_URL as REPORTER_SEARCH_URL
from vitiligo.sources.reporter import ReporterClient, to_project
from vitiligo.storage import (
    Document,
    Embedding,
    IngestionRun,
    Prior,
    PriorKind,
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


def run_geo_ingestion(
    query: str = GEO_DEFAULT_QUERY,
    batch_size: int = 100,
    limit: int | None = None,
    commit_every: int = 50,
) -> IngestionStats:
    """Search NCBI GEO DataSets and persist series metadata."""

    def factory() -> tuple[Iterator[Document], int | None]:
        client = GEOClient()
        handle = client.search(query)
        return (
            client.iter_documents(query=query, batch_size=batch_size, limit=limit),
            handle.total,
        )

    return _run_ingestion(
        source=SourceKind.GEO.value,
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
            target_iter = client.iter_target_priors(disease_efo, disease_name, limit=target_limit)

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


def run_gwas_ingestion(
    trait_query: str = GWAS_DEFAULT_QUERY,
    file_name: str = ASSOCIATIONS_FILE,
    commit_every: int = 100,
) -> IngestionStats:
    """Import inherited variants associated with the trait from the GWAS Catalog."""
    import httpx

    from vitiligo.storage import GeneticAssociation

    init_db()
    source = "gwas_catalog"
    run = IngestionRun(source=source, query=f"{trait_query}|{file_name}")
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = inserted = updated = 0
    total_found: int | None = None
    try:
        # The release covers every trait and is tens of megabytes, so the filter
        # runs here and only the matching rows are kept.
        cache_name = f"{trait_query}-associations.json"
        try:
            with httpx.Client(
                timeout=httpx.Timeout(600.0, connect=30.0), follow_redirects=True
            ) as client:
                raw = fetch_associations(client, file_name)
            payload = filtered_payload(raw, trait_query, file_name, associations_url(file_name))
            save_payload(
                "gwas_catalog",
                cache_name,
                json.dumps(payload).encode("utf-8"),
                url=associations_url(file_name),
            )
        except httpx.HTTPError as exc:
            cached = load_payload("gwas_catalog", cache_name)
            if cached is None:
                raise
            logger.warning("GWAS Catalog unreachable (%s); using the cached rows", exc)
            payload = json.loads(cached)
        records = records_from_rows(rows_from_payload(payload))
        total_found = len(records)
        logger.info("GWAS Catalog: %d association(s) for %r", total_found, trait_query)

        with session_scope() as session:
            for record in records:
                fetched += 1
                existing = session.exec(
                    select(GeneticAssociation).where(
                        and_(
                            GeneticAssociation.source == record.source,
                            GeneticAssociation.source_id == record.source_id,
                        )
                    )
                ).first()
                if existing is None:
                    session.add(record)
                    inserted += 1
                else:
                    for field in (
                        "trait", "mapped_trait", "variant", "mapped_gene", "reported_genes",
                        "risk_allele", "p_value", "p_value_text", "odds_ratio_or_beta",
                        "confidence_interval", "study_accession", "pubmed_id", "initial_sample",
                        "raw_metadata", "retrieved_at",
                    ):  # fmt: skip
                        setattr(existing, field, getattr(record, field))
                    session.add(existing)
                    updated += 1
                if fetched % commit_every == 0:
                    session.commit()
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


def run_isrctn_ingestion(
    query: str = ISRCTN_DEFAULT_QUERY,
    commit_every: int = 25,
) -> IngestionStats:
    """Import vitiligo trials from ISRCTN, the registry outside ClinicalTrials.gov."""
    init_db()
    source = TrialSourceKind.ISRCTN.value
    run = IngestionRun(source=source, query=query)
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = inserted = updated = 0
    total_found: int | None = None
    try:
        with ISRCTNClient() as client, session_scope() as session:
            for trial in client.iter_trials(query):
                fetched += 1
                ins, upd = _upsert_trial(session, trial)
                inserted += ins
                updated += upd
                if fetched % commit_every == 0:
                    session.commit()
            session.commit()
        total_found = fetched
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


def run_reporter_ingestion(
    query: str = REPORTER_DEFAULT_QUERY,
    commit_every: int = 50,
) -> IngestionStats:
    """Import NIH-funded projects matching the query from NIH RePORTER."""
    from vitiligo.storage import ResearchProject

    init_db()
    source = "nih_reporter"
    run = IngestionRun(source=source, query=query)
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = inserted = updated = 0
    total_found: int | None = None
    try:
        collected: list[dict[str, Any]] = []
        with ReporterClient() as client, session_scope() as session:
            for record in client.iter_projects(query):
                collected.append(record)
                project = to_project(record)
                if project is None:
                    continue
                fetched += 1
                existing = session.exec(
                    select(ResearchProject).where(
                        and_(
                            ResearchProject.source == project.source,
                            ResearchProject.source_id == project.source_id,
                        )
                    )
                ).first()
                if existing is None:
                    session.add(project)
                    inserted += 1
                else:
                    for field in (
                        "core_project_num", "title", "abstract", "contact_pi",
                        "contact_pi_profile_id", "investigators", "organization", "org_city",
                        "org_state", "org_country", "fiscal_year", "award_amount", "agency",
                        "activity_code", "is_active", "project_start", "project_end", "terms",
                        "project_url", "raw_metadata", "retrieved_at",
                    ):  # fmt: skip
                        setattr(existing, field, getattr(project, field))
                    session.add(existing)
                    updated += 1
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
        total_found = fetched
        save_payload(
            source,
            f"{query}-projects.json",
            json.dumps(collected).encode("utf-8"),
            url=REPORTER_SEARCH_URL,
        )
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


def run_drugbank_ingestion(
    file: Path,
    query: str = DRUGBANK_DEFAULT_QUERY,
    disease_id: str = DEFAULT_VITILIGO_EFO_ID,
    seed_from_opentargets: bool = True,
    limit: int | None = None,
    commit_every: int = 25,
) -> IngestionStats:
    """Import vitiligo-relevant drug/target priors from a DrugBank XML export."""
    if not file.is_file():
        raise FileNotFoundError(f"DrugBank export not found: {file}")

    init_db()
    run_query = f"file:{file}|query:{query}"
    total_found = count_drugbank_drugs(file)

    run = IngestionRun(source=PriorSourceKind.DRUGBANK.value, query=run_query)
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = 0
    inserted = 0
    updated = 0

    try:
        with session_scope() as session:
            tracked = session.get(IngestionRun, run_id)
            if tracked is not None:
                tracked.total_found = total_found

            seed_names = _load_opentargets_seed_names(session) if seed_from_opentargets else set()

            for prior in iter_drugbank_priors(
                file,
                query=query,
                disease_id=disease_id,
                seed_names=seed_names or None,
                limit=limit,
            ):
                fetched += 1
                ins, upd = _upsert_prior(session, prior)
                inserted += ins
                updated += upd

                if fetched % commit_every == 0:
                    session.commit()
                    logger.info(
                        "Progress [drugbank]: fetched=%d inserted=%d updated=%d",
                        fetched,
                        inserted,
                        updated,
                    )

            session.commit()

        _finalize_run(run_id, "completed", fetched, inserted, updated, fetched, None)
    except Exception as exc:
        logger.exception("Ingestion failed for source=drugbank")
        _finalize_run(run_id, "failed", fetched, inserted, updated, total_found, str(exc))
        raise

    return IngestionStats(
        source=PriorSourceKind.DRUGBANK.value,
        total_found=total_found,
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        run_id=run_id,
    )


def _load_opentargets_seed_names(session) -> set[str]:  # type: ignore[no-untyped-def]
    rows = session.exec(
        select(Prior.name, Prior.synonyms).where(
            Prior.source == PriorSourceKind.OPENTARGETS,
            Prior.kind == PriorKind.DRUG,
            Prior.disease_id == DEFAULT_VITILIGO_EFO_ID,
        )
    ).all()
    names: set[str] = set()
    for name, synonyms in rows:
        if name:
            names.add(normalize_drug_name(name))
        for syn in synonyms or []:
            if syn:
                names.add(normalize_drug_name(str(syn)))
    return names


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

    if (existing.title, existing.abstract) != (doc.title, doc.abstract):
        # Embeddings encode title + abstract; drop them so `embed run`
        # re-embeds this document instead of serving a stale vector.
        for embedding in session.exec(
            select(Embedding).where(Embedding.document_id == existing.id)
        ).all():
            session.delete(embedding)

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
