"""Repair corpora built before ingestion fixes, without re-fetching from sources.

Two known defects in corpora built with v1.0.0:

- PubMed titles with inline markup (``CD8<sup>+</sup>``) were truncated at the
  first tag. The original ``ArticleTitle`` XML is stored in
  ``raw_metadata.pubmed_xml_excerpt``, so titles are re-derived from it with
  the current parser.
- GEO ingestion stored samples (GSM) and other non-series records as datasets.
  Those documents are removed; the current parser would no longer create them.

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
from vitiligo.sources.pubmed import full_text
from vitiligo.storage import Document, Embedding, SourceKind, session_scope
from vitiligo.storage.models import GraphExtraction

logger = get_logger(__name__)

_ARTICLE_TITLE_RE = re.compile(r"<ArticleTitle(?:\s[^>]*)?>.*?</ArticleTitle>", re.DOTALL)


@dataclass
class RepairStats:
    applied: bool
    pubmed_titles_fixed: int = 0
    geo_documents_removed: int = 0
    embeddings_dropped: int = 0
    title_examples: list[tuple[str, str | None, str]] = field(default_factory=list)


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


def repair_corpus(*, apply: bool = False, max_examples: int = 5) -> RepairStats:
    """Fix truncated PubMed titles and remove non-series GEO documents.

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
                for extraction in session.exec(
                    select(GraphExtraction).where(GraphExtraction.document_id == doc.id)
                ).all():
                    session.delete(extraction)
                session.delete(doc)

        if not apply:
            session.rollback()

    logger.info(
        "Corpus repair (%s): pubmed_titles=%d geo_removed=%d embeddings_dropped=%d",
        "applied" if apply else "dry run",
        stats.pubmed_titles_fixed,
        stats.geo_documents_removed,
        stats.embeddings_dropped,
    )
    return stats
