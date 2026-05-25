"""PubMed (NCBI E-utilities) source client.

We use the E-utilities REST API directly:
  - `esearch.fcgi` to find PMIDs matching a query (with history server).
  - `efetch.fcgi` to retrieve full XML records in batches.

API docs: https://www.ncbi.nlm.nih.gov/books/NBK25500/

Rate limits: 3 requests/second without an API key, 10/second with one.
We stay well under the limit with a conservative inter-request delay
and respect the `NCBI_TOOL` / `NCBI_EMAIL` identification fields NCBI
requires for programmatic access.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from lxml import etree
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from vitiligo.config import Settings, get_settings
from vitiligo.logging import get_logger
from vitiligo.storage.models import Document, SourceKind

logger = get_logger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Default query targeting vitiligo across MeSH and free text.
# Cast wide; we can filter downstream.
DEFAULT_VITILIGO_QUERY = '"vitiligo"[MeSH Terms] OR "vitiligo"[Title/Abstract]'

# Fetch in modest batches to keep requests small and resumable.
DEFAULT_BATCH_SIZE = 200


@dataclass(frozen=True)
class SearchHandle:
    """Result of an esearch call. WebEnv/QueryKey let us efetch without re-sending IDs."""

    total: int
    web_env: str
    query_key: str
    query: str


class PubMedClient:
    """Thin client over NCBI E-utilities for PubMed."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        request_delay_s: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "User-Agent": f"{self.settings.ncbi_tool}/0.1 (+https://github.com/recepsirin/vitiligo-initiative)",
                "Accept": "application/xml",
            },
        )
        # Respect rate limits: 10/s with key, 3/s without. Use a safety margin.
        if request_delay_s is None:
            request_delay_s = 0.12 if self.settings.ncbi_api_key else 0.35
        self._delay = request_delay_s
        self._last_request_ts = 0.0

    def __enter__(self) -> PubMedClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------------ helpers

    def _identity_params(self) -> dict[str, str]:
        params: dict[str, str] = {"tool": self.settings.ncbi_tool}
        if self.settings.ncbi_email:
            params["email"] = self.settings.ncbi_email
        if self.settings.ncbi_api_key:
            params["api_key"] = self.settings.ncbi_api_key
        return params

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = self._delay - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        self._throttle()
        response = self._client.get(url, params=params)
        # NCBI sometimes returns 429; tenacity retries on HTTPError.
        response.raise_for_status()
        return response

    # ------------------------------------------------------------------- public

    def search(self, query: str = DEFAULT_VITILIGO_QUERY) -> SearchHandle:
        """Run an esearch and return a handle (WebEnv/QueryKey) to fetch with."""
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "usehistory": "y",
            "retmax": 0,
            "retmode": "xml",
            **self._identity_params(),
        }
        logger.info("PubMed esearch: %s", query)
        response = self._get(ESEARCH_URL, params)
        root = etree.fromstring(response.content)

        count_el = root.find("Count")
        webenv_el = root.find("WebEnv")
        querykey_el = root.find("QueryKey")

        if count_el is None or webenv_el is None or querykey_el is None:
            raise RuntimeError("PubMed esearch response missing expected fields.")

        total = int(count_el.text or 0)
        logger.info("PubMed esearch matched %d records", total)

        return SearchHandle(
            total=total,
            web_env=webenv_el.text or "",
            query_key=querykey_el.text or "",
            query=query,
        )

    def fetch_batch(
        self,
        handle: SearchHandle,
        retstart: int,
        retmax: int = DEFAULT_BATCH_SIZE,
    ) -> list[Document]:
        """Fetch a single batch of full records from a prior esearch handle."""
        params: dict[str, Any] = {
            "db": "pubmed",
            "WebEnv": handle.web_env,
            "query_key": handle.query_key,
            "retstart": retstart,
            "retmax": retmax,
            "retmode": "xml",
            "rettype": "abstract",
            **self._identity_params(),
        }
        response = self._get(EFETCH_URL, params)
        return list(parse_pubmed_xml(response.content))

    def iter_documents(
        self,
        query: str = DEFAULT_VITILIGO_QUERY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        limit: int | None = None,
    ) -> Iterator[Document]:
        """Yield all documents matching `query`, fetching in batches.

        Args:
            query: PubMed query expression.
            batch_size: Number of records per efetch call (max 10_000).
            limit: Optional cap on total documents (useful for smoke tests).
        """
        handle = self.search(query)
        total = handle.total if limit is None else min(handle.total, limit)
        retstart = 0

        while retstart < total:
            this_batch = min(batch_size, total - retstart)
            logger.info(
                "PubMed efetch batch retstart=%d retmax=%d (of %d)",
                retstart,
                this_batch,
                total,
            )
            docs = self.fetch_batch(handle, retstart=retstart, retmax=this_batch)
            yield from docs
            retstart += this_batch


