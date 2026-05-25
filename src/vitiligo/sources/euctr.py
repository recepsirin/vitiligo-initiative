"""EU CTR / CTIS source client — Clinical Trials Information System.

CTIS is the EMA's public clinical-trials register that fully replaced the
legacy EU Clinical Trials Register in January 2025. It exposes a public
JSON API at https://euclinicaltrials.eu/ctis-public-api/ which is what we
target here. There is no published OpenAPI spec, so this client is built
defensively against the real shapes observed at runtime.

Two endpoints are used:
- POST /search   — paginated list with rich summary fields per trial
- GET  /retrieve/{ctNumber} — full record, including trial objective,
                              eligibility criteria, and full product info

We hit /retrieve once per trial. At the current vitiligo scale (~20 EU
trials) this is trivial. If the corpus ever grows, swap in batched
retrieval or skip the detail call when not needed.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
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

CTIS_API_BASE = "https://euclinicaltrials.eu/ctis-public-api"
SEARCH_URL = f"{CTIS_API_BASE}/search"
RETRIEVE_URL = f"{CTIS_API_BASE}/retrieve"

DEFAULT_VITILIGO_QUERY = "vitiligo"
DEFAULT_PAGE_SIZE = 50


# Phase normalization: CTIS reports verbose human-readable strings. Map
# them to a small canonical set that lines up with ClinicalTrials.gov.
# Patterns are checked in order; the first match wins.
_PHASE_PATTERNS: list[tuple[str, str]] = [
    (r"phase\s*1\s*and\s*phase\s*2|phase\s*i\s*and\s*phase\s*ii", "PHASE1/PHASE2"),
    (r"phase\s*2\s*and\s*phase\s*3|phase\s*ii\s*and\s*phase\s*iii", "PHASE2/PHASE3"),
    (r"phase\s*3\s*and\s*phase\s*4|phase\s*iii\s*and\s*phase\s*iv", "PHASE3/PHASE4"),
    (r"phase\s*4|phase\s*iv", "PHASE4"),
    (r"phase\s*3|phase\s*iii", "PHASE3"),
    (r"phase\s*2|phase\s*ii", "PHASE2"),
    (r"early\s*phase\s*1|phase\s*0", "EARLY_PHASE1"),
    (r"phase\s*1|phase\s*i", "PHASE1"),
    (r"bioequivalence", "BIOEQUIVALENCE"),
]


def _normalize_phase(raw: str | None) -> list[str]:
    if not raw:
        return []
    text = raw.lower()
    for pattern, label in _PHASE_PATTERNS:
        if re.search(pattern, text):
            return label.split("/") if "/" in label else [label]
    return []


def _parse_eu_date(value: str | None) -> str | None:
    """Convert CTIS DD/MM/YYYY strings into ISO YYYY-MM-DD."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value  # surface as-is rather than dropping unfamiliar shapes


def _parse_trial_countries(raw: list[str] | None) -> list[str]:
    """CTIS encodes countries as ['Netherlands:5', 'Germany:5'] — strip the suffix."""
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        country = (item.split(":", 1)[0] or "").strip()
        if country and country not in seen:
            seen.add(country)
            out.append(country)
    return sorted(out)


@dataclass(frozen=True)
class SearchHandle:
    total: int
    query: str


