"""WHO ICTRP, the whole search result at once.

``ictrp_web`` reads one record per request, which answers "what was the trial
this paper cites". It cannot answer "what trials exist", because the portal's
search is an ASP.NET form rather than a URL.

The form can be posted to. ``search`` fills it the way the page does and
returns what its own **Export to CSV** button produces: every matching trial
in one file, 58 columns wide. For vitiligo that is 1,020 trials against the
347 ClinicalTrials.gov carries, and it reaches CTRI, ChiCTR, IRCT, ITMCTR,
JPRN, PACTR, TCTR, ANZCTR, ReBEC, CRIS, RPCEC, SLCTR and NL-OMON — most of
which publish no API at all.

Two things shape this module.

**The columns are a whitelist, not a filter.** Eleven of the 58 columns are
an investigator's name, address, telephone number, email and affiliation, or
an ethics committee's contact — populated in 833, 813 and 791 rows
respectively. Rather than strip them after the fact, ``_FIELDS`` names the
columns that become a trial and the rest are never read, so no contact
detail can reach the store through an oversight.

**Repeated fields arrive concatenated.** The record page gives conditions and
interventions as separate grid rows; the CSV runs them into one cell behind
their own numbering -- "Health Condition 1: ...Health Condition 2: ...". The
numbering is what splits them back apart, and a cell with no numbering is one
value, not a parse failure.

Rows convert into the record shape ``parse_ictrp_record`` already reads, so a
trial from the export, from a record page and from a bulk XML file are the
same row built by the same code.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator
from pathlib import Path

import httpx
from lxml import etree

from vitiligo.logging import get_logger
from vitiligo.sources.ictrp import parse_ictrp_record, strip_label_prefix
from vitiligo.sources.isrctn import redact_emails
from vitiligo.storage.models import Trial

logger = get_logger(__name__)

SEARCH_URL = "https://trialsearch.who.int/"
USER_AGENT = (
    "vitiligo-initiative/0.1 (non-profit vitiligo research; "
    "+https://github.com/recepsirin/vitiligo-initiative)"
)
DEFAULT_VITILIGO_QUERY = "vitiligo"

# The columns that become a trial. Every column absent from this map is never
# read: that is how the contact and ethics-contact columns stay out of the
# store. Values are the data-set field names the XML parser expects.
_FIELDS: dict[str, str] = {
    "TrialID": "TrialID",
    "Source Register": "Primary_Register_text",
    "Public title": "Public_title",
    "Scientific title": "Scientific_title",
    "Acronym": "Acronym",
    "Primary sponsor": "Primary_sponsor",
    "Date registration": "Date_registration2",
    "Date enrollement": "Date_enrollement",
    "Last Refreshed on": "last_updated",
    "Target size": "Target_size",
    "Recruitment Status": "Recruitment_status2",
    "Study type": "Study_type",
    "Study design": "Study_design",
    "Phase": "Phase",
}

_CRITERIA_FIELDS: dict[str, str] = {
    "Inclusion Criteria": "Inclusion_criteria",
    "Exclusion Criteria": "Exclusion_criteria",
    "Inclusion agemin": "Inclusion_agemin",
    "Inclusion agemax": "Inclusion_agemax",
    "Inclusion gender": "Inclusion_sex",
}

# Columns holding several values in one cell, and the kind each becomes.
_REPEATED: dict[str, tuple[str, str]] = {
    "Countries": ("Country", "CountryName"),
    "Condition": ("Health_condition", "Condition_FreeText"),
    "Intervention": ("Intervention", "Intervention_FreeText"),
    "Primary outcome": ("Primary_outcome", "Outcome_Name"),
    "Secondary outcome": ("Secondary_outcome", "Outcome_Name"),
    "Secondary ID": ("Secondary_IDs", "SecondaryID"),
}

# "Health Condition 2:" and "Intervention2:" mark where one value ends and the
# next begins. Splitting *before* the marker keeps it with its own value, so
# the label prefix can then be stripped as the record page's is.
# The bare "Condition" alternative also matches inside "Health Condition",
# which split that label in half and left "Health" as a condition of its own.
_NUMBERED = re.compile(
    r"(?=(?<!Health )(?:Health Condition|Condition|Intervention)\s*\d+\s*:)", re.I
)
_TIMEPOINT = re.compile(r"\s*Timepoints?\s*:\s*", re.I)
_BR = re.compile(r"<\s*br\s*/?\s*>", re.I)


def _clean(value: str | None) -> str:
    """One cell as text, with the portal's literal ``<br>`` markup as breaks."""
    text = _BR.sub("\n", value or "")
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def _split(column: str, value: str) -> list[str]:
    """The separate values in one cell."""
    text = _clean(value)
    if not text:
        return []
    if column in {"Countries", "Secondary ID"}:
        parts = re.split(r"[;\n]", text)
    else:
        parts = _NUMBERED.split(text)
        if len(parts) == 1:
            parts = text.split("\n") if column == "Condition" else [text]
    out: list[str] = []
    for part in parts:
        cleaned = strip_label_prefix(part)
        if cleaned and cleaned.lower() not in {"nil", "none", "na", "n/a", "-"}:
            out.append(cleaned)
    return out


