"""PubMed Central (PMC) Open Access source client.

PMC hosts full-text biomedical articles. We target the Open Access
subset, which we can fetch and redistribute under each article's
licence (typically CC-BY / CC-BY-NC). Articles outside OA can still be
searched but the full text is not available via efetch.

We use the same NCBI E-utilities endpoints as PubMed, just with
`db=pmc`, and parse the returned JATS XML to extract structured
sections (introduction, methods, results, discussion) alongside the
standard metadata fields.

API docs:
- https://www.ncbi.nlm.nih.gov/books/NBK25500/
- https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/
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

# Vitiligo across PMC, limited to Open Access (full text is fetchable).
DEFAULT_VITILIGO_QUERY = (
    '("vitiligo"[MeSH Terms] OR "vitiligo"[Title/Abstract]) AND "open access"[filter]'
)

# PMC payloads are large (full text). Keep batches small.
DEFAULT_BATCH_SIZE = 50


@dataclass(frozen=True)
class SearchHandle:
    """Result of a PMC esearch call."""

    total: int
    web_env: str
    query_key: str
    query: str


class PMCClient:
    """Thin client over NCBI E-utilities for PubMed Central (Open Access)."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        request_delay_s: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "User-Agent": f"{self.settings.ncbi_tool}/0.1 (+https://github.com/recepsirin/vitiligo-initiative)",
                "Accept": "application/xml",
            },
        )
        if request_delay_s is None:
            request_delay_s = 0.12 if self.settings.ncbi_api_key else 0.35
        self._delay = request_delay_s
        self._last_request_ts = 0.0

    def __enter__(self) -> PMCClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

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
        response.raise_for_status()
        return response

    def search(self, query: str = DEFAULT_VITILIGO_QUERY) -> SearchHandle:
        params: dict[str, Any] = {
            "db": "pmc",
            "term": query,
            "usehistory": "y",
            "retmax": 0,
            "retmode": "xml",
            **self._identity_params(),
        }
        logger.info("PMC esearch: %s", query)
        response = self._get(ESEARCH_URL, params)
        root = etree.fromstring(response.content)

        count_el = root.find("Count")
        webenv_el = root.find("WebEnv")
        querykey_el = root.find("QueryKey")
        if count_el is None or webenv_el is None or querykey_el is None:
            raise RuntimeError("PMC esearch response missing expected fields.")

        total = int(count_el.text or 0)
        logger.info("PMC esearch matched %d records", total)
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
        params: dict[str, Any] = {
            "db": "pmc",
            "WebEnv": handle.web_env,
            "query_key": handle.query_key,
            "retstart": retstart,
            "retmax": retmax,
            "retmode": "xml",
            **self._identity_params(),
        }
        response = self._get(EFETCH_URL, params)
        return list(parse_pmc_xml(response.content))

    def iter_documents(
        self,
        query: str = DEFAULT_VITILIGO_QUERY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        limit: int | None = None,
    ) -> Iterator[Document]:
        handle = self.search(query)
        total = handle.total if limit is None else min(handle.total, limit)
        retstart = 0
        while retstart < total:
            this_batch = min(batch_size, total - retstart)
            logger.info(
                "PMC efetch batch retstart=%d retmax=%d (of %d)",
                retstart,
                this_batch,
                total,
            )
            docs = self.fetch_batch(handle, retstart=retstart, retmax=this_batch)
            yield from docs
            retstart += this_batch


# ---------------------------------------------------------------------- parsing

# Section titles we care to extract individually. Everything else falls into "other".
_SECTION_KEYWORDS = {
    "introduction": "introduction",
    "background": "introduction",
    "methods": "methods",
    "materials and methods": "methods",
    "patients and methods": "methods",
    "results": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
}


def parse_pmc_xml(xml_bytes: bytes) -> Iterator[Document]:
    """Yield normalized `Document` instances from a PMC efetch XML payload."""
    # PMC sometimes returns a single <article> root and sometimes a <pmc-articleset>.
    root = etree.fromstring(xml_bytes)
    articles = root.iterfind(".//article") if root.tag != "article" else [root]
    for article in articles:
        try:
            doc = _parse_pmc_article(article)
            if doc is not None:
                yield doc
        except Exception as exc:
            logger.warning("Failed to parse PMC article: %s", exc)