class EUCTRClient:
    """Thin client over the CTIS public JSON API."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        request_delay_s: float = 0.3,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "User-Agent": "vitiligo-initiative/0.1 (+https://github.com/recepsirin/vitiligo-initiative)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        self._delay = request_delay_s
        self._last_request_ts = 0.0

    def __enter__(self) -> EUCTRClient:
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
    def _post(self, url: str, payload: dict[str, Any]) -> httpx.Response:
        self._throttle()
        response = self._client.post(url, json=payload)
        response.raise_for_status()
        return response

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _get(self, url: str) -> httpx.Response:
        self._throttle()
        response = self._client.get(url)
        response.raise_for_status()
        return response

    def search_count(self, query: str = DEFAULT_VITILIGO_QUERY) -> int:
        response = self._post(
            SEARCH_URL,
            {
                "pagination": {"page": 1, "size": 1},
                "searchCriteria": {"medicalCondition": query},
            },
        )
        data = response.json()
        return int((data.get("pagination") or {}).get("totalRecords") or 0)

    def search(self, query: str = DEFAULT_VITILIGO_QUERY) -> SearchHandle:
        total = self.search_count(query)
        logger.info("CTIS search matched %d trials for '%s'", total, query)
        return SearchHandle(total=total, query=query)

    def _iter_search_records(
        self,
        query: str,
        page_size: int,
    ) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            response = self._post(
                SEARCH_URL,
                {
                    "pagination": {"page": page, "size": page_size},
                    "sort": {"property": "decisionDate", "direction": "DESC"},
                    "searchCriteria": {"medicalCondition": query},
                },
            )
            payload = response.json()
            records = payload.get("data") or []
            if not records:
                break
            logger.info("CTIS page %d: fetched %d records", page, len(records))
            yield from records

            pagination = payload.get("pagination") or {}
            if not pagination.get("nextPage"):
                break
            page += 1

    def retrieve(self, ct_number: str) -> dict[str, Any]:
        response = self._get(f"{RETRIEVE_URL}/{ct_number}")
        payload: dict[str, Any] = response.json()
        return payload

    def iter_trials(
        self,
        query: str = DEFAULT_VITILIGO_QUERY,
        page_size: int = DEFAULT_PAGE_SIZE,
        limit: int | None = None,
        with_details: bool = True,
    ) -> Iterator[Trial]:
        emitted = 0
        for record in self._iter_search_records(query, page_size):
            ct_number = (record.get("ctNumber") or "").strip()
            if not ct_number:
                continue

            detail: dict[str, Any] | None = None
            if with_details:
                try:
                    detail = self.retrieve(ct_number)
                except httpx.HTTPError as exc:
                    logger.warning("CTIS detail fetch failed for %s: %s", ct_number, exc)
                    detail = None

            try:
                trial = parse_euctr(record, detail)
            except Exception as exc:
                logger.warning("Failed to parse CTIS record %s: %s", ct_number, exc)
                continue

            if trial is None:
                continue

            yield trial
            emitted += 1
            if limit is not None and emitted >= limit:
                return


# ---------------------------------------------------------------------- parsing


def parse_euctr(
    search_record: dict[str, Any],
    detail: dict[str, Any] | None = None,
) -> Trial | None:
    """Build a `Trial` from a CTIS search record (and optional detail payload).

    Both arguments are tolerated as None / partial. The function never
    raises on missing nested keys.
    """
    ct_number = (search_record.get("ctNumber") or "").strip()
    if not ct_number:
        return None

    status_text = _coerce_status(search_record, detail)
    countries = _parse_trial_countries(search_record.get("trialCountries"))
    phases = _normalize_phase(search_record.get("trialPhase"))
    interventions = _interventions_from_detail(detail)
    sponsors = _sponsors_from_record(search_record, detail)
    eligibility = _eligibility_from_detail(detail)
    summary = _summary_from_detail(detail) or _coerce_str(search_record.get("ctTitle"))
    primary_outcome_text = _coerce_str(search_record.get("primaryEndPoint"))
    secondary_outcome_text = _coerce_str(search_record.get("endPoint"))

    enrollment_count = _coerce_int(search_record.get("totalNumberEnrolled"))
    start_date = _parse_eu_date(search_record.get("startDateEU"))
    decision_date = _parse_eu_date(search_record.get("decisionDateOverall"))
    last_update = _parse_eu_date(search_record.get("lastUpdated"))

    return Trial(
        source=TrialSourceKind.EUCTR,
        source_id=ct_number,
        brief_title=_coerce_str(search_record.get("shortTitle"))
        or _coerce_str(search_record.get("ctTitle")),
        official_title=_coerce_str(search_record.get("ctTitle")),
        summary=summary,
        status=status_text,
        last_known_status=None,
        study_type="INTERVENTIONAL",  # CTIS is interventional-only by mandate
        phases=phases,
        conditions=_conditions_from_record(search_record),
        keywords=list(search_record.get("therapeuticAreas") or []),
        interventions=interventions,
        arm_groups=[],
        sponsors=sponsors,
        locations=[{"country": c} for c in countries],
        countries=countries,
        primary_outcomes=(
            [{"measure": primary_outcome_text, "description": None, "time_frame": None}]
            if primary_outcome_text
            else []
        ),
        secondary_outcomes=(
            [{"measure": secondary_outcome_text, "description": None, "time_frame": None}]
            if secondary_outcome_text
            else []
        ),
        enrollment_count=enrollment_count,
        enrollment_type="AUTHORISED" if enrollment_count is not None else None,
        eligibility_criteria=eligibility,
        sex=_coerce_str(search_record.get("gender")),
        minimum_age=None,
        maximum_age=None,
        healthy_volunteers=None,
        start_date=start_date,
        primary_completion_date=None,
        completion_date=None,
        first_posted_date=decision_date,
        last_update_date=last_update,
        has_results=str(search_record.get("resultsFirstReceived") or "").lower() == "yes",
        raw_metadata={
            "ct_number": ct_number,
            "search": search_record,
            "detail_present": detail is not None,
        },
    )


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _coerce_status(
    search_record: dict[str, Any],
    detail: dict[str, Any] | None,
) -> str | None:
    """Prefer the human-readable status from the detail payload when available."""
    if detail:
        detail_status = detail.get("ctStatus")
        if isinstance(detail_status, str):
            return detail_status.strip().upper().replace(" ", "_")
    raw = search_record.get("ctStatus")
    if isinstance(raw, str):
        return raw.strip().upper().replace(" ", "_")
    if isinstance(raw, int):
        return f"CTIS_STATE_{raw}"
    return None


def _conditions_from_record(search_record: dict[str, Any]) -> list[str]:
    raw = search_record.get("conditions")
    if isinstance(raw, list):
        return [str(c).strip() for c in raw if c]
    if isinstance(raw, str):
        # CTIS sometimes returns comma-separated text.
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts
    return []


def _interventions_from_detail(detail: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not detail:
        return []
    products = (
        detail.get("authorizedApplication", {})
        .get("authorizedPartI", {})
        .get("products")
        or []
    )
    out: list[dict[str, Any]] = []
    for p in products:
        name = _coerce_str(p.get("productName")) or _coerce_str(
            p.get("otherMedicinalProduct")
        )
        substances = p.get("jsonActiveSubstanceNames") or []
        if isinstance(substances, str):
            substances = [substances]
        out.append(
            {
                "type": "DRUG",
                "name": name,
                "description": _coerce_str(p.get("pharmaceuticalFormDisplay")),
                "other_names": [str(s) for s in substances if s],
            }
        )
    return out


def _sponsors_from_record(
    search_record: dict[str, Any],
    detail: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    sponsor_name = _coerce_str(search_record.get("sponsor"))
    sponsor_type = _coerce_str(search_record.get("sponsorType"))
    if sponsor_name:
        out.append(
            {
                "role": "lead",
                "name": sponsor_name,
                "class": sponsor_type,
            }
        )

    if detail:
        all_sponsors = (
            detail.get("authorizedApplication", {})
            .get("authorizedPartI", {})
            .get("sponsors")
            or []
        )
        for s in all_sponsors:
            org = (s.get("organisation") or {})
            name = _coerce_str(org.get("organisationName")) or _coerce_str(
                org.get("organisation")
            )
            if not name or any(name == existing["name"] for existing in out):
                continue
            out.append(
                {
                    "role": "lead" if s.get("primary") else "collaborator",
                    "name": name,
                    "class": "Commercial" if s.get("isCommercial") else "Non-commercial",
                }
            )
    return out


def _summary_from_detail(detail: dict[str, Any] | None) -> str | None:
    if not detail:
        return None
    info = (
        detail.get("authorizedApplication", {})
        .get("authorizedPartI", {})
        .get("trialDetails", {})
        .get("trialInformation", {})
    )
    objective = (info.get("trialObjective") or {}).get("mainObjective")
    result: str | None = _coerce_str(objective)
    return result


def _eligibility_from_detail(detail: dict[str, Any] | None) -> str | None:
    if not detail:
        return None
    info = (
        detail.get("authorizedApplication", {})
        .get("authorizedPartI", {})
        .get("trialDetails", {})
        .get("trialInformation", {})
    )
    elig = info.get("eligibilityCriteria") or {}

    inclusions = _flatten_criteria(elig.get("principalInclusionCriteria"))
    exclusions = _flatten_criteria(elig.get("principalExclusionCriteria"))

    sections: list[str] = []
    if inclusions:
        sections.append("Inclusion Criteria:\n" + "\n".join(f"- {c}" for c in inclusions))
    if exclusions:
        sections.append("Exclusion Criteria:\n" + "\n".join(f"- {c}" for c in exclusions))
    return "\n\n".join(sections) or None


def _flatten_criteria(value: Any) -> list[str]:
    """CTIS criteria come as a list of dicts; we want the English text per item."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = _coerce_str(item.get("principalInclusionCriteria")) or _coerce_str(
                item.get("principalExclusionCriteria")
            )
            if text:
                out.append(text)
        elif isinstance(item, str):
            text = _coerce_str(item)
            if text:
                out.append(text)
    return out
