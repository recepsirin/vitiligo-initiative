"""ClinicalTrials.gov (US NIH) source client — API v2.

API docs: https://clinicaltrials.gov/data-api/api

We use the public REST endpoint at https://clinicaltrials.gov/api/v2/studies
which returns rich JSON for every registered study. No auth is required.
A polite User-Agent and a small per-request delay keep us well within
NIH's rate guidance.

The parser is defensive: every nested module may be absent or partial,
so each helper falls back to None / [] rather than raising.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from vitiligo.config import Settings, get_settings
from vitiligo.logging import get_logger
from vitiligo.storage.models import Trial, TrialSourceKind

logger = get_logger(__name__)

STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"

DEFAULT_VITILIGO_QUERY = "vitiligo"
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000


@dataclass(frozen=True)
class SearchHandle:
    """Result of an initial CT.gov search."""

    total: int
    query: str


class CTGovClient:
    """Thin client over the ClinicalTrials.gov v2 REST API."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        request_delay_s: float = 0.2,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "User-Agent": "vitiligo-initiative/0.1 (+https://github.com/recepsirin/vitiligo-initiative)",
                "Accept": "application/json",
            },
        )
        self._delay = request_delay_s
        self._last_request_ts = 0.0

    def __enter__(self) -> CTGovClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

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
    def _get(self, params: dict[str, Any]) -> httpx.Response:
        self._throttle()
        response = self._client.get(STUDIES_URL, params=params)
        response.raise_for_status()
        return response

    def search_count(self, query: str = DEFAULT_VITILIGO_QUERY) -> int:
        """Return the total number of trials matching `query`."""
        response = self._get(
            {
                "query.cond": query,
                "pageSize": 1,
                "countTotal": "true",
                "format": "json",
            }
        )
        data = response.json()
        return int(data.get("totalCount") or 0)

    def search(self, query: str = DEFAULT_VITILIGO_QUERY) -> SearchHandle:
        total = self.search_count(query)
        logger.info("ClinicalTrials.gov search matched %d trials for '%s'", total, query)
        return SearchHandle(total=total, query=query)

    def iter_trials(
        self,
        query: str = DEFAULT_VITILIGO_QUERY,
        page_size: int = DEFAULT_PAGE_SIZE,
        limit: int | None = None,
    ) -> Iterator[Trial]:
        """Yield all trials matching `query`, paginated via `nextPageToken`."""
        page_size = min(page_size, MAX_PAGE_SIZE)
        page_token: str | None = None
        emitted = 0

        while True:
            params: dict[str, Any] = {
                "query.cond": query,
                "pageSize": page_size,
                "format": "json",
            }
            if page_token:
                params["pageToken"] = page_token

            response = self._get(params)
            data = response.json()

            studies = data.get("studies", [])
            if not studies:
                break

            logger.info(
                "ClinicalTrials.gov page: fetched=%d (%d so far)",
                len(studies),
                emitted + len(studies),
            )
            for study in studies:
                try:
                    trial = parse_ctgov_study(study)
                    if trial is None:
                        continue
                except Exception as exc:
                    nct = (
                        study.get("protocolSection", {})
                        .get("identificationModule", {})
                        .get("nctId")
                    )
                    logger.warning("Failed to parse CT.gov study NCT=%s: %s", nct, exc)
                    continue

                yield trial
                emitted += 1
                if limit is not None and emitted >= limit:
                    return

            page_token = data.get("nextPageToken")
            if not page_token:
                break


# ---------------------------------------------------------------------- parsing


