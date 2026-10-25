"""WHO ICTRP, one record at a time.

``ictrp.py`` ingests a bulk XML export, which has to be downloaded from the
search portal by hand. That covers a sweep of the registry network, but it
cannot answer the question that actually comes up: a paper cites
``CTRI/2017/05/008692``, and nothing in the corpus says what that trial was.

The portal's record page answers it. ``Trial2.aspx?TrialID=<id>`` returns the
WHO Trial Registration Data Set for one trial — titles, condition,
interventions, sponsor, countries, target size, design, eligibility and
outcomes — for every registry in the network, including CTRI, ChiCTR, IRCT,
PACTR and DRKS. Several of those publish no API and render their own sites
with JavaScript, so for them this is the only machine-readable route.

Three things shape this module.

**It reuses the XML parser instead of adding a second one.** The record page
is an ASP.NET grid whose ``<span>`` ids are the data-set field names, so a
page converts into the record shape ``parse_ictrp_record`` already reads. A
web-resolved trial and an export-ingested trial are then the same row, built
by the same code and skipped by the same cross-registry dedup.

**The page carries personal data.** Every record has a contacts grid with
investigator names, street addresses, telephone numbers and email addresses,
and an ethics grid naming the approving committee. No field of a ``Trial``
comes from either, so ``strip_personal`` removes both grids and redacts
emails and telephone numbers from the prose that remains — before the
payload is cached. The hash recorded in the raw-payload manifest is
therefore of what we kept, not of what was served. That is deliberate: the
bytes as served are not ours to retain.

**The portal is flaky rather than strict.** An unknown id returns HTTP 200
with a page that simply holds no record, and a valid id intermittently drops
the connection — three of five lookups failed on first attempt and all three
succeeded on retry. So absence is read from the content, never from the
status code, and requests are retried with a backoff.

Text is stored as served. Some registries' records reach the portal with
apostrophes and bullets already mangled into ``¿``; that corruption is
upstream, and guessing the intended characters would be inventing data.
"""

from __future__ import annotations

import html
import re
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

import httpx
from lxml import etree

from vitiligo.logging import get_logger
from vitiligo.sources.ictrp import parse_ictrp_record
from vitiligo.sources.raw_cache import DEFAULT_RAW_CACHE, load_payload, save_payload
from vitiligo.storage.models import Trial

logger = get_logger(__name__)

RECORD_URL = "https://trialsearch.who.int/Trial2.aspx"
CACHE_SOURCE = "ictrp-web"
REQUEST_DELAY_SECONDS = 1.0
MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 3.0

# The contacts grid (names, addresses, telephone, email) and the ethics grid
# (the approving committee's contact). Dropped whole, before caching.
PERSONAL_GRIDS: tuple[str, ...] = ("DataList4", "DataList5")

REDACTED_EMAIL = "[email removed]"
REDACTED_PHONE = "[phone removed]"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# A telephone number only where a label introduces one. An unlabelled run of
# digits is as likely to be a date or a trial id: matching those turned
# `29-05-2017` into `[phone removed]` and `ChiCTR2000036712` into `ChiCTR[phone
# removed]` before this was narrowed.
_PHONE = re.compile(
    r"\b(?:tel|telephone|phone|mobile|cell|fax)\b[\s.:#]*\+?\d[\d\s().-]{6,}\d",
    re.I,
)

_SPAN = re.compile(r'<span id="([^"]+)"[^>]*>(.*?)</span>', re.S)
_GRID_SPAN = re.compile(r"^(DataList\w+)_ctl(\d+)_(.+)$")

# Scalar fields. `<span id="DataList3_ctl01_Public_titleLabel">` is the
# data-set field Public_title. Four names differ from the export's: the
# register arrives in a span called "Description", and three carry the
# export's own suffixes.
_TRIAL_FIELDS: dict[str, str] = {
    "TrialID": "TrialID",
    "Description": "Primary_Register_text",
    "Public_title": "Public_title",
    "Scientific_title": "Scientific_title",
    "Acronym": "Acronym",
    "Primary_sponsor": "Primary_sponsor",
    "Recruitment_status": "Recruitment_status2",
    "Date_registration": "Date_registration2",
    "Date_enrollement": "Date_enrollement",
    "Last_updated": "last_updated",
    "Target_size": "Target_size",
    "Study_type": "Study_type",
    "Study_design": "Study_design",
    "Phase": "Phase",
}

