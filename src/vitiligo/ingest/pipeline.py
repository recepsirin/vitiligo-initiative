"""Ingestion pipelines.

A pipeline pulls documents from a source, upserts them into the document
store, and records an `IngestionRun` for auditability and resumability.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable, Iterator, Sequence
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
    normalize_protocol_id,
    should_skip_ictrp_record,
)
from vitiligo.sources.ictrp_csv import SEARCH_URL as ICTRP_SEARCH_URL
from vitiligo.sources.ictrp_csv import count_csv_rows, iter_csv_trials, redacted_csv, search
from vitiligo.sources.ictrp_web import resolve_trials
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
from vitiligo.sources.raw_cache import (
    DEFAULT_RAW_CACHE,
    load_payload,
    payload_path,
    save_payload,
)
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
from vitiligo.trials.countries import normalize_countries
from vitiligo.trials.relevance import (
    DERM_DRUG_SCOPE,
    DRUG_CLASS_SCOPE,
    is_vitiligo_trial,
    treats_skin_disease,
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


def run_oa_fulltext_ingestion(
    source_ids: Sequence[str] | None = None,
    limit: int | None = None,
    commit_every: int = 25,
    refresh: bool = False,
) -> IngestionStats:
    """Give the papers we hold as abstracts their open-access body.

    PMC holds the full text of 44 of the 522 published vitiligo trials.
    Unpaywall finds a free copy for 154 of the 463 with a DOI, mostly on the
    publisher's own site, and 71 of those carry a Creative Commons licence --
    the only ones this fetches. What a licence permits is recorded on the
    document beside the text, because "we hold this" and "we may hold this"
    are different claims.

    The body is merged into the existing PubMed document rather than stored as
    a second record: the paper is one paper, and splitting it would double it
    the way a registry record doubles when two registries hold it.

    Most of it fails, and that is the finding rather than a bug. Of 40
    licensed papers, 21 were refused outright and 13 answered with a
    JavaScript shell -- Wiley, Oxford, Elsevier and JAMA all decline a
    programmatic request for an article they published under CC BY. Six
    answered: two repositories, two SciELO journals, a Springer PDF and the
    NIHR's HI-Light report.
    """
    import httpx

    from vitiligo.sources.oa_fulltext import USER_AGENT, find_open_copy, read_open_copy

    init_db()
    run = IngestionRun(source=SourceKind.PUBMED.value, query="oa-fulltext")
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = inserted = updated = skipped = 0
    try:
        with session_scope() as session:
            statement = select(Document).where(Document.source == SourceKind.PUBMED)
            if source_ids:
                statement = statement.where(Document.source_id.in_(list(source_ids)))  # type: ignore[attr-defined]
            candidates = [
                doc
                for doc in session.exec(statement).all()
                if (doc.doi or "").strip()
                and (refresh or not ((doc.raw_metadata or {}).get("full_text") or "").strip())
            ]
            if limit is not None:
                candidates = candidates[:limit]
            total_found = len(candidates)
            logger.info("Open-access full text: %d candidates", total_found)

            with httpx.Client(
                headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True
            ) as client:
                for doc in candidates:
                    fetched += 1
                    copy = find_open_copy(str(doc.doi), client=client)
                    if copy is None or not copy.may_fetch:
                        skipped += 1
                        continue
                    got = read_open_copy(copy, client=client, refresh=refresh)
                    if got is None:
                        skipped += 1
                        continue
                    text, tables = got
                    metadata = dict(doc.raw_metadata or {})
                    metadata.update(
                        {
                            "full_text": text,
                            "tables": tables,
                            "oa_licence": copy.licence,
                            "oa_url": copy.best_url,
                            "oa_host": copy.host_type,
                        }
                    )
                    doc.raw_metadata = metadata
                    doc.retrieved_at = datetime.now(UTC)
                    session.add(doc)
                    updated += 1
                    if fetched % commit_every == 0:
                        session.commit()
                        logger.info(
                            "Progress [oa-fulltext]: fetched=%d updated=%d skipped=%d",
                            fetched,
                            updated,
                            skipped,
                        )
            session.commit()
        _finalize_run(run_id, "completed", fetched, inserted, updated, total_found, None)
    except Exception as exc:
        logger.exception("Open-access full-text ingestion failed")
        _finalize_run(run_id, "failed", fetched, inserted, updated, None, str(exc))
        raise

    return IngestionStats(
        source="oa-fulltext",
        total_found=total_found,
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        run_id=run_id,
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


# The JAK inhibitors this project's scenario model is built on, plus the rest
# of the class in clinical use. A drug's trials in other diseases are the
# class's evidence base: ritlecitinib and baricitinib are approved in alopecia
# areata, ruxolitinib in myelofibrosis, and their dose-response and safety do
# not stop being informative because the skin in question is not vitiligo.
JAK_INHIBITORS: tuple[str, ...] = (
    "ruxolitinib",
    "ritlecitinib",
    "baricitinib",
    "upadacitinib",
    "tofacitinib",
    "abrocitinib",
    "deucravacitinib",
    "delgocitinib",
    "ivarmacitinib",
    "povorcitinib",
)


# The drugs this project holds a vitiligo prior for, beyond the JAK class, and
# the diseases their trials have to be in to be worth holding. Without the
# condition filter these 34 drugs return 31,881 trials, most of them
# "dexamethasone in septic shock" and "metformin in type 2 diabetes": a trial
# of a vitiligo prior that is not about skin at all. Restricted to skin and
# autoimmune disease they return 3,763.
PRIOR_DRUGS: tuple[str, ...] = (
    "tacrolimus",
    "pimecrolimus",
    "methotrexate",
    "afamelanotide",
    "latanoprost",
    "bimatoprost",
    "trioxsalen",
    "tretinoin",
    "triamcinolone",
    "dexamethasone",
    "beclomethasone",
    "fluticasone",
    "simvastatin",
    "atorvastatin",
    "metformin",
    "sirolimus",
    "apremilast",
    "abatacept",
    "etanercept",
    "anifrolumab",
    "piperine",
    "ibuprofen",
    "fluorouracil",
    "cerdulatinib",
    "mycophenolate",
    "ciclosporin",
    "azathioprine",
    "calcipotriol",
    "clobetasol",
    "betamethasone",
    "mometasone",
    "dupilumab",
    "ustekinumab",
    "secukinumab",
)

SKIN_AND_AUTOIMMUNE = (
    '(vitiligo OR psoriasis OR "atopic dermatitis" OR eczema OR "alopecia areata" OR '
    '"lichen planus" OR "lichen sclerosus" OR "hidradenitis suppurativa" OR urticaria OR '
    'pemphigus OR pemphigoid OR morphea OR scleroderma OR "cutaneous lupus" OR '
    '"mycosis fungoides" OR "seborrheic dermatitis" OR "contact dermatitis" OR '
    '"hypopigmentation" OR "skin disease")'
)


def run_prior_drug_ingestion(
    drugs: Sequence[str] = PRIOR_DRUGS,
    page_size: int = 100,
    limit: int | None = None,
    commit_every: int = 100,
) -> IngestionStats:
    """Import trials of the project's prior drugs, in skin and autoimmune disease.

    These are the drugs Open Targets and DrugBank tie to vitiligo and that a
    dermatologist actually reaches for: tacrolimus, calcipotriol, clobetasol,
    methotrexate, afamelanotide. Their trials in psoriasis and atopic
    dermatitis are the comparative evidence for the same molecules.

    Marked ``derm_drug`` and counted separately, for the same reason as the
    JAK class: a trial of tacrolimus in atopic dermatitis is not a vitiligo
    trial.
    """
    return run_drug_class_ingestion(
        drugs=drugs,
        scope=DERM_DRUG_SCOPE,
        condition=SKIN_AND_AUTOIMMUNE,
        keep=treats_skin_disease,
        page_size=page_size,
        limit=limit,
        commit_every=commit_every,
        label="prior-drugs",
    )


def run_jak_class_ingestion(
    drugs: Sequence[str] = JAK_INHIBITORS,
    page_size: int = 100,
    limit: int | None = None,
    commit_every: int = 100,
) -> IngestionStats:
    """Import every ClinicalTrials.gov trial of a JAK inhibitor, in any disease.

    There are 1,399 of them and the vitiligo corpus held 41, because they are
    not findable by any condition this project reads: they are in rheumatoid
    arthritis, atopic dermatitis, myelofibrosis, psoriasis and alopecia
    areata. 428 of the ones we lacked have posted results, against 65 in the
    whole vitiligo corpus, which is the asymmetry worth closing.
    """
    return run_drug_class_ingestion(
        drugs=drugs,
        scope=DRUG_CLASS_SCOPE,
        page_size=page_size,
        limit=limit,
        commit_every=commit_every,
        label="jak-class",
    )


def run_drug_class_ingestion(
    drugs: Sequence[str],
    scope: str,
    condition: str | None = None,
    keep: Callable[[Trial], bool] | None = None,
    page_size: int = 100,
    limit: int | None = None,
    commit_every: int = 100,
    label: str = "drug-class",
) -> IngestionStats:
    """Import trials by the drug they give, not the disease they treat.

    **They are marked, not mixed.** Each trial's metadata records its
    ``scope``, because a trial of ruxolitinib in myelofibrosis is not a
    vitiligo trial and a count that said otherwise would be a number about
    another disease wearing this project's name. Every published figure about
    vitiligo trials filters on ``in_vitiligo_corpus``.

    A trial that is both -- ruxolitinib cream in vitiligo -- keeps its place
    in the vitiligo corpus: the condition search is the one that says what it
    is, so an existing row's scope is read and carried over rather than
    stamped.

    ``condition`` narrows the search and ``keep`` checks what came back, which
    is not the same thing and both are needed. Asking ClinicalTrials.gov for
    these drugs in a list of skin diseases returned 2,974 trials we did not
    hold, and 1,579 of them were oncology -- 420 breast cancer at the top,
    because methotrexate and fluorouracil are chemotherapy and the condition
    expression expands further than it reads. Filtering on the conditions the
    record actually carries leaves 1,362.
    """
    init_db()
    run = IngestionRun(source=TrialSourceKind.CTGOV.value, query=f"{label}:{len(drugs)} drugs")
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = inserted = updated = skipped = 0
    try:
        client = CTGovClient()
        try:
            with session_scope() as session:
                seen: set[str] = set()
                for drug in drugs:
                    logger.info("%s: %s", label, drug)
                    for trial in client.iter_trials(
                        query=drug,
                        page_size=page_size,
                        limit=limit,
                        field="query.intr",
                        condition=condition,
                    ):
                        if trial.source_id in seen:
                            continue
                        seen.add(trial.source_id)
                        fetched += 1
                        if keep is not None and not keep(trial):
                            skipped += 1
                            continue
                        metadata = dict(trial.raw_metadata or {})
                        existing = session.exec(
                            select(Trial).where(
                                Trial.source == trial.source,
                                Trial.source_id == trial.source_id,
                            )
                        ).first()
                        if existing is None:
                            metadata["scope"] = scope
                            metadata["scope_drug"] = drug
                        else:
                            prior = existing.raw_metadata or {}
                            if prior.get("scope"):
                                metadata["scope"] = prior["scope"]
                                metadata["scope_drug"] = prior.get("scope_drug", drug)
                        trial.raw_metadata = metadata
                        ins, upd = _upsert_trial(session, trial)
                        inserted += ins
                        updated += upd
                        if fetched % commit_every == 0:
                            session.commit()
                            logger.info(
                                "Progress [%s]: fetched=%d inserted=%d updated=%d skipped=%d",
                                label,
                                fetched,
                                inserted,
                                updated,
                                skipped,
                            )
                session.commit()
        finally:
            client.close()
        _finalize_run(run_id, "completed", fetched, inserted, updated, fetched, None)
    except Exception as exc:
        logger.exception("%s ingestion failed", label)
        _finalize_run(run_id, "failed", fetched, inserted, updated, None, str(exc))
        raise

    return IngestionStats(
        source=label,
        total_found=fetched,
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        run_id=run_id,
    )


def run_published_trial_ingestion(
    query: str = (
        "(vitiligo[MeSH Terms] AND (randomized controlled trial[Publication Type]"
        " OR clinical trial[Publication Type] OR controlled clinical trial[Publication Type]))"
        " OR (vitiligo[MeSH Terms] AND comparative study[Publication Type])"
        " OR (vitiligo[tiab] AND (randomized[tiab] OR randomised[tiab] OR placebo[tiab]"
        ' OR double-blind[tiab] OR "double blind"[tiab]))'
        # An old record is a title and nothing else, so the title has to be
        # searched directly: 399 of the 401 vitiligo papers before 1970 carry
        # no abstract, in PubMed or in Europe PMC.
        " OR ((vitiligo[Title] OR leucoderma[Title] OR leukoderma[Title])"
        ' AND ("controlled study"[Title] OR "controlled trial"[Title]'
        ' OR "clinical trial"[Title] OR "double blind"[Title] OR "double-blind"[Title]'
        ' OR "single blind"[Title] OR randomized[Title] OR randomised[Title]'
        ' OR crossover[Title] OR "cross-over"[Title] OR "comparative study"[Title]'
        ' OR "comparative trial"[Title] OR placebo[Title]'
        # A head-to-head comparison is a design statement, and for a record
        # with no abstract the title is all there is.
        ' OR versus[Title] OR "vs"[Title] OR "comparison of"[Title]'
        ' OR "compared with"[Title] OR "compared to"[Title]))'
    ),
    commit_every: int = 50,
) -> IngestionStats:
    """Build trial records for vitiligo trials that were never registered.

    PubMed lists 522 published vitiligo trials and 28 of them carry a registry
    accession. The rest were run, reported and never registered, mostly
    because they predate the 2005 rule that made registration a condition of
    publication, and they are invisible to a trials table built from
    registries. Eighteen published Turkish vitiligo trials name no registry id
    between them.

    The papers are already in the corpus. This reads the ones we hold rather
    than fetching again, so the search runs against PubMed only to decide
    which documents are trial reports.
    """
    from vitiligo.sources.ictrp import normalize_protocol_id
    from vitiligo.sources.published_trials import comparison_key, registry_ids, trial_from_document

    init_db()
    run = IngestionRun(source=TrialSourceKind.PUBLICATION.value, query=query)
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = inserted = updated = skipped = 0
    try:
        client = PubMedClient()
        try:
            pmids = list(client.search_ids(query))
        finally:
            client.close()
        logger.info("PubMed reports %d published trial papers", len(pmids))

        with session_scope() as session:
            held: set[str] = set()
            # A one-column select yields the values, not one-tuples.
            for source_id in session.exec(select(Trial.source_id)).all():
                held.add(comparison_key(source_id))
                key = normalize_protocol_id(source_id)
                if key:
                    held.add(key)

            wanted = set(pmids)
            documents = [
                doc
                for doc in session.exec(
                    select(Document).where(Document.source == SourceKind.PUBMED)
                ).all()
                if doc.source_id in wanted
            ]
            logger.info("%d of them are held as documents", len(documents))

            for document in documents:
                fetched += 1
                if any(comparison_key(i) in held for i in registry_ids(document)):
                    skipped += 1
                    continue
                trial = trial_from_document(document)
                if trial is None:
                    skipped += 1
                    continue
                ins, upd = _upsert_trial(session, trial)
                inserted += ins
                updated += upd
                if fetched % commit_every == 0:
                    session.commit()
            session.commit()
        _finalize_run(run_id, "completed", fetched, inserted, updated, len(pmids), None)
    except Exception as exc:
        logger.exception("Published-trial ingestion failed")
        _finalize_run(run_id, "failed", fetched, inserted, updated, None, str(exc))
        raise

    return IngestionStats(
        source="published-trials",
        total_found=len(pmids),
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        run_id=run_id,
    )


def run_vitiligo_outcome_ingestion(commit_every: int = 50) -> IngestionStats:
    """Hold the cancer immunotherapy trials in which vitiligo appeared.

    Checkpoint blockade and melanoma vaccines cause depigmentation through the
    same CD8 response to melanocyte antigens that causes the disease, and its
    appearance predicts durable response. That makes these the mechanism
    evidence the disease's own literature cannot supply, because nobody
    randomises people to develop vitiligo.

    They are marked ``vitiligo_outcome`` and excluded from every figure about
    vitiligo trials: the disease being treated is a cancer. The papers are
    already in the corpus, so this reads them rather than fetching again.
    """
    from vitiligo.sources.published_trials import outcome_trial_from_document

    init_db()
    run = IngestionRun(source=TrialSourceKind.PUBLICATION.value, query="vitiligo-as-outcome")
    with session_scope() as bookkeeping:
        bookkeeping.add(run)
        bookkeeping.flush()
        run_id = run.id

    fetched = inserted = updated = skipped = 0
    try:
        with session_scope() as session:
            documents = session.exec(
                select(Document).where(Document.source == SourceKind.PUBMED)
            ).all()
            for document in documents:
                fetched += 1
                trial = outcome_trial_from_document(document)
                if trial is None:
                    skipped += 1
                    continue
                ins, upd = _upsert_trial(session, trial)
                inserted += ins
                updated += upd
                if inserted % commit_every == 0 and ins:
                    session.commit()
            session.commit()
        _finalize_run(run_id, "completed", fetched, inserted, updated, fetched, None)
    except Exception as exc:
        logger.exception("Vitiligo-as-outcome ingestion failed")
        _finalize_run(run_id, "failed", fetched, inserted, updated, None, str(exc))
        raise

    return IngestionStats(
        source="vitiligo-as-outcome",
        total_found=fetched,
        fetched=fetched,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        run_id=run_id,
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
    require_vitiligo: bool = False,
) -> IngestionStats:
    """Import trials from a WHO ICTRP XML export file.

    Export from https://trialsearch.who.int/ (Export results to XML).
    Records already present via ctgov/euctr ingestion are skipped by default.

    Unlike the by-id route, this one keeps every record by default, because
    the export is the result of ICTRP's own disease-scoped search.
    ``require_vitiligo`` turns on ``is_vitiligo_trial``, which is worth having
    when the export is broader than one disease: a search for the synonyms
    returns gingival depigmentation and orthodontic white spot lesions in far
    greater numbers than it returns vitiligo.
    """
    if not file.is_file():
        raise FileNotFoundError(f"ICTRP export not found: {file}")

    total_found = count_ictrp_records(file)
    if limit is not None:
        total_found = min(total_found, limit)

    return _ingest_ictrp_trials(
        lambda: iter_ictrp_trials(file, limit=limit),
        query=f"file:{file}",
        total_found=total_found,
        skip_duplicates=skip_duplicates,
        commit_every=commit_every,
        keep=is_vitiligo_trial if require_vitiligo else None,
    )


def run_ictrp_resolution(
    trial_ids: Sequence[str],
    skip_duplicates: bool = True,
    commit_every: int = 10,
    refresh: bool = False,
    require_vitiligo: bool = True,
) -> IngestionStats:
    """Resolve registry ids one at a time against the WHO ICTRP record pages.

    This is the route to the registries that publish no API of their own —
    CTRI, ChiCTR, IRCT, PACTR — so a trial a paper cites by id can be read
    rather than left as a string. Ids ICTRP does not hold simply do not
    arrive; records registered under another condition are skipped.
    """
    return _ingest_ictrp_trials(
        lambda: resolve_trials(trial_ids, refresh=refresh),
        query=f"ids:{','.join(sorted(trial_ids))[:400]}",
        total_found=len(trial_ids),
        skip_duplicates=skip_duplicates,
        commit_every=commit_every,
        keep=is_vitiligo_trial if require_vitiligo else None,
    )


def run_ictrp_search_ingestion(
    term: str = "vitiligo",
    skip_duplicates: bool = True,
    limit: int | None = None,
    commit_every: int = 50,
    require_vitiligo: bool = False,
    cache: Path | None = DEFAULT_RAW_CACHE,
) -> IngestionStats:
    """Search WHO ICTRP and import every trial it returns.

    The portal's search is an ASP.NET form, not a URL, which is why this went
    unreached for so long -- but the form posts back, and its own Export to
    CSV button returns the whole result set. For vitiligo that is every trial
    the ICTRP network holds, not only the ones a paper happened to cite.

    The export is cached with its contact columns removed, so what lands on
    disk carries no investigator's name, address, telephone number or email.
    """
    payload = redacted_csv(search(term))
    if cache is not None:
        saved = save_payload(
            "ictrp-search",
            f"{re.sub(r'[^A-Za-z0-9]+', '-', term).strip('-') or 'search'}.csv",
            payload,
            url=ICTRP_SEARCH_URL,
            cache=cache,
        )
        path = payload_path(saved.source, saved.name, cache)
    else:
        path = Path(tempfile.mkstemp(suffix=".csv")[1])
        path.write_bytes(payload)

    total_found = count_csv_rows(path)
    if limit is not None:
        total_found = min(total_found, limit)

    return _ingest_ictrp_trials(
        lambda: iter_csv_trials(path, limit=limit),
        query=f"search:{term}",
        total_found=total_found,
        skip_duplicates=skip_duplicates,
        commit_every=commit_every,
        keep=is_vitiligo_trial if require_vitiligo else None,
    )


def _ingest_ictrp_trials(
    trials: Callable[[], Iterator[Trial]],
    *,
    query: str,
    total_found: int | None,
    skip_duplicates: bool,
    commit_every: int,
    keep: Callable[[Trial], bool] | None = None,
) -> IngestionStats:
    """Upsert ICTRP trials from either route under one audited run."""
    init_db()
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
            protocol_ids = _load_protocol_ids(session) if skip_duplicates else set()

            for trial in trials():
                fetched += 1
                if keep is not None and not keep(trial):
                    logger.info(
                        "Skipping %s: registered under %s, not vitiligo",
                        trial.source_id,
                        trial.conditions or "no condition",
                    )
                    skipped += 1
                    continue
                if should_skip_ictrp_record(
                    trial,
                    skip_duplicates=skip_duplicates,
                    existing_keys=existing_keys,
                    existing_protocol_ids=protocol_ids,
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


def _load_protocol_ids(session) -> set[str]:  # type: ignore[no-untyped-def]
    """Sponsor protocol numbers that identify exactly one trial we hold.

    A European record names the sponsor's protocol, not the NCT, so this is
    the only thing linking EUCTR2019-000846-37-FR to NCT04052425. A number
    two trials both cite identifies neither, so it is dropped: among vitiligo
    trials that is "TARGETDERM", a cohort name rather than a protocol, and
    matching on it would skip a real trial as a duplicate.
    """
    claimed: dict[str, set[str]] = {}
    rows = session.exec(
        select(Trial.source_id, Trial.raw_metadata).where(Trial.source == TrialSourceKind.CTGOV)
    ).all()
    for source_id, metadata in rows:
        identification = (((metadata or {}).get("study") or {}).get("protocolSection") or {}).get(
            "identificationModule"
        ) or {}
        candidates = [(identification.get("orgStudyIdInfo") or {}).get("id")]
        candidates += [s.get("id") for s in (identification.get("secondaryIdInfos") or [])]
        for candidate in candidates:
            if not candidate:
                continue
            normalized = normalize_protocol_id(str(candidate))
            if len(normalized) >= 6:
                claimed.setdefault(normalized, set()).add(source_id)
    return {key for key, owners in claimed.items() if len(owners) == 1}


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
    """Insert a new trial or update the existing row keyed by (source, source_id).

    Country names are canonicalised on the way in, because the country filter
    matches the stored string: ClinicalTrials.gov files Turkey as "Turkey
    (Türkiye)" and ICTRP's partners as "Turkey", and a reader searching for
    one found a seventh of the trials.
    """
    trial.countries = normalize_countries(trial.countries or [])
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