def parse_ctgov_study(study: dict[str, Any]) -> Trial | None:
    """Parse a single CT.gov v2 `study` JSON object into a `Trial`."""
    protocol = study.get("protocolSection") or {}
    ident = protocol.get("identificationModule") or {}
    nct_id = (ident.get("nctId") or "").strip()
    if not nct_id:
        return None

    status_mod = protocol.get("statusModule") or {}
    desc_mod = protocol.get("descriptionModule") or {}
    cond_mod = protocol.get("conditionsModule") or {}
    design_mod = protocol.get("designModule") or {}
    arms_mod = protocol.get("armsInterventionsModule") or {}
    out_mod = protocol.get("outcomesModule") or {}
    elig_mod = protocol.get("eligibilityModule") or {}
    contacts_mod = protocol.get("contactsLocationsModule") or {}
    sponsor_mod = protocol.get("sponsorCollaboratorsModule") or {}

    enrollment = (design_mod.get("enrollmentInfo") or {})
    locations = contacts_mod.get("locations") or []
    countries = sorted(
        {(loc.get("country") or "").strip() for loc in locations if loc.get("country")}
    )

    return Trial(
        source=TrialSourceKind.CTGOV,
        source_id=nct_id,
        brief_title=ident.get("briefTitle") or None,
        official_title=ident.get("officialTitle") or None,
        summary=(desc_mod.get("briefSummary") or "").strip() or None,
        status=status_mod.get("overallStatus"),
        last_known_status=status_mod.get("lastKnownStatus"),
        study_type=design_mod.get("studyType"),
        phases=list(design_mod.get("phases") or []),
        conditions=list(cond_mod.get("conditions") or []),
        keywords=list(cond_mod.get("keywords") or []),
        interventions=_normalize_interventions(arms_mod.get("interventions") or []),
        arm_groups=_normalize_arm_groups(arms_mod.get("armGroups") or []),
        sponsors=_normalize_sponsors(sponsor_mod),
        locations=_normalize_locations(locations),
        countries=countries,
        primary_outcomes=_normalize_outcomes(out_mod.get("primaryOutcomes") or []),
        secondary_outcomes=_normalize_outcomes(out_mod.get("secondaryOutcomes") or []),
        enrollment_count=enrollment.get("count"),
        enrollment_type=enrollment.get("type"),
        eligibility_criteria=elig_mod.get("eligibilityCriteria"),
        sex=elig_mod.get("sex"),
        minimum_age=elig_mod.get("minimumAge"),
        maximum_age=elig_mod.get("maximumAge"),
        healthy_volunteers=elig_mod.get("healthyVolunteers"),
        start_date=_date_struct(status_mod.get("startDateStruct")),
        primary_completion_date=_date_struct(status_mod.get("primaryCompletionDateStruct")),
        completion_date=_date_struct(status_mod.get("completionDateStruct")),
        first_posted_date=_date_struct(status_mod.get("studyFirstPostDateStruct")),
        last_update_date=_date_struct(status_mod.get("lastUpdatePostDateStruct")),
        has_results=bool(study.get("hasResults")),
        raw_metadata={"nct_id": nct_id, "study": study},
    )


def _date_struct(struct: dict[str, Any] | None) -> str | None:
    if not isinstance(struct, dict):
        return None
    return struct.get("date") or None


def _normalize_interventions(interventions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": iv.get("type"),
            "name": iv.get("name"),
            "description": iv.get("description"),
            "other_names": list(iv.get("otherNames") or []),
        }
        for iv in interventions
    ]


def _normalize_arm_groups(arms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": a.get("label"),
            "type": a.get("type"),
            "description": a.get("description"),
            "intervention_names": list(a.get("interventionNames") or []),
        }
        for a in arms
    ]


def _normalize_sponsors(sponsor_mod: dict[str, Any]) -> list[dict[str, Any]]:
    sponsors: list[dict[str, Any]] = []
    lead = sponsor_mod.get("leadSponsor") or {}
    if lead:
        sponsors.append(
            {
                "role": "lead",
                "name": lead.get("name"),
                "class": lead.get("class"),
            }
        )
    for c in sponsor_mod.get("collaborators") or []:
        sponsors.append(
            {
                "role": "collaborator",
                "name": c.get("name"),
                "class": c.get("class"),
            }
        )
    return sponsors


def _normalize_locations(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "facility": loc.get("facility"),
            "status": loc.get("status"),
            "city": loc.get("city"),
            "state": loc.get("state"),
            "country": loc.get("country"),
        }
        for loc in locations
    ]


def _normalize_outcomes(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "measure": o.get("measure"),
            "description": o.get("description"),
            "time_frame": o.get("timeFrame"),
        }
        for o in outcomes
    ]
