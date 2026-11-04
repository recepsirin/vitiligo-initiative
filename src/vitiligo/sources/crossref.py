"""Crossref source client — journal articles outside MEDLINE.

API docs: https://api.crossref.org

MEDLINE indexes about 5,500 journals. Crossref registers a DOI for almost
anything with one, which is where the rest of the trial literature is: the
*Journal of Pakistan Association of Dermatologists*, *Pigment International*,
*The Egyptian Journal of Hospital Medicine*, *Al-Azhar International Medical
Journal*, the *Chinese Journal of Dermatology*, and the conference abstracts
of the BJD, JAAD and JID. A title search for vitiligo returns 10,719 journal
articles, 4,111 of which this corpus held under no DOI and no title.

No key is needed. Crossref asks for a contact in the User-Agent and gives
pooled rate limits in return, so the address is the project's.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from vitiligo.logging import get_logger
from vitiligo.storage.models import Document, SourceKind

logger = get_logger(__name__)

WORKS_URL = "https://api.crossref.org/works"
USER_AGENT = (
    "vitiligo-initiative/0.1 (non-profit vitiligo research; "
    "+https://github.com/recepsirin/vitiligo-initiative)"
)
PAGE_SIZE = 200

_TAGS = re.compile(r"<[^>]+>")


class CrossrefClient:
    """Reads Crossref's works endpoint, one cursor page at a time."""

    def __init__(self, timeout: float = 90.0, delay: float = 0.5) -> None:
        self._delay = delay
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CrossrefClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _page(self, params: dict[str, str]) -> dict[str, Any]:
        response = self._client.get(WORKS_URL, params=params)
        response.raise_for_status()
        message: dict[str, Any] = response.json()["message"]
        return message

    def search_titles(self, term: str, page_size: int = PAGE_SIZE) -> Iterator[dict[str, Any]]:
        """Every journal article whose title matches ``term``.

        Crossref's title index is fuzzy, so "vitiligo" also returns papers
        that merely cite one. The caller's disease gate settles that; this
        drops only the works whose title does not contain the word at all,
        which is two thirds of what comes back.
        """
        cursor = "*"
        pages = 0
        while True:
            message = self._page(
                {
                    "query.title": term,
                    "rows": str(page_size),
                    "cursor": cursor,
                    "filter": "type:journal-article",
                }
            )
            items = message.get("items") or []
            if not items:
                return
            yield from items
            pages += 1
            cursor = message.get("next-cursor") or ""
            if not cursor:
                return
            if pages % 10 == 0:
                logger.info("Crossref: %d pages read", pages)
            time.sleep(self._delay)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def work(self, doi: str) -> dict[str, Any] | None:
        """One work in full, which is the only form that carries affiliations.

        The search response omits them, and the affiliation is where the
        country comes from, so a record worth keeping is fetched again.
        """
        response = self._client.get(f"{WORKS_URL}/{doi}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        message: dict[str, Any] = response.json()["message"]
        return message


def _text(parts: Any) -> str:
    if isinstance(parts, list):
        return " ".join(str(p) for p in parts).strip()
    return str(parts or "").strip()


def document_from_work(work: dict[str, Any]) -> Document | None:
    """A ``Document`` for a Crossref work, or ``None`` if it has no title.

    The authors are reshaped into the form ``countries_of`` reads, so a
    Crossref paper's country comes from the same affiliation parsing as a
    PubMed one rather than a second copy of it.
    """
    title = _text(work.get("title"))
    doi = str(work.get("DOI") or "").lower().strip()
    if not title or not doi:
        return None
    issued = (work.get("issued") or {}).get("date-parts") or [[None]]
    year = issued[0][0] if issued and issued[0] else None
    authors = [
        {
            "last": str(author.get("family") or "") or None,
            "first": str(author.get("given") or "") or None,
            "affiliations": [
                str(place.get("name") or "")
                for place in (author.get("affiliation") or [])
                if place.get("name")
            ],
        }
        for author in (work.get("author") or [])
    ]
    abstract = _TAGS.sub(" ", str(work.get("abstract") or "")).strip()
    return Document(
        source=SourceKind.CROSSREF,
        source_id=doi,
        title=title,
        abstract=abstract or None,
        journal=_text(work.get("container-title")) or None,
        year=int(year) if isinstance(year, int) else None,
        doi=doi,
        language=str(work.get("language") or "") or None,
        authors=authors,
        # Crossref has no publication-type vocabulary. Leaving this empty is
        # the honest record and makes the title the deciding evidence, which
        # for these journals it is.
        publication_types=[],
        raw_metadata={
            "doi": doi,
            "publisher": work.get("publisher"),
            "type": work.get("type"),
            "subject": work.get("subject") or [],
        },
    )