def _parse_pmc_article(article: etree._Element) -> Document | None:
    pmcid = _extract_article_id(article, "pmc")
    pmid = _extract_article_id(article, "pmid")
    doi = _extract_article_id(article, "doi")
    source_id = pmcid or pmid or doi
    if not source_id:
        return None

    title = _findtext(article, ".//front//article-title")
    journal = _findtext(article, ".//front//journal-title")
    year = _parse_year(article)
    language = article.get("{http://www.w3.org/XML/1998/namespace}lang")
    abstract = _collect_abstract(article)
    authors = _parse_authors(article)
    keywords = _parse_keywords(article)
    publication_types = [article.get("article-type")] if article.get("article-type") else []
    sections, full_text = _collect_body(article)

    raw: dict[str, Any] = {
        "pmcid": pmcid,
        "pmid": pmid,
        "doi": doi,
        "sections": sections,
        "full_text": full_text,
    }

    return Document(
        source=SourceKind.PMC,
        source_id=source_id,
        title=title,
        abstract=abstract,
        journal=journal,
        year=year,
        doi=doi,
        language=language,
        authors=authors,
        mesh_terms=[],  # PMC carries them inconsistently; can be merged from PubMed later.
        keywords=keywords,
        publication_types=publication_types,
        raw_metadata=raw,
    )


_ID_TYPE_ALIASES: dict[str, set[str]] = {
    "pmc": {"pmc", "pmcid"},
    "pmid": {"pmid", "pubmed"},
    "doi": {"doi"},
}


def _extract_article_id(article: etree._Element, id_type: str) -> str | None:
    aliases = _ID_TYPE_ALIASES.get(id_type, {id_type})
    for aid in article.iterfind(".//article-id"):
        if (aid.get("pub-id-type") or "").lower() in aliases and aid.text:
            return aid.text.strip()
    return None


def _findtext(el: etree._Element, xpath: str) -> str | None:
    found = el.find(xpath)
    if found is None:
        return None
    text = "".join(found.itertext()).strip()
    return text or None


def _parse_year(article: etree._Element) -> int | None:
    for xpath in (".//pub-date/year", ".//pub-date"):
        el = article.find(xpath)
        if el is None:
            continue
        text = "".join(el.itertext()).strip()
        digits = "".join(ch for ch in text[:8] if ch.isdigit())
        if len(digits) >= 4:
            try:
                return int(digits[:4])
            except ValueError:
                continue
    return None


def _collect_abstract(article: etree._Element) -> str | None:
    parts: list[str] = []
    for ab in article.iterfind(".//front//abstract"):
        text = " ".join("".join(p.itertext()).strip() for p in ab.iter() if p.text)
        text = text.strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts) if parts else None


def _parse_authors(article: etree._Element) -> list[dict[str, Any]]:
    authors: list[dict[str, Any]] = []
    for contrib in article.iterfind(".//contrib[@contrib-type='author']"):
        last = _findtext(contrib, ".//surname")
        fore = _findtext(contrib, ".//given-names")
        entry: dict[str, Any] = {}
        if last:
            entry["last"] = last
        if fore:
            entry["fore"] = fore
        if entry:
            authors.append(entry)
    return authors


def _parse_keywords(article: etree._Element) -> list[str]:
    keywords: list[str] = []
    for kw in article.iterfind(".//kwd"):
        text = "".join(kw.itertext()).strip()
        if text:
            keywords.append(text)
    return keywords


def _collect_body(article: etree._Element) -> tuple[dict[str, str], str]:
    """Return (sections-by-canonical-name, full_text)."""
    sections: dict[str, list[str]] = {}
    body = article.find(".//body")
    if body is None:
        return {}, ""

    for sec in body.iterfind("./sec"):
        title = _findtext(sec, "./title") or ""
        text_parts: list[str] = []
        for p in sec.iter("p"):
            t = " ".join("".join(p.itertext()).split()).strip()
            if t:
                text_parts.append(t)
        section_text = "\n\n".join(text_parts).strip()
        if not section_text:
            continue
        canonical = _SECTION_KEYWORDS.get(title.lower().strip(), title or "other")
        sections.setdefault(canonical, []).append(section_text)

    merged = {name: "\n\n".join(parts) for name, parts in sections.items()}
    full_text = "\n\n".join(f"## {name.title()}\n\n{text}" for name, text in merged.items())
    return merged, full_text
