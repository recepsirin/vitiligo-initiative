"""Open-access full text from wherever the publisher put it.

PMC is the only full-text source this project reads, and PMC holds 44 of the
522 published vitiligo trials. Unpaywall holds the rest of the map: of 463
trials with a DOI it finds a free copy for 154, most of them on the
publisher's own site and invisible to PMC.

A free copy is not the same as a copy we may take, so this module reads the
licence and not the price.

**Only a Creative Commons licence is fetched.** A CC licence grants copying;
"bronze" open access -- free to read on the publisher's page, no licence at
all -- grants nothing, and 83 of the 154 are bronze or unlicensed. They are
deliberately left alone. The licence Unpaywall reports is recorded on every
document this module stores, so the basis for holding each one is auditable
afterwards rather than remembered.

**HTML is preferred over PDF.** Both carry the same tables, but HTML carries
them as markup. A PDF gives back lines of text with the columns already lost,
and a cell reading "23 (76.7%)" is worthless once it is no longer under
"Group 1 (n = 30)" -- which is the whole reason for going after full text
rather than settling for abstracts.

**A landing page is not a failure.** Nineteen of the reachable papers resolve
through doi.org to a publisher page that may answer with markup, a JavaScript
shell or a refusal. The fetch records which, because "Elsevier served a shell"
and "we never asked" are different facts and only one of them is worth
retrying.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from vitiligo.config import get_settings
from vitiligo.logging import get_logger
from vitiligo.sources.raw_cache import DEFAULT_RAW_CACHE, load_payload, save_payload
from vitiligo.sources.tables import Table, has_data, render_tables, tables_from_html

logger = get_logger(__name__)

UNPAYWALL_URL = "https://api.unpaywall.org/v2/{doi}"
CACHE_SOURCE = "oa-fulltext"
USER_AGENT = (
    "vitiligo-initiative/0.1 (non-profit vitiligo research; "
    "+https://github.com/recepsirin/vitiligo-initiative)"
)
REQUEST_TIMEOUT = 60.0


@dataclass(frozen=True)
class OpenCopy:
    """Where a paper's open copy is, and on what terms."""

    doi: str
    licence: str
    host_type: str
    version: str
    url: str
    pdf_url: str | None = None

    @property
    def may_fetch(self) -> bool:
        """True only for a Creative Commons licence.

        Everything else Unpaywall calls open access is free to read rather
        than free to copy, and this project does not treat the two as the
        same thing.
        """
        return self.licence.lower().startswith("cc")

    @property
    def best_url(self) -> str:
        """The markup first; the PDF only when there is no page to read."""
        return self.url or (self.pdf_url or "")

    @property
    def candidate_urls(self) -> list[str]:
        """Every address worth trying, markup first.

        Thirteen of the forty reachable papers answered their landing page
        with a JavaScript shell -- a couple of kilobytes that render into an
        article in a browser and into nothing here. The PDF behind the same
        record is a separate address and often answers properly, so one
        refusal is not the end of the record.
        """
        urls = [u for u in (self.url, self.pdf_url) if u]
        return list(dict.fromkeys(urls))


def find_open_copy(doi: str, *, client: httpx.Client, email: str | None = None) -> OpenCopy | None:
    """Ask Unpaywall where a DOI's open copy is.

    Returns ``None`` when there is none, when Unpaywall does not know the DOI,
    or when no contact address is configured -- Unpaywall requires one on
    every call, so without it this source is simply off.
    """
    address = email if email is not None else get_settings().unpaywall_email
    if not address:
        logger.info("Unpaywall needs a contact address (UNPAYWALL_EMAIL); skipping %s", doi)
        return None
    try:
        response = client.get(UNPAYWALL_URL.format(doi=doi), params={"email": address})
        if response.status_code != 200:
            return None
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Unpaywall failed for %s: %s", doi, exc)
        return None
    if not payload.get("is_oa"):
        return None
    best = payload.get("best_oa_location") or {}
    return OpenCopy(
        doi=doi,
        licence=str(best.get("license") or ""),
        host_type=str(best.get("host_type") or ""),
        version=str(best.get("version") or ""),
        url=str(best.get("url") or ""),
        pdf_url=str(best.get("url_for_pdf")) if best.get("url_for_pdf") else None,
    )


def _cache_name(doi: str, suffix: str) -> str:
    return f"{re.sub(r'[^A-Za-z0-9]+', '-', doi).strip('-')}{suffix}"


def fetch_open_copy(
    copy: OpenCopy,
    *,
    client: httpx.Client,
    cache: Path | None = DEFAULT_RAW_CACHE,
    refresh: bool = False,
    url: str | None = None,
) -> tuple[bytes, str] | None:
    """The bytes of an open copy, with the content type the server declared.

    Refuses anything without a Creative Commons licence. Served payloads are
    cached, so re-reading a figure months later does not depend on the
    publisher still being up or still being generous.
    """
    if not copy.may_fetch:
        logger.info("Not fetching %s: licence is %r, not Creative Commons", copy.doi, copy.licence)
        return None
    target = url or copy.best_url
    if not target:
        return None

    suffix = ".pdf" if target.lower().endswith(".pdf") else ".html"
    name = _cache_name(copy.doi, suffix)
    if cache is not None and not refresh:
        cached = load_payload(CACHE_SOURCE, name, cache)
        if cached is not None:
            return cached, "application/pdf" if suffix == ".pdf" else "text/html"

    try:
        response = client.get(target, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.info("No open copy served for %s: %s", copy.doi, type(exc).__name__)
        return None

    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    payload = response.content
    if cache is not None:
        save_payload(CACHE_SOURCE, name, payload, url=target, cache=cache)
    return payload, content_type


def read_open_copy(
    copy: OpenCopy,
    *,
    client: httpx.Client,
    cache: Path | None = DEFAULT_RAW_CACHE,
    refresh: bool = False,
    minimum_chars: int = 2000,
) -> tuple[str, list[Table]] | None:
    """The text and tables of an open copy, trying each address it has.

    An answer counts when it carries a table or enough text to be an article.
    A landing page that renders in a browser arrives here as a couple of
    kilobytes of script, which is neither, so the next address is tried.
    """
    for url in copy.candidate_urls:
        got = fetch_open_copy(copy, client=client, cache=cache, refresh=refresh, url=url)
        if got is None:
            continue
        text, tables = read_payload(*got)
        if any(has_data(t) for t in tables) or len(text) >= minimum_chars:
            return text, tables
        logger.info("%s answered %s with nothing readable", copy.doi, url)
    return None


def text_from_pdf(payload: bytes) -> str:
    """A PDF's text, where ``pypdf`` is installed.

    The columns are gone by the time a PDF is laid out, so this is prose with
    the table cells strung along one line. It is a fallback, not a substitute
    for a page of markup.
    """
    try:
        from io import BytesIO

        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - optional extra
        logger.info("pypdf is not installed; install the 'papers' extra to read PDFs")
        return ""
    try:
        reader = PdfReader(BytesIO(payload))
        return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    except Exception as exc:  # pragma: no cover - a malformed PDF is a fact, not a bug
        logger.warning("Could not read the PDF: %s", exc)
        return ""


def read_payload(payload: bytes, content_type: str) -> tuple[str, list[Table]]:
    """``(text, tables)`` from whatever the server sent."""
    if "pdf" in content_type or payload[:5] == b"%PDF-":
        return text_from_pdf(payload), []
    tables = tables_from_html(payload)
    rendered = render_tables(tables)
    return rendered, tables
