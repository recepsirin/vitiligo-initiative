"""ISRCTN: the registry ClinicalTrials.gov does not cover.

Trials run outside the United States often register with ISRCTN instead,
and nothing in the corpus reached it. The eight vitiligo trials it holds
include a within-patient randomised comparison of NB-UVB against excimer
laser after mini-grafting, which no other registry we read carries.

Two things shape this module.

**A search for "vitiligo" is not a list of vitiligo trials.** ISRCTN matches
the word anywhere, so a hair-loss serum and a skin-infection study come back
because vitiligo appears in their exclusion criteria. ``is_about_vitiligo``
keeps the ones whose condition or title is the disease; it drops roughly
nine in ten of the matches.

**The records carry contact details** — investigator names, telephone
numbers, email addresses and site street addresses. An evidence corpus has
no use for any of it, so ``_strip_personal`` drops those elements and
redacts the emails sponsors write into the summary prose, before anything is
stored. Recruitment countries are kept, because where a trial ran matters.

API: https://www.isrctn.com/api/query/format/default?q=... (XML, no key)
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from lxml import etree

from vitiligo.logging import get_logger
from vitiligo.storage.models import Trial, TrialSourceKind

logger = get_logger(__name__)

API_URL = "https://www.isrctn.com/api/query/format/default"
NS = {"i": "http://www.67bricks.com/isrctn"}
DEFAULT_VITILIGO_QUERY = "vitiligo"
DEFAULT_LIMIT = 100

# Elements naming or locating a person, or a street address we have no use
# for. Removed before storage; the recruitment countries are kept.
PERSONAL_ELEMENTS = ("contact", "contactDetails", "parties", "trialCentres")

# Sponsors publish contact addresses inside the summary prose too.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
REDACTED_EMAIL = "[email removed]"


@dataclass(frozen=True)
class SearchResult:
    """What one search returned."""

    total: int
    trials: list[etree._Element]


def _texts(element: etree._Element, path: str) -> list[str]:
    return [t.strip() for t in element.xpath(path, namespaces=NS) if str(t).strip()]


def _text(element: etree._Element, path: str) -> str | None:
    found = _texts(element, path)
    return found[0] if found else None


def redact_emails(text: str | None) -> str | None:
    """Email addresses out of free text, which sponsors write into summaries."""
    return _EMAIL.sub(REDACTED_EMAIL, text) if text else text


def _strip_personal(trial: etree._Element) -> etree._Element:
    """A copy with names, contact details and street addresses removed.

    Registry records are public, but an evidence corpus has no use for a
    named investigator's email or a site's street address, so neither is
    stored. Emails also appear inside summary prose, which is redacted
    rather than dropped, since the surrounding sentences carry the method.
    """
    clone = copy.deepcopy(trial)
    for name in PERSONAL_ELEMENTS:
        for element in clone.xpath(f".//i:{name}", namespaces=NS):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
    for element in clone.iter():
        if element.text:
            element.text = redact_emails(element.text)
    return clone


def is_about_vitiligo(trial: etree._Element, term: str = "vitiligo") -> bool:
    """True when the condition or title is the disease, not a passing mention."""
    needle = term.lower()
    condition = " ".join(_texts(trial, ".//i:conditions//text()")).lower()
    titles = " ".join(
        _texts(trial, ".//i:trialDescription/i:title//text()")
        + _texts(trial, ".//i:trialDescription/i:scientificTitle//text()")
    ).lower()
    return needle in condition or needle in titles


def _date(value: str | None) -> str | None:
    """ISRCTN writes ISO timestamps; the store keeps plain dates."""
    return value[:10] if value else None


def _status(trial: etree._Element) -> str | None:
    """ISRCTN states a status only as an override; otherwise dates imply it."""
    override = _text(trial, ".//i:recruitmentStatusOverride/text()")
    if override:
        return override
    start = _date(_text(trial, ".//i:recruitmentStart/text()"))
    end = _date(_text(trial, ".//i:recruitmentEnd/text()"))
    if start and end:
        return "COMPLETED_RECRUITMENT" if end < "2026-10-24" else "RECRUITING"
    return None


def _interventions(trial: etree._Element) -> list[dict[str, Any]]:
    out = []
    for element in trial.xpath(".//i:interventions/i:intervention", namespaces=NS):
        out.append(
            {
                "name": _text(element, "./i:drugNames/text()")
                or _text(element, "./i:interventionType/text()"),
                "type": _text(element, "./i:interventionType/text()"),
                "description": _text(element, "./i:description/text()"),
            }
        )
    return out


def _eligibility(trial: etree._Element) -> str | None:
    inclusion = _text(trial, ".//i:inclusion/text()")
    exclusion = _text(trial, ".//i:exclusion/text()")
    parts = [
        f"Inclusion:\n{inclusion}" if inclusion else "",
        f"Exclusion:\n{exclusion}" if exclusion else "",
    ]
    joined = "\n\n".join(p for p in parts if p)
    return joined or None


def _enrolment(trial: etree._Element) -> tuple[int | None, str | None]:
    final = _text(trial, ".//i:totalFinalEnrolment/text()")
    target = _text(trial, ".//i:targetEnrolment/text()")
    for value, kind in ((final, "ACTUAL"), (target, "ESTIMATED")):
        if value and value.isdigit():
            return int(value), kind
    return None, None


def to_trial(trial: etree._Element) -> Trial | None:
    """One ISRCTN record as a stored trial, without any personal details."""
    number = _text(trial, ".//i:isrctn/text()")
    if not number:
        return None
    safe = _strip_personal(trial)
    count, count_type = _enrolment(trial)
    phase = _text(trial, ".//i:intervention/i:phase/text()")
    return Trial(
        source=TrialSourceKind.ISRCTN,
        source_id=f"ISRCTN{number}",
        brief_title=_text(trial, ".//i:trialDescription/i:title/text()"),
        official_title=_text(trial, ".//i:trialDescription/i:scientificTitle/text()"),
        summary=redact_emails(_text(trial, ".//i:plainEnglishSummary/text()")),
        status=_status(trial),
        study_type=(_text(trial, ".//i:primaryStudyDesign/text()") or "").upper() or None,
        phases=[phase] if phase else [],
        conditions=_texts(trial, ".//i:conditions/i:condition/i:description/text()"),
        interventions=_interventions(trial),
        countries=_texts(trial, ".//i:recruitmentCountries/i:country/text()"),
        enrollment_count=count,
        enrollment_type=count_type,
        eligibility_criteria=_eligibility(trial),
        sex=_text(trial, ".//i:gender/text()"),
        minimum_age=_text(trial, ".//i:lowerAgeLimit/text()"),
        maximum_age=_text(trial, ".//i:upperAgeLimit/text()"),
        healthy_volunteers=(_text(trial, ".//i:healthyVolunteersAllowed/text()") == "true"),
        start_date=_date(_text(trial, ".//i:recruitmentStart/text()")),
        completion_date=_date(_text(trial, ".//i:overallEndDate/text()")),
        has_results=bool(_texts(trial, ".//i:publicationDetails/text()")),
        raw_metadata={"xml": etree.tostring(safe, encoding="unicode")},
    )


def parse_search(xml: bytes) -> SearchResult:
    """Trials in one API response, with the total it reports."""
    root = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    total = root.get("totalCount")
    return SearchResult(
        total=int(total) if total and total.isdigit() else 0,
        trials=root.findall(".//i:fullTrial", NS),
    )


class ISRCTNClient:
    """Thin client over the ISRCTN query API."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(120.0, connect=20.0),
            headers={"User-Agent": "vitiligo-initiative/1.0 (research)"},
        )
        self._owns_client = client is None

    def __enter__(self) -> ISRCTNClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(self, query: str = DEFAULT_VITILIGO_QUERY, limit: int = DEFAULT_LIMIT) -> bytes:
        response = self._client.get(API_URL, params={"q": query, "limit": limit})
        response.raise_for_status()
        return bytes(response.content)

    def iter_trials(
        self, query: str = DEFAULT_VITILIGO_QUERY, limit: int = DEFAULT_LIMIT
    ) -> Iterator[Trial]:
        """Vitiligo trials from one search, skipping passing mentions."""
        result = parse_search(self.search(query, limit))
        logger.info("ISRCTN: %d record(s) match %r", result.total, query)
        kept = 0
        for element in result.trials:
            if not is_about_vitiligo(element, query):
                continue
            trial = to_trial(element)
            if trial is not None:
                kept += 1
                yield trial
        logger.info("ISRCTN: %d of %d are about the condition", kept, len(result.trials))
