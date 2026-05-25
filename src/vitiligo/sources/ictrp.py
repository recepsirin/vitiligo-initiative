"""WHO ICTRP source — bulk XML file import.

WHO ICTRP has no free public REST API comparable to ClinicalTrials.gov or
CTIS. The supported workflow is to export search results from
https://trialsearch.who.int/ as XML (Export results to XML → Export all
trials to XML) and ingest locally:

    vitiligo ingest ictrp --file export.xml

Each XML record follows the ICTRP Trial Registration Data Set shape
observed in WHO exports and partner parsers (``Trial/TrialID``,
``Public_title``, ``Recruitment_status2``, repeated ``Health_condition`` /
``Intervention`` blocks, etc.).

Records are stored under ``source=ictrp`` keyed by ICTRP ``TrialID``.
Trials already ingested from ClinicalTrials.gov or EU CTR are skipped
via cross-registry ID matching so the corpus does not double-count.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lxml import etree
from lxml.etree import Element

from vitiligo.logging import get_logger
from vitiligo.storage.models import Trial, TrialSourceKind

logger = get_logger(__name__)

# Primary registers whose records we already ingest via dedicated pipelines.
_SKIP_PRIMARY_REGISTERS: frozenset[str] = frozenset(
    {
        "ClinicalTrials.gov",
        "EU Clinical Trials Register",
    }
)

_PRIMARY_REGISTER_ALIASES: dict[str, str] = {
    "German Clinical Trials Register": "DRKS",
    "Netherlands Trial Register": "NTR",
    "EU Clinical Trials Register": "EUCTR",
    "ClinicalTrials.gov": "NCT",
}

_NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
_EUCTR_RE = re.compile(r"\b20\d{2}-\d{6}-\d{2}(?:-\d{2})?\b")

_PHASE_PATTERNS: list[tuple[str, str]] = [
    (r"phase\s*1\s*[/&]\s*phase\s*2|phase\s*i\s*[/&]\s*phase\s*ii", "PHASE1/PHASE2"),
    (r"phase\s*2\s*[/&]\s*phase\s*3|phase\s*ii\s*[/&]\s*phase\s*iii", "PHASE2/PHASE3"),
    (r"phase\s*3\s*[/&]\s*phase\s*4|phase\s*iii\s*[/&]\s*phase\s*iv", "PHASE3/PHASE4"),
    (r"phase\s*4|phase\s*iv", "PHASE4"),
    (r"phase\s*3|phase\s*iii", "PHASE3"),
    (r"phase\s*2|phase\s*ii", "PHASE2"),
    (r"early\s*phase\s*1|phase\s*0", "EARLY_PHASE1"),
    (r"phase\s*1|phase\s*i", "PHASE1"),
]

_STATUS_MAP: dict[str, str] = {
    "recruiting": "RECRUITING",
    "not yet recruiting": "NOT_YET_RECRUITING",
    "active, not recruiting": "ACTIVE_NOT_RECRUITING",
    "enrolling by invitation": "ENROLLING_BY_INVITATION",
    "completed": "COMPLETED",
    "terminated": "TERMINATED",
    "suspended": "SUSPENDED",
    "withdrawn": "WITHDRAWN",
    "unknown status": "UNKNOWN",
    "no longer available": "NO_LONGER_AVAILABLE",
    "available": "AVAILABLE",
}


def iter_ictrp_trials(path: Path, limit: int | None = None) -> Iterator[Trial]:
    """Yield parsed trials from an ICTRP XML export file."""
    emitted = 0
    for record_root in iter_ictrp_record_roots(path):
        trial = parse_ictrp_record(record_root)
        if trial is None:
            continue
        yield trial
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def count_ictrp_records(path: Path) -> int:
    """Count parseable trial records in an ICTRP XML export."""
    return sum(1 for _ in iter_ictrp_record_roots(path))


def iter_ictrp_record_roots(path: Path) -> Iterator[Element]:
    """Yield the root element for each trial record in an export file."""
    data = path.read_bytes()
    seen_ids: set[str] = set()

    for doc_root in _iter_xml_documents(data):
        for record in _find_record_elements(doc_root):
            trial_id = _text(record, "Trial/TrialID")
            if not trial_id or trial_id in seen_ids:
                continue
            seen_ids.add(trial_id)
            yield record


def parse_ictrp_record(root: Element) -> Trial | None:
    """Parse one ICTRP XML record into a ``Trial``."""
    trial_id = _text(root, "Trial/TrialID")
    if not trial_id:
        return None

    primary_register = _text(root, "Trial/Primary_Register_text") or ""
    public_title = _text(root, "Trial/Public_title")
    scientific_title = _text(root, "Trial/Scientific_title")
    summary = _text(root, "Trial/Study_design") or _text(root, "Trial/Brief_summary")

    conditions = [
        text
        for text in (_text(el, "Condition_FreeText") for el in root.iter("Health_condition"))
        if text
    ]
    keywords = [
        text for text in (_text(el, "Keyword") for el in root.iter("Keyword")) if text
    ]

    interventions: list[dict[str, Any]] = []
    for el in root.iter("Intervention"):
        name = _text(el, "Intervention_FreeText") or _text(el, "Intervention_code")
        if not name:
            continue
        interventions.append(
            {
                "type": "DRUG",
                "name": name,
                "description": _text(el, "Other_details"),
                "other_names": [],
            }
        )

    sponsors: list[dict[str, Any]] = []
    primary_sponsor = _text(root, "Trial/Primary_sponsor")
    if primary_sponsor:
        sponsors.append({"role": "lead", "name": primary_sponsor, "class": None})
    for el in root.iter("Secondary_Sponsors"):
        name = _text(el, "Secondary_Sponsor")
        if name:
            sponsors.append({"role": "collaborator", "name": name, "class": None})

    countries = _parse_countries(root)
    secondary_ids = [
        sid for sid in (_text(el, "SecondaryID") for el in root.iter("Secondary_IDs")) if sid
    ]

    primary_outcomes: list[dict[str, Any]] = []
    for el in root.iter("Primary_outcome"):
        description = _text(el, "Outcome_Name")
        if description:
            primary_outcomes.append(
                {
                    "measure": description,
                    "description": _text(el, "Timepoints"),
                    "time_frame": _text(el, "Time_frame1"),
                }
            )

    secondary_outcomes: list[dict[str, Any]] = []
    for el in root.iter("Secondary_outcome"):
        description = _text(el, "Outcome_Name")
        if description:
            secondary_outcomes.append(
                {
                    "measure": description,
                    "description": _text(el, "Timepoints"),
                    "time_frame": _text(el, "Time_frame2"),
                }
            )

    criteria = root.find("Criteria")
    eligibility = _text(criteria, "Inclusion_criteria") if criteria is not None else None
    sex = _text(criteria, "Inclusion_sex") if criteria is not None else None
    minimum_age = _text(criteria, "Inclusion_agemin") if criteria is not None else None
    maximum_age = _text(criteria, "Inclusion_agemax") if criteria is not None else None

    results_el = root.find("Results")
    results_flag = (_text(results_el, "results_yes_no") if results_el is not None else "") or ""
    has_results = results_flag.strip().lower() in {"yes", "y", "true", "1"}

    enrollment_count = _parse_int(_text(root, "Trial/Target_size"))

    return Trial(
        source=TrialSourceKind.ICTRP,
        source_id=trial_id,
        brief_title=public_title or scientific_title,
        official_title=scientific_title or public_title,
        summary=summary,
        status=_normalize_status(_text(root, "Trial/Recruitment_status2")),
        study_type=_normalize_study_type(_text(root, "Trial/Study_type")),
        phases=_normalize_phase(_text(root, "Trial/Phase")),
        conditions=conditions,
        keywords=keywords,
        interventions=interventions,
        sponsors=sponsors,
        countries=countries,
        primary_outcomes=primary_outcomes,
        secondary_outcomes=secondary_outcomes,
        enrollment_count=enrollment_count,
        eligibility_criteria=eligibility,
        sex=sex,
        minimum_age=minimum_age,
        maximum_age=maximum_age,
        start_date=_text(root, "Trial/Date_enrollement"),
        first_posted_date=_text(root, "Trial/Date_registration2"),
        last_update_date=_text(root, "Trial/last_updated"),
        has_results=has_results,
        raw_metadata={
            "trial_id": trial_id,
            "primary_register": primary_register,
            "primary_register_alias": _PRIMARY_REGISTER_ALIASES.get(primary_register),
            "secondary_ids": secondary_ids,
            "cross_registry_keys": sorted(
                f"{src}:{sid}" for src, sid in extract_cross_registry_keys(trial_id, secondary_ids)
            ),
        },
    )


def should_skip_ictrp_record(
    trial: Trial,
    *,
    skip_duplicates: bool,
    existing_keys: set[tuple[str, str]],
) -> bool:
    """Return True when an ICTRP record should not be inserted."""
    meta = trial.raw_metadata or {}
    primary_register = str(meta.get("primary_register") or "")
    if primary_register in _SKIP_PRIMARY_REGISTERS:
        return True

    if not skip_duplicates:
        return False

    for source, source_id in extract_cross_registry_keys(
        trial.source_id,
        list(meta.get("secondary_ids") or []),
    ):
        if (source.value, source_id) in existing_keys:
            return True
    return False


def extract_cross_registry_keys(
    trial_id: str,
    secondary_ids: list[str] | None = None,
) -> set[tuple[TrialSourceKind, str]]:
    """Map ICTRP IDs to canonical (source, source_id) pairs for deduplication."""
    keys: set[tuple[TrialSourceKind, str]] = set()
    for raw in [trial_id, *(secondary_ids or [])]:
        for token in re.split(r"[;,|\s]+", raw or ""):
            token = token.strip()
            if not token:
                continue
            nct = _NCT_RE.search(token)
            if nct:
                keys.add((TrialSourceKind.CTGOV, nct.group(0).upper()))
            euctr = _EUCTR_RE.search(token)
            if euctr:
                keys.add((TrialSourceKind.EUCTR, euctr.group(0)[:19]))
            if token.upper().startswith("NCT") and len(token) >= 11:
                keys.add((TrialSourceKind.CTGOV, token[:11].upper()))
            if token.upper().startswith("EUCTR"):
                keys.add((TrialSourceKind.EUCTR, token[:19].upper()))
    return keys


def _iter_xml_documents(data: bytes) -> Iterator[Element]:
    """Parse one or more XML documents from an ICTRP export file."""
    try:
        yield etree.fromstring(data)
        return
    except etree.XMLSyntaxError:
        pass

    text = data.decode("utf-8-sig", errors="replace")
    chunks = re.split(r"(?=<\?xml)", text)
    if len(chunks) <= 1:
        try:
            yield etree.fromstring(text.encode("utf-8"))
        except etree.XMLSyntaxError as exc:
            raise ValueError("Could not parse ICTRP XML export") from exc
        return

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or "TrialID" not in chunk:
            continue
        try:
            yield etree.fromstring(chunk.encode("utf-8"))
        except etree.XMLSyntaxError:
            logger.warning("Skipping malformed ICTRP XML chunk")


def _find_record_elements(root: Element) -> list[Element]:
    """Return top-level ICTRP record elements (each wraps a ``Trial`` block)."""
    candidates = [el for el in root.iter() if el.find("Trial/TrialID") is not None]
    if not candidates:
        return []

    candidate_ids = {id(el) for el in candidates}
    top_level: list[Element] = []
    for el in candidates:
        parent = el.getparent()
        nested = False
        while parent is not None:
            if id(parent) in candidate_ids:
                nested = True
                break
            parent = parent.getparent()
        if not nested:
            top_level.append(el)
    return top_level


def _text(root: Element | None, path: str) -> str | None:
    if root is None:
        return None
    node = root.find(path)
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _parse_countries(root: Element) -> list[str]:
    countries: list[str] = []
    seen: set[str] = set()
    for el in root.iter("Country"):
        name = _text(el, "CountryName")
        if not name:
            continue
        cleaned = re.sub(r":\d+$", "", name.strip())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            countries.append(cleaned)
    return countries


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", value.replace(",", ""))
    return int(match.group(0)) if match else None


def _normalize_phase(raw: str | None) -> list[str]:
    if not raw:
        return []
    text = raw.strip().lower()
    if text in {"not applicable", "na", "n/a", "none", "-"}:
        return []
    for pattern, label in _PHASE_PATTERNS:
        if re.search(pattern, text):
            return label.split("/") if "/" in label else [label]
    return [raw.strip().upper().replace(" ", "_")]


def _normalize_status(raw: str | None) -> str | None:
    if not raw:
        return None
    mapped = _STATUS_MAP.get(raw.strip().lower())
    if mapped:
        return mapped
    return raw.strip().upper().replace(" ", "_").replace(",", "")


def _normalize_study_type(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip().lower()
    if "interventional" in text or "intervention" in text:
        return "INTERVENTIONAL"
    if "observational" in text:
        return "OBSERVATIONAL"
    return raw.strip().upper()