# ---------------------------------------------------------------------- parsing


def parse_pubmed_xml(xml_bytes: bytes) -> Iterator[Document]:
    """Yield normalized `Document` instances from a PubmedArticleSet XML payload."""
    root = etree.fromstring(xml_bytes)
    for article in root.iterfind(".//PubmedArticle"):
        try:
            yield _parse_article(article)
        except Exception as exc:
            pmid = _findtext(article, ".//PMID")
            logger.warning("Failed to parse PubMed article PMID=%s: %s", pmid, exc)


def _parse_article(article: etree._Element) -> Document:
    pmid = _findtext(article, ".//PMID") or ""
    if not pmid:
        raise ValueError("Article missing PMID")

    title = _findtext(article, ".//ArticleTitle")
    abstract = _collect_abstract(article)
    journal = _findtext(article, ".//Journal/Title")
    year = _parse_year(article)
    language = _findtext(article, ".//Language")
    doi = _extract_doi(article)
    authors = _parse_authors(article)
    mesh_terms = _parse_mesh(article)
    keywords = _parse_keywords(article)
    publication_types = [
        pt.text for pt in article.iterfind(".//PublicationTypeList/PublicationType") if pt.text
    ]

    raw = {
        "pmid": pmid,
        "pubmed_xml_excerpt": etree.tostring(article, encoding="unicode")[:8000],
    }

    return Document(
        source=SourceKind.PUBMED,
        source_id=pmid,
        title=title,
        abstract=abstract,
        journal=journal,
        year=year,
        doi=doi,
        language=language,
        authors=authors,
        mesh_terms=mesh_terms,
        keywords=keywords,
        publication_types=publication_types,
        raw_metadata=raw,
    )


def _findtext(el: etree._Element, xpath: str) -> str | None:
    found = el.findtext(xpath)
    return found.strip() if found else None


def _collect_abstract(article: etree._Element) -> str | None:
    """Join all AbstractText elements (some abstracts are split by section labels)."""
    parts: list[str] = []
    for ab in article.iterfind(".//Abstract/AbstractText"):
        label = ab.get("Label")
        text = "".join(ab.itertext()).strip()
        if not text:
            continue
        parts.append(f"{label}: {text}" if label else text)
    return "\n\n".join(parts) if parts else None


def _parse_year(article: etree._Element) -> int | None:
    for xpath in (
        ".//Article/Journal/JournalIssue/PubDate/Year",
        ".//Article/Journal/JournalIssue/PubDate/MedlineDate",
        ".//PubmedData/History/PubMedPubDate[@PubStatus='pubmed']/Year",
    ):
        text = _findtext(article, xpath)
        if not text:
            continue
        # MedlineDate is free-form like "2019 Spring" — take the first 4 digits.
        digits = "".join(ch for ch in text[:8] if ch.isdigit())
        if len(digits) >= 4:
            try:
                return int(digits[:4])
            except ValueError:
                continue
    return None


def _extract_doi(article: etree._Element) -> str | None:
    for aid in article.iterfind(".//ArticleIdList/ArticleId"):
        if (aid.get("IdType") or "").lower() == "doi" and aid.text:
            return aid.text.strip()
    return None


def _parse_authors(article: etree._Element) -> list[dict[str, Any]]:
    authors: list[dict[str, Any]] = []
    for author in article.iterfind(".//AuthorList/Author"):
        last = _findtext(author, "LastName")
        fore = _findtext(author, "ForeName")
        initials = _findtext(author, "Initials")
        collective = _findtext(author, "CollectiveName")
        affiliations = [
            (aff.text or "").strip()
            for aff in author.iterfind(".//AffiliationInfo/Affiliation")
            if (aff.text or "").strip()
        ]
        entry: dict[str, Any] = {}
        if collective:
            entry["collective"] = collective
        if last:
            entry["last"] = last
        if fore:
            entry["fore"] = fore
        if initials:
            entry["initials"] = initials
        if affiliations:
            entry["affiliations"] = affiliations
        if entry:
            authors.append(entry)
    return authors


def _parse_mesh(article: etree._Element) -> list[str]:
    terms: list[str] = []
    for heading in article.iterfind(".//MeshHeadingList/MeshHeading"):
        descriptor = _findtext(heading, "DescriptorName")
        if descriptor:
            terms.append(descriptor)
    return terms


def _parse_keywords(article: etree._Element) -> list[str]:
    return [
        (kw.text or "").strip()
        for kw in article.iterfind(".//KeywordList/Keyword")
        if (kw.text or "").strip()
    ]
