"""NIH RePORTER: which vitiligo research the US government is paying for.

Everything else in the corpus is finished work — papers written, trials
registered, data deposited. Funded projects are the opposite: they say what
is being attempted now, years before any of it is published, and they name
the people attempting it.

That answers a question the evidence cannot. The roadmap's slowest items wait
on a person — a reviewer who will read the JAK findings, a biostatistician
for the patient-level data request, a clinical lead for the maintenance
trial. Active grants identify who works on a question today, at which
institution, with money to do it.

Read it for what it is. An award is a plan, not a result: projects are funded
on promise, change direction, and often end without publishing. Nothing here
is evidence about vitiligo, and none of it belongs in an evidence count.

API: https://api.reporter.nih.gov/ (v2, POST, no key required)
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from vitiligo.logging import get_logger
from vitiligo.storage.models import ResearchProject, ResearchSourceKind

logger = get_logger(__name__)

SEARCH_URL = "https://api.reporter.nih.gov/v2/projects/search"
DEFAULT_VITILIGO_QUERY = "vitiligo"
DEFAULT_PAGE_SIZE = 100
# The API rejects offsets beyond this; a trait with more projects needs
# splitting by fiscal year rather than paging further.
MAX_OFFSET = 14_999

SEARCH_FIELDS = "projecttitle,abstracttext,terms"


@dataclass(frozen=True)
class ReporterPage:
    """One page of results, with the total the API reports."""

    total: int
    results: list[dict[str, Any]]


class ReporterClient:
    """Thin client over the NIH RePORTER v2 search API."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(120.0, connect=20.0),
            headers={"User-Agent": "vitiligo-initiative/1.0 (research)"},
        )
        self._owns_client = client is None

    def __enter__(self) -> ReporterClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(
        self, query: str = DEFAULT_VITILIGO_QUERY, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE
    ) -> ReporterPage:
        payload = {
            "criteria": {
                "advanced_text_search": {
                    "operator": "and",
                    "search_field": SEARCH_FIELDS,
                    "search_text": query,
                }
            },
            "offset": offset,
            "limit": limit,
        }
        response = self._client.post(SEARCH_URL, json=payload)
        response.raise_for_status()
        body = response.json()
        return ReporterPage(
            total=int(body.get("meta", {}).get("total", 0)),
            results=list(body.get("results") or []),
        )

    def iter_projects(
        self, query: str = DEFAULT_VITILIGO_QUERY, page_size: int = DEFAULT_PAGE_SIZE
    ) -> Iterator[dict[str, Any]]:
        """Every project the query matches, a page at a time."""
        offset = 0
        total: int | None = None
        while True:
            page = self.search(query, offset=offset, limit=page_size)
            if total is None:
                total = page.total
                logger.info("NIH RePORTER: %d project(s) for %r", total, query)
            if not page.results:
                return
            yield from page.results
            offset += len(page.results)
            if offset >= total or offset > MAX_OFFSET:
                if offset > MAX_OFFSET:
                    logger.warning("NIH RePORTER: stopping at the API's offset limit")
                return


def _investigators(record: dict[str, Any]) -> list[dict[str, Any]]:
    people = record.get("principal_investigators") or []
    return [p for p in people if isinstance(p, dict)]


def _date(value: Any) -> str | None:
    return str(value)[:10] if value else None


def to_project(record: dict[str, Any]) -> ResearchProject | None:
    """One API record as a stored row, or ``None`` when it has no project number."""
    project_num = str(record.get("project_num") or "").strip()
    if not project_num:
        return None
    org = record.get("organization") or {}
    people = _investigators(record)
    contact = next((p for p in people if p.get("is_contact_pi")), people[0] if people else {})
    return ResearchProject(
        source=ResearchSourceKind.NIH_REPORTER,
        source_id=project_num,
        core_project_num=str(record.get("core_project_num") or "").strip() or None,
        title=str(record.get("project_title") or "").strip() or None,
        abstract=str(record.get("abstract_text") or "").strip() or None,
        contact_pi=str(contact.get("full_name") or "").strip() or None,
        contact_pi_profile_id=(
            str(contact.get("profile_id")) if contact.get("profile_id") is not None else None
        ),
        investigators=[str(p.get("full_name") or "").strip() for p in people if p.get("full_name")],
        organization=str(org.get("org_name") or "").strip() or None,
        org_city=str(org.get("org_city") or "").strip() or None,
        org_state=str(org.get("org_state") or "").strip() or None,
        org_country=str(org.get("org_country") or "").strip() or None,
        fiscal_year=int(record["fiscal_year"]) if record.get("fiscal_year") else None,
        award_amount=int(record["award_amount"]) if record.get("award_amount") else None,
        agency=str((record.get("agency_ic_admin") or {}).get("abbreviation") or "").strip() or None,
        activity_code=str(record.get("activity_code") or "").strip() or None,
        is_active=bool(record.get("is_active")),
        project_start=_date(record.get("project_start_date")),
        project_end=_date(record.get("project_end_date")),
        terms=str(record.get("pref_terms") or "").strip() or None,
        project_url=str(record.get("project_detail_url") or "").strip() or None,
        raw_metadata=record,
        retrieved_at=datetime.now(UTC),
    )