# Repeated grids. Each row becomes one element of the named kind. ICTRP
# numbers the grids, and the numbering is stable across registries.
_REPEATED_GRIDS: dict[str, tuple[str, dict[str, str]]] = {
    "DataList2": ("Country", {"Country": "CountryName"}),
    "DataList8": ("Health_condition", {"Condition_FreeText": "Condition_FreeText"}),
    "DataList10": ("Intervention", {"Intervention_FreeText": "Intervention_FreeText"}),
    "DataList12": (
        "Primary_outcome",
        {"Outcome_Name": "Outcome_Name", "Time_Frame1": "Time_frame1"},
    ),
    "DataList14": (
        "Secondary_outcome",
        {"Outcome_Name": "Outcome_Name", "Time_Frame2": "Time_frame2"},
    ),
    "DataList16": ("Secondary_IDs", {"SecondaryID": "SecondaryID"}),
}

# Eligibility. Three of these reach the page as unnamed grid labels; the
# sample records agree on which is which.
_CRITERIA_FIELDS: dict[str, str] = {
    "Inclusion_criteria": "Inclusion_criteria",
    "Exclusion_criteria": "Exclusion_criteria",
    "Label8": "Inclusion_agemin",
    "Label11": "Inclusion_agemax",
    "Label12": "Inclusion_sex",
}

_RESULTS_FIELDS: dict[str, str] = {"lblResultsYesNo": "results_yes_no"}

# The web view prints a field's own label into its value; the export does not.
_LABEL_PREFIX = re.compile(
    r"^(?:Inclusion criteria|Exclusion criteria|Health Condition\s*\d*|Intervention\s*\d*)\s*:\s*",
    re.I,
)

# The web view folds an outcome's timepoint into its name, and leaves the
# timepoint field empty. The export keeps them apart, so split them back.
_TIMEPOINT = re.compile(r"\s*Timepoints?\s*:\s*", re.I)

# The one outbound link on the page is the record in its home registry.
_SOURCE_RECORD_LINK = re.compile(r'href="(https?://(?!\S*(?:who\.int|w3\.org))[^"]+)"', re.I)


def strip_personal(page: str) -> str:
    """Drop the contacts and ethics grids, and redact contact details.

    Applied before the payload is cached, so nothing we store carries an
    investigator's name, address, telephone number or email.
    """
    for grid in PERSONAL_GRIDS:
        page = re.sub(
            rf'<span id="{grid}_ctl\d+_[^"]*"[^>]*>.*?</span>',
            "",
            page,
            flags=re.S,
        )
    page = _EMAIL.sub(REDACTED_EMAIL, page)
    return _PHONE.sub(REDACTED_PHONE, page)


def _cell_text(body: str) -> str:
    """One grid cell as text, with its line breaks kept."""
    text = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return _LABEL_PREFIX.sub("", text.strip()).strip()


def _field_name(suffix: str) -> str:
    """The data-set field a span id names.

    ``Condition_FreeTextLabel`` and ``Country_Label`` spell the same
    convention two ways; both name the field before the ``Label``.
    """
    return re.sub(r"Label$", "", suffix).rstrip("_")


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_summary_row(value: str, others: list[str]) -> bool:
    """True when a row just restates every other row in its grid.

    Some grids end with a row holding all the preceding ones joined together —
    PACTR's conditions arrive as "Skin and Connective Tissue Diseases",
    "vitiligo", and then both at once. Keeping that third row would invent a
    condition no registry recorded.
    """
    if len(others) < 2:
        return False
    return _collapse(value) == _collapse(" ".join(others))


def _split_timepoint(values: dict[str, str]) -> dict[str, str]:
    """Move an outcome's timepoint out of its name and into its own field.

    "Extent of repigmentationTimepoint: 16 weeks" is one span on the page and
    two fields in the export. The week an outcome was measured at is the first
    thing anyone asks of it, so it should not be left buried in prose.
    """
    name = values.get("Outcome_Name")
    if name is None:
        return values
    parts = _TIMEPOINT.split(name, maxsplit=1)
    if len(parts) != 2:
        return values
    measure, timepoints = parts[0].strip(), parts[1].strip()
    if not measure or not timepoints:
        return values
    return {**values, "Outcome_Name": measure, "Timepoints": timepoints}