# Columns kept when the export is written to the raw cache. The payload as
# served carries 833 emails, 813 telephone numbers and 683 postal addresses;
# caching it unchanged would put every one of them on disk.
_CACHEABLE: frozenset[str] = frozenset(
    {*_FIELDS, *_CRITERIA_FIELDS, *_REPEATED, "web address", "results yes no",
     "results date posted", "results url link", "results date completed",
     "results summary", "results outcome measures", "other records",
     "Prospective registration", "Bridging flag truefalse", "Bridged type",
     "Export date"}
)  # fmt: skip

# A telephone number only where a label introduces one: an unlabelled run of
# digits in these columns is a target size, a date or a trial id.
_PHONE = re.compile(
    r"\b(?:tel|telephone|phone|mobile|cell|fax)\b[\s.:#]*(?:no\.?)?[\s.:#]*\+?\d[\d\s().-]{6,}\d",
    re.I,
)
REDACTED_PHONE = "[phone removed]"


def redacted_csv(payload: bytes) -> bytes:
    """The export with every contact column dropped, for the raw cache.

    What is saved is therefore not byte-identical to what WHO served. That is
    the point: the columns removed are an investigator's name, address,
    telephone number and email, and an evidence corpus has no use for any of
    them.
    """
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    kept = [c for c in (reader.fieldnames or []) if c in _CACHEABLE]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=kept, lineterminator="\n")
    writer.writeheader()
    for row in reader:
        writer.writerow({c: _redact(row.get(c, "")) for c in kept})
    return out.getvalue().encode("utf-8")


def _redact(value: str) -> str:
    """Contact details a sponsor wrote into a free-text column.

    Dropping the contact columns is not enough on its own: one CTRI record
    puts a postal address, a telephone number and an email inside the name of
    its funding source. ISRCTN had the same habit, which is why
    ``redact_emails`` already exists.
    """
    return _PHONE.sub(REDACTED_PHONE, redact_emails(value) or "")


def row_to_xml(row: dict[str, str]) -> etree._Element | None:
    """Convert one exported row into the ICTRP record shape."""
    trial_id = (row.get("TrialID") or "").strip()
    if not trial_id:
        return None

    root = etree.Element("Trial_Record")
    trial = etree.SubElement(root, "Trial")
    for column, field in _FIELDS.items():
        value = _clean(row.get(column))
        if value:
            etree.SubElement(trial, field).text = value

    for column, (kind, child) in _REPEATED.items():
        for value in _split(column, row.get(column, "")):
            element = etree.SubElement(root, kind)
            if child == "Outcome_Name":
                parts = _TIMEPOINT.split(value, maxsplit=1)
                if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                    etree.SubElement(element, "Outcome_Name").text = parts[0].strip()
                    etree.SubElement(element, "Timepoints").text = parts[1].strip()
                    continue
            etree.SubElement(element, child).text = value

    # "Inclusion criteria: " is the column's own label printed into its value.
    criteria = {
        field: strip_label_prefix(_clean(row.get(column)))
        for column, field in _CRITERIA_FIELDS.items()
        if strip_label_prefix(_clean(row.get(column)))
    }
    if criteria:
        element = etree.SubElement(root, "Criteria")
        for field, value in criteria.items():
            etree.SubElement(element, field).text = value

    flag = _clean(row.get("results yes no"))
    if flag:
        element = etree.SubElement(root, "Results")
        etree.SubElement(element, "results_yes_no").text = flag

    return root


