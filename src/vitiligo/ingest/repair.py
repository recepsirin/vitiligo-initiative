"""Repair corpora built before ingestion fixes, without re-fetching from sources.

Two known defects in corpora built with v1.0.0:

- PubMed titles with inline markup (``CD8<sup>+</sup>``) were truncated at the
  first tag. The original ``ArticleTitle`` XML is stored in
  ``raw_metadata.pubmed_xml_excerpt``, so titles are re-derived from it with
  the current parser.
- GEO ingestion stored samples (GSM) and other non-series records as datasets.
  Those documents are removed; the current parser would no longer create them.

A third defect is not version-specific and will recur: a trial reconstructed
from a paper was judged by whatever the gate said on the day it was ingested,
and the gate has been wrong. It once read only digits and missed "Twenty-two
patients"; it once let the abstract decide and admitted 120 case-control and
epidemiology papers, because "148 patients were classified" and "148 patients
were randomised" are the same sentence to a pattern. Records admitted by an
older gate are re-judged against the current one.

Documents whose title changes lose their embeddings so ``vitiligo embed run``
re-embeds them. Nothing is written unless ``apply=True``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree
from sqlmodel import Session, select

from vitiligo.logging import get_logger
from vitiligo.sources.geo import parse_geo_summary
from vitiligo.sources.published_trials import (
    countries_of,
    observes_vitiligo_under_immunotherapy,
    reports_a_trial,
)
from vitiligo.sources.pubmed import full_text
from vitiligo.storage import Document, Embedding, SourceKind, session_scope
from vitiligo.storage.models import Trial, TrialSourceKind
from vitiligo.trials.countries import normalize_countries
from vitiligo.trials.relevance import VITILIGO_AS_OUTCOME_SCOPE, studies_vitiligo

logger = get_logger(__name__)

_ARTICLE_TITLE_RE = re.compile(r"<ArticleTitle(?:\s[^>]*)?>.*?</ArticleTitle>", re.DOTALL)


@dataclass
class RepairStats:
    applied: bool
    pubmed_titles_fixed: int = 0
    geo_documents_removed: int = 0
    embeddings_dropped: int = 0
    paper_trials_rejudged: int = 0
    paper_countries_fixed: int = 0
    title_examples: list[tuple[str, str | None, str]] = field(default_factory=list)
    rejudged_examples: list[tuple[str, str | None]] = field(default_factory=list)
    country_examples: list[tuple[str, list[str], list[str]]] = field(default_factory=list)


def title_from_excerpt(excerpt: str | None) -> str | None:
    """Re-derive a PubMed title from the stored XML excerpt (None if unavailable)."""
    if not excerpt:
        return None
    match = _ARTICLE_TITLE_RE.search(excerpt)
    if match is None:
        return None
    try:
        fragment = etree.fromstring(f"<wrap>{match.group(0)}</wrap>".encode())
    except etree.XMLSyntaxError:
        return None
    return full_text(fragment, "ArticleTitle")


def _drop_embeddings(session: Session, document_id: int) -> int:
    rows = session.exec(select(Embedding).where(Embedding.document_id == document_id)).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def _rejudge_paper_trials(
    session: Session, stats: RepairStats, apply: bool, max_examples: int
) -> None:
    """Drop every trial built from a paper the current gate would not admit.

    The paper stays in the corpus; only the claim that it reports a trial
    goes. Each stratum is judged by its own gate, because they ask different
    questions: whether this paper reports a trial of vitiligo, or whether it
    reports a cancer immunotherapy trial in which vitiligo appeared.
    """
    trials = session.exec(select(Trial).where(Trial.source == TrialSourceKind.PUBLICATION)).all()
    documents = {(doc.source, doc.source_id): doc for doc in session.exec(select(Document)).all()}
    for trial in trials:
        document = documents.get((SourceKind.PUBMED, trial.source_id)) or documents.get(
            (SourceKind.CROSSREF, trial.source_id)
        )
        if document is None:
            # The paper is gone, so nothing can re-judge it. Leaving the
            # trial is the lesser wrong: it was admitted on evidence once.
            continue
        scope = (trial.raw_metadata or {}).get("scope")
        if scope == VITILIGO_AS_OUTCOME_SCOPE:
            keep = observes_vitiligo_under_immunotherapy(document)
        else:
            keep = studies_vitiligo(
                document.title or "", document.abstract or ""
            ) and reports_a_trial(document)
        if keep:
            # The country comes from the affiliation, and how an affiliation
            # is read has changed: the list held 73 countries and now holds
            # every one, and a postal code, a city and an email domain are
            # read besides. A record the ingestion skips as already held
            # never sees that, so 42 Crossref papers kept an empty country
            # while their letterheads said Latvia, Egypt, India and Russia.
            countries = normalize_countries(countries_of(document))
            if countries != (trial.countries or []):
                stats.paper_countries_fixed += 1
                if len(stats.country_examples) < max_examples:
                    stats.country_examples.append(
                        (trial.source_id, trial.countries or [], countries)
                    )
                if apply:
                    trial.countries = countries
                    session.add(trial)
            continue
        stats.paper_trials_rejudged += 1
        if len(stats.rejudged_examples) < max_examples:
            stats.rejudged_examples.append((trial.source_id, trial.brief_title))
        if apply:
            session.delete(trial)


def repair_corpus(*, apply: bool = False, max_examples: int = 5) -> RepairStats:
    """Fix truncated titles, drop non-series GEO records, re-judge paper trials.

    With ``apply=False`` (default) only counts what would change.
    """
    stats = RepairStats(applied=apply)
    with session_scope() as session:
        pubmed = session.exec(select(Document).where(Document.source == SourceKind.PUBMED)).all()
        for doc in pubmed:
            title = title_from_excerpt((doc.raw_metadata or {}).get("pubmed_xml_excerpt"))
            if title is None or title == doc.title:
                continue
            stats.pubmed_titles_fixed += 1
            if len(stats.title_examples) < max_examples:
                stats.title_examples.append((doc.source_id, doc.title, title))
            if apply:
                assert doc.id is not None
                stats.embeddings_dropped += _drop_embeddings(session, doc.id)
                doc.title = title
                session.add(doc)

        geo = session.exec(select(Document).where(Document.source == SourceKind.GEO)).all()
        for doc in geo:
            if parse_geo_summary(doc.raw_metadata or {}) is not None:
                continue
            stats.geo_documents_removed += 1
            if apply:
                assert doc.id is not None
                stats.embeddings_dropped += _drop_embeddings(session, doc.id)
                session.delete(doc)

        _rejudge_paper_trials(session, stats, apply, max_examples)

        if not apply:
            session.rollback()

    logger.info(
        "Corpus repair (%s): pubmed_titles=%d geo_removed=%d embeddings_dropped=%d "
        "paper_trials_rejudged=%d paper_countries_fixed=%d",
        "applied" if apply else "dry run",
        stats.pubmed_titles_fixed,
        stats.geo_documents_removed,
        stats.embeddings_dropped,
        stats.paper_trials_rejudged,
        stats.paper_countries_fixed,
    )
    return stats