def record_to_xml(page: str) -> etree._Element | None:
    """Convert a record page into the ICTRP export's record shape.

    Returns ``None`` when the page holds no record, which is how the portal
    answers an unknown id — with HTTP 200 and a page missing the id span.
    """
    cells: dict[tuple[str, int, str], str] = {}
    for span_id, body in _SPAN.findall(page):
        match = _GRID_SPAN.match(span_id)
        if match is None:
            continue
        grid, row = match.group(1), int(match.group(2))
        text = _cell_text(body)
        if text:
            cells[(grid, row, _field_name(match.group(3)))] = text

    if not any(grid == "DataList3" and field == "TrialID" for grid, _, field in cells):
        return None

    root = etree.Element("Trial_Record")
    trial = etree.SubElement(root, "Trial")
    for (grid, _, field), value in cells.items():
        if grid == "DataList3" and field in _TRIAL_FIELDS:
            etree.SubElement(trial, _TRIAL_FIELDS[field]).text = value

    for grid, (kind, fields) in _REPEATED_GRIDS.items():
        rows = {
            row: {
                fields[field]: value
                for (g, r, field), value in cells.items()
                if g == grid and r == row and field in fields
            }
            for row in sorted({r for g, r, _ in cells if g == grid})
        }
        primary = next(iter(fields.values()))
        for row, values in rows.items():
            if not values:
                continue
            others = [v[primary] for r, v in rows.items() if r != row and v.get(primary)]
            if primary in values and _is_summary_row(values[primary], others):
                continue
            element = etree.SubElement(root, kind)
            for name, value in _split_timepoint(values).items():
                etree.SubElement(element, name).text = value

    criteria = {
        _CRITERIA_FIELDS[field]: value
        for (grid, _, field), value in cells.items()
        if grid == "DataList6" and field in _CRITERIA_FIELDS
    }
    if criteria:
        element = etree.SubElement(root, "Criteria")
        for name, value in criteria.items():
            etree.SubElement(element, name).text = value

    results = {
        _RESULTS_FIELDS[field]: value
        for (grid, _, field), value in cells.items()
        if grid == "DataListResults" and field in _RESULTS_FIELDS
    }
    if results:
        element = etree.SubElement(root, "Results")
        for name, value in results.items():
            etree.SubElement(element, name).text = value

    return root


def parse_record_page(page: str) -> Trial | None:
    """Parse one record page into a ``Trial``, or ``None`` if it holds none."""
    root = record_to_xml(page)
    if root is None:
        return None
    trial = parse_ictrp_record(root)
    if trial is None:
        return None

    metadata = dict(trial.raw_metadata or {})
    metadata["record_url"] = f"{RECORD_URL}?TrialID={trial.source_id}"
    link = _SOURCE_RECORD_LINK.search(page)
    if link is not None:
        metadata["source_record_url"] = link.group(1)
    trial.raw_metadata = metadata
    return trial


def is_about_vitiligo(trial: Trial, term: str = "vitiligo") -> bool:
    """True when the condition or title is the disease, not a passing mention.

    Papers cite registry ids for context as well as for evidence.
    DRKS00012745 is a sixteen-country study of stigmatization across
    dermatological disease, cited in a vitiligo paper but registered under the
    condition "skin disease"; it is not a vitiligo trial and does not pass.
    """
    needle = term.lower()
    haystack = " ".join(
        [
            *(trial.conditions or []),
            *(trial.keywords or []),
            trial.brief_title or "",
            trial.official_title or "",
        ]
    ).lower()
    return needle in haystack


def fetch_record(
    trial_id: str,
    *,
    client: httpx.Client,
    cache: Path | None = DEFAULT_RAW_CACHE,
    refresh: bool = False,
    delay: float = REQUEST_DELAY_SECONDS,
) -> str | None:
    """Return one record page with personal data already removed.

    Served pages are cached, so re-running an ingest or checking a figure
    months later does not depend on the portal being up.
    """
    name = f"{re.sub(r'[^A-Za-z0-9]+', '-', trial_id).strip('-')}.html"
    if cache is not None and not refresh:
        cached = load_payload(CACHE_SOURCE, name, cache)
        if cached is not None:
            return cached.decode("utf-8", errors="replace")

    page: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if delay:
            time.sleep(delay)
        try:
            response = client.get(RECORD_URL, params={"TrialID": trial_id})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            if attempt == MAX_ATTEMPTS:
                logger.warning("ICTRP %s failed after %d attempts: %s", trial_id, attempt, exc)
                return None
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue
        page = strip_personal(response.text)
        break

    if page is None:
        return None
    if record_to_xml(page) is None:
        logger.info("ICTRP has no record for %s", trial_id)
        return None

    if cache is not None:
        save_payload(CACHE_SOURCE, name, page.encode("utf-8"), url=RECORD_URL, cache=cache)
    return page


def resolve_trials(
    trial_ids: Iterable[str],
    *,
    client: httpx.Client | None = None,
    cache: Path | None = DEFAULT_RAW_CACHE,
    refresh: bool = False,
    delay: float = REQUEST_DELAY_SECONDS,
) -> Iterator[Trial]:
    """Resolve registry ids into trials, skipping any the portal does not hold."""
    owned = client is None
    client = client or httpx.Client(
        timeout=90.0,
        follow_redirects=True,
        headers={"User-Agent": "vitiligo-initiative/0.1 (research)"},
    )
    try:
        seen: set[str] = set()
        for raw_id in trial_ids:
            trial_id = raw_id.strip()
            if not trial_id or trial_id in seen:
                continue
            seen.add(trial_id)
            page = fetch_record(trial_id, client=client, cache=cache, refresh=refresh, delay=delay)
            if page is None:
                continue
            trial = parse_record_page(page)
            if trial is None:
                continue
            yield trial
    finally:
        if owned:
            client.close()