def parse_row(row: dict[str, str]) -> Trial | None:
    """One exported row as a ``Trial``, with its home registry's link kept."""
    root = row_to_xml(row)
    if root is None:
        return None
    trial = parse_ictrp_record(root)
    if trial is None:
        return None

    metadata = dict(trial.raw_metadata or {})
    address = _clean(row.get("web address"))
    if address:
        metadata["source_record_url"] = address
    results_url = _clean(row.get("results url link"))
    if results_url:
        metadata["results_url"] = results_url
    trial.raw_metadata = metadata
    return trial


def iter_csv_trials(path: Path, limit: int | None = None) -> Iterator[Trial]:
    """Yield trials from an ICTRP CSV export."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    emitted = 0
    for row in csv.DictReader(io.StringIO(text)):
        trial = parse_row(row)
        if trial is None:
            continue
        yield trial
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def count_csv_rows(path: Path) -> int:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return sum(1 for row in csv.DictReader(io.StringIO(text)) if (row.get("TrialID") or "").strip())


def _form_fields(html: str) -> dict[str, str]:
    """Every hidden and text input the portal's form posts back.

    ``__VIEWSTATEENCRYPTED`` is among them. Leaving it out is not an error the
    portal reports -- it answers 200 with its own error page, which reads
    exactly like a search that found nothing.
    """
    fields: dict[str, str] = {}
    for match in re.finditer(r"<input[^>]*>", html):
        tag = match.group(0)
        name = re.search(r'name="([^"]+)"', tag)
        if name is None:
            continue
        kind = re.search(r'type="([^"]+)"', tag)
        if kind is not None and kind.group(1) in {"checkbox", "submit"}:
            continue
        value = re.search(r'value="([^"]*)"', tag)
        fields[name.group(1)] = value.group(1) if value else ""
    return fields


def search(
    term: str = DEFAULT_VITILIGO_QUERY,
    *,
    client: httpx.Client | None = None,
    with_results_only: bool = False,
) -> bytes:
    """Run the portal's own search and return its CSV export.

    One POST to fill the form, one to press Export to CSV -- the same two the
    page makes, with the same fields.
    """
    owned = client is None
    client = client or httpx.Client(
        timeout=300.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    )
    try:
        home = client.get(SEARCH_URL)
        home.raise_for_status()

        data = _form_fields(home.text)
        data["TextBox1"] = term
        data["Button1"] = "Search"
        if with_results_only:
            data["chkWithResultsOnly"] = "on"
        results = client.post(SEARCH_URL, data=data, headers={"Referer": SEARCH_URL})
        results.raise_for_status()

        found = re.search(r"([\d,]+)\s+records?\s+for\s+([\d,]+)\s+trials?", results.text)
        if found is None:
            raise ValueError(f"ICTRP search for {term!r} returned no result header")
        logger.info("ICTRP search for %r: %s", term, found.group(0))

        export = _form_fields(results.text)
        export["Button7"] = "Export to CSV"
        payload = client.post(SEARCH_URL, data=export, headers={"Referer": SEARCH_URL})
        payload.raise_for_status()
        if b"TrialID" not in payload.content[:2000]:
            raise ValueError("ICTRP export did not return a CSV")
        return payload.content
    finally:
        if owned:
            client.close()
