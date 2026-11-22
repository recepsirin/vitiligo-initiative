"""WHO ICTRP source — bulk XML file import.

WHO ICTRP has no free public REST API comparable to ClinicalTrials.gov or
CTIS, and its search cannot be driven by URL. This module covers the bulk
route; ``sources.ictrp_web`` resolves one record at a time by id, which is
how a trial a paper cites gets read. The supported bulk workflow is to
export search results from
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
#
# "EU Clinical Trials Register" was here and should not have been. The euctr
# pipeline reads CTIS, the system that replaced that register in 2023; the
# register's own back catalogue is separate data. Skipping it lost every
# European vitiligo trial that predates CTIS -- eighteen in the vitiligo
# export, of which seven are held nowhere else. The eleven that are
# duplicates are caught by ID instead, which is what dedup is for.
_SKIP_PRIMARY_REGISTERS: frozenset[str] = frozenset({"ClinicalTrials.gov"})

_PRIMARY_REGISTER_ALIASES: dict[str, str] = {
    "German Clinical Trials Register": "DRKS",
    "Netherlands Trial Register": "NTR",
    "EU Clinical Trials Register": "EUCTR",
    "ClinicalTrials.gov": "NCT",
}

_NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
_EUCTR_RE = re.compile(r"\b20\d{2}-\d{6}-\d{2}(?:-\d{2})?\b")
# A CTIS record's ICTRP id is the CTIS number with the register glued to the
# front, and "S2022" is no word boundary, so _EUCTR_RE never saw it. Eleven
# trials were held twice for want of this: NCT06113328, 2023-503502-37-00 and
# CTIS2023-503502-37-00 are all MK-6194-007.
_CTIS_RE = re.compile(r"\bCTIS(20\d{2}-\d{6}-\d{2}(?:-\d{2})?)\b", re.IGNORECASE)
# ISRCTN had no pattern at all, so the seven trials held through its own API
# were held a second time through ICTRP -- four of them with enrollment 0 on
# the API copy and the real figure on the ICTRP one.
_ISRCTN_RE = re.compile(r"\bISRCTN\d{6,}\b", re.IGNORECASE)

# CTIS and EudraCT records reach ICTRP listing every phase with a yes or no:
# "Human pharmacology (Phase I): no Therapeutic exploratory (Phase II): yes ...".
# Searching that text for a phase found "Phase IV" in all 27 of them, so 25
# trials in phase 1, 2 or 3 were held as phase 4 (cached export, measured 2026-11-21).
_PHASE_FLAG = re.compile(r"\(phase\s+(i{1,3}|iv)\)\s*:\s*(yes|no)?")
_PHASE_NUMERAL = {
    "0": "0",  # ChiCTR's and IRCT's phase 0, kept as the registry writes it
    "1": "PHASE1",
    "2": "PHASE2",
    "3": "PHASE3",
    "4": "PHASE4",
    "i": "PHASE1",
    "ii": "PHASE2",
    "iii": "PHASE3",
    "iv": "PHASE4",
}

_STATUS_MAP: dict[str, str] = {
    "recruiting": "RECRUITING",
    "not yet recruiting": "NOT_YET_RECRUITING",
    "active, not recruiting": "ACTIVE_NOT_RECRUITING",
    "enrolling by invitation": "ENROLLING_BY_INVITATION",
    "completed": "COMPLETED",
    "complete": "COMPLETED",
    "terminated": "TERMINATED",
    "suspended": "SUSPENDED",
    "withdrawn": "WITHDRAWN",
    "unknown status": "UNKNOWN",
    "no longer available": "NO_LONGER_AVAILABLE",
    "available": "AVAILABLE",
}


# A field's own label, printed into its value. ICTRP prepends one even when
# the registry already wrote it, so "Inclusion criteria: Inclusion Criteria: 1."
# is a real value and stripping once is not enough.
_LABEL_PREFIX = re.compile(
    r"^(?:(?:Inclusion criteria|Exclusion criteria|Health Condition\s*\d*"
    r"|Condition\s*\d*|Intervention\s*\d*)\s*:\s*)+",
    re.I,
)


# ICTRP's free-text intervention runs an arm's name and its description into one
# value: "Ointment of Apamargaksharyoga: Dose: QS for local application, ...".
# Kept whole, 670 such values became drug entities named with a description
# (issue #21). A label before the first colon names the intervention, unless it
# names an arm or a field ("Intervention group:", "Product name:"), when the name
# follows it; a short first line names it too. A value that is prose -- 116 with
# no label, about 120 behind an arm label -- names nothing, and keeps its text.
_NAME_MAX = 80
# "Nome" and "nill" are registrants' typos (ChiCTR2600118018, ChiCTR2000035934).
_PLACEHOLDER = re.compile(r"^(?:nil|nill|none|nome|na|n/a|not applicable|-)$", re.I)
# Labels that name an arm, a field or the design, not what an arm receives. IRCT
# lists its intervention category ("Treatment - Drugs") beside the interventions,
# and a half-side study names its "Control lesion".
_ARM_LABEL = re.compile(
    r"^(?:(?:intervention|control|experimental|treatment|study|comparator|trial|observation"
    r"|vehicle control)\s*(?:group|arm|agent|drug|product|lesion)?\s*\w{0,3}"
    r"|(?:first|second|third)\s+intervention(?:\s+group)?"
    r"|(?:group|gruop|arm|part)[\s-]*\w{1,3}|case|(?:\d+\.\s*)?study setting"
    r"|product (?:name|code)|trade name|medical device|treatment\s*-\s*\w+"
    r"|randomi[sz]ed controlled trial|single arm(?: clinical study)?)$",
    re.I,
)
# What names nothing a group is given: a sentence, an instruction, a negation or
# a placeholder ("We will participate ...", "Apply 2 times a day.", "Without CAP
# treatment", "Not provided at time of registration"), a population ("200 HEALTHY
# INDIVIDUALS ..."), a sample, a measure, a route or the condition itself.
_NOT_A_NAME = re.compile(
    r"^(?:all|the|a|an|in|each|both|see|this|there|patients?|participants?|subjects?"
    r"|receiving|vitiligo patients|no|control\s+group|take|apply|without|we|consisting"
    r"|nil(?:control)?|not\s+(?:applicab\w*|provided)|\d+\s+sessions?"
    r"|(?:\d+\s+)?(?:healthy|children|pediatric|women|men|adults)"
    r"|(?:\d+\W*\s*)?(?:taking\s+\w+\s+skin|peripheral\s+blood|skin\s+tissues?|adverse\s+effects?)"
    r"|orally$|topically$|(?:oral|topical)\s+and\s+(?:oral|topical|subcutaneous)$)\b",
    re.I,
)
_SENTENCE = re.compile(r"\b(?:will|who)\b", re.I)
_MEASURE = re.compile(r"\b(?:index|scale|assessment|questionnaire)$", re.I)
_CONDITION = re.compile(
    r"^(?:L\d\d\W*)?(?:(?:non-?)?(?:progressive|segmental|stable|active)\s+)*vitiligo$", re.I
)
# "Group I Melagenina Plus®", "Active control group, PUVA sol": the arm, then its name.
_ARM_PREFIX = re.compile(
    r"^(?:(?:group|arm)\s*(?!of\b)(?:\(\w{1,3}\)|\w{1,3})|(?:active\s+)?(?:control|study)\s+group)"
    r"\s*(?:[:.,-]\s*|\s+)(?=\S)",
    re.I,
)
# Context around a name: "Efficacy of 2% Tofacitnib gel in Acral Vitiligo",
# "SPARC121 as Active", "Excimer light with".
_AIM_PREFIX = re.compile(r"^(?:(?:efficacy|safety|effect|use)\s+of|active agent\s*-)\s+", re.I)
_CONTEXT_SUFFIX = re.compile(
    r"\s+(?:(?:in|for)\s+(?:the\s+(?:treatment|management)\s+of\s+)?(?:acral\s+)?"
    r"(?:vitiligo(?:\s+vulgaris)?|s?h?witra)"
    r"|(?:as|is)\s+(?:the\s+)?(?:active|comparator|intervention)"
    r"|and|with|along|of|namely|containing|either)$",
    re.I,
)
_LEADING_JUNK = re.compile(r"^(?:[^\w(]|Â)+")  # bullets and mojibake: "Â¢Women in ..."
_PRODUCT_CODE = re.compile(
    r",\s*product code\b.*$", re.I
)  # CTIS: "Ritlecitinib, Product Code: ..."
_LABELLED = re.compile(rf"^([^:]{{1,{_NAME_MAX}}}):\s*(.*)$")
_TAG = re.compile(r"</?\w+\s*/?>")  # a few records arrive wrapped in HTML paragraphs
# "Oral tofacitinib (Group A)" names the tablet; "Group B (Oral PUVAsol)" too.
_BRACKETED = re.compile(r"^(.+?)\s*\(([^()]+)\)$")
# "TA Group", "placebo treated patients": the arm is named after what it receives.
_GROUP_SUFFIX = re.compile(
    r"\s+(?:(?:treated|treatment)\s+(?:group|arm|patients)|group|arm)$", re.I
)
# ChiCTR and ITMCTR write each group with what it is given, "Group:intervention;",
# and "None" for a group given nothing, so the label names a group, never the
# intervention: "Vitiligo group:None;", "CKBA 0.5% group:Apply topically ...".
# Read the CTRI way, such labels became drug entities, one of them "Vitiligo".
# The registry joins the pairs with a bare ";"; a registrant's own "; " stays
# inside one ("TID); 2. minors: weight>60kg").
_GROUPED_REGISTRIES = ("ChiCTR", "ITMCTR")
_PAIR_BOUNDARY = re.compile(r";(?=\S)")


def _trim(text: str) -> str:
    """Strip the punctuation around a name, keeping a bracket that closes.

    Stripping every bracket left 47 names open: "Thuravadhi Chooranam (Internal".
    """
    # A leading ")" never closes: IRCT writes "Intervention group 1 : ) Micro-needling".
    text = _LEADING_JUNK.sub("", text.strip()).rstrip(".").strip(" ,")
    while text.endswith(")") and text.count(")") > text.count("("):
        text = text[:-1].rstrip(" ,.")
    while text.startswith("(") and text.count("(") > text.count(")"):
        text = text[1:].lstrip(" ,")
    while text.endswith("("):
        text = text[:-1].rstrip(" ,.")
    while text.count("(") > text.count(")"):  # cut at a colon: "... device (JMDN code"
        text = text[: text.rindex("(")].rstrip(" ,.")
    inner = text[1:-1]
    if text.startswith("(") and text.endswith(")") and inner.count("(") == inner.count(")"):
        text = inner.strip()
    return text


def _name(candidate: str) -> str | None:
    """The intervention a candidate names, or None if it names none.

    "Fangbai Granule;Control group" names the granule; "none;Group 2" nothing.
    """
    for part in candidate.split(";"):
        labelled = _LABELLED.match(part.strip())
        if labelled and _ARM_LABEL.match(labelled.group(1).strip()):
            part = labelled.group(2)
        part = _trim(_PRODUCT_CODE.sub("", part))
        bracketed = _BRACKETED.match(part)
        if bracketed:
            outer, inner = bracketed.group(1).strip(), bracketed.group(2).strip()
            if _ARM_LABEL.match(inner):
                part = outer
            elif _ARM_LABEL.match(outer):
                part = _trim(inner)
        if not part or _ARM_LABEL.match(part):
            continue
        if len(part) > _NAME_MAX or _names_nothing(part):
            return None
        part = _without_context(part)
        if part and not _ARM_LABEL.match(part) and not _CONDITION.match(part):
            return part
    return None


def _names_nothing(part: str) -> bool:
    return bool(
        _PLACEHOLDER.match(part)
        or _NOT_A_NAME.match(part)
        or _SENTENCE.search(part)
        or _MEASURE.search(part)
    )


def _without_context(part: str) -> str:
    """The name inside an arm prefix, an aim, a role or a trailing connective."""
    part = _AIM_PREFIX.sub("", _ARM_PREFIX.sub("", part))
    while True:
        shorter = _trim(_GROUP_SUFFIX.sub("", _CONTEXT_SUFFIX.sub("", part)))
        if shorter == part:
            return part
        part = shorter


def _group_pairs(text: str) -> list[tuple[str, str]] | None:
    """(name, description) for each "Group:intervention;" pair, or None if none.

    A group given "None" yields nothing; a description that is prose, no name.
    """
    given_to: list[str] = []
    for chunk in _PAIR_BOUNDARY.split(text.strip().rstrip(";")):
        group, colon, given = chunk.partition(":")
        if colon and len(group) <= _NAME_MAX and "\n" not in group:
            given_to.append(given)
        elif given_to:  # a bare ";" inside one group's intervention
            given_to[-1] += ";" + chunk
    if not given_to:
        return None
    pairs: dict[str, tuple[str, str]] = {}
    for raw in given_to:
        given = raw.strip(" ;\n")
        # "Control Group: Monotherapy Group(...):None" gives the group nothing too.
        if not given or _PLACEHOLDER.match(given.rsplit(":", 1)[-1].strip(" ;.")):
            continue
        name = _name(given) if "\n" not in given else None
        pairs.setdefault(name or given, (name or "", given))
    return list(pairs.values())


def split_intervention(text: str, *, grouped: bool = False) -> list[tuple[str, str]]:
    """An ICTRP free-text intervention as (name, description) pairs.

    An empty name means the value is prose that names no intervention; an empty
    list means it is a placeholder ("Nil: Nil"). CTRI values end with the next
    arm's heading, a lone "Control" line, which is dropped. ``grouped`` reads the
    value as ChiCTR and ITMCTR write it, one "Group:intervention;" per group.
    """
    lines = [line.strip() for line in _TAG.sub("", text or "").split("\n") if line.strip()]
    if len(lines) > 1 and lines[-1].lower() == "control":
        lines = lines[:-1]
    if not lines:
        return []
    body = "\n".join(lines)
    if grouped:
        pairs = _group_pairs(body)
        if pairs is not None:
            return pairs
    head = lines[0]
    for _ in range(3):  # "Control group: Experimental group: X" carries several labels
        match = _LABELLED.match(head)
        if match is None:
            break
        label, rest = match.group(1).strip(), match.group(2).strip()
        if _PLACEHOLDER.match(label) and (not rest or _PLACEHOLDER.match(rest)):
            return []
        if _ARM_LABEL.match(label) or _PLACEHOLDER.match(label):
            head = rest
            continue
        name = _name(label)
        return [(name, body)] if name else [("", body)]
    if len(lines) == 1 and head.count(";") >= 1 and not _LABELLED.match(head):
        names = [n for n in (_name(item) for item in head.split(";")) if n]
        if names and all(len(item.strip()) <= _NAME_MAX for item in head.split(";")):
            return [(n, "") for n in dict.fromkeys(names)]
    if _PLACEHOLDER.match(head):
        return []
    name = _name(head) if len(head) <= _NAME_MAX else None
    if name:
        return [(name, body if body != name else "")]
    return [("", body)]


def intervention_entries(
    text: str, details: str | None = None, *, trial_id: str = ""
) -> list[dict[str, Any]]:
    """The trial interventions one ICTRP value gives, each keeping the registry's text.

    ``trial_id`` tells which registry wrote the value (see ``_GROUPED_REGISTRIES``).
    A value that names nothing still gives one unnamed entry: a trial's treatment
    groups read the text ("... with phototherapy group:None;").
    """
    grouped = trial_id.startswith(_GROUPED_REGISTRIES)
    named = split_intervention(text, grouped=grouped) or [("", "")]
    return [
        {
            "type": "DRUG",
            "name": name,
            "description": "\n".join(part for part in (description, details) if part) or None,
            "free_text": text,
            "other_names": [],
        }
        for name, description in named
    ]


def strip_label_prefix(text: str) -> str:
    """Drop the field label ICTRP prints into a value, however many times."""
    return _LABEL_PREFIX.sub("", text.strip()).strip()


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
    keywords = [text for text in (_text(el, "Keyword") for el in root.iter("Keyword")) if text]

    interventions: list[dict[str, Any]] = []
    for el in root.iter("Intervention"):
        text = _text(el, "Intervention_FreeText") or _text(el, "Intervention_code")
        if not text:
            continue
        interventions += intervention_entries(text, _text(el, "Other_details"), trial_id=trial_id)

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


def normalize_protocol_id(value: str) -> str:
    """A sponsor's protocol number, comparable across registries.

    The same trial is "INCB 18424-306" on ClinicalTrials.gov and
    "INCB18424-306" in the EU register, so punctuation and case cannot be
    part of the comparison.
    """
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def should_skip_ictrp_record(
    trial: Trial,
    *,
    skip_duplicates: bool,
    existing_keys: set[tuple[str, str]],
    existing_protocol_ids: set[str] | None = None,
) -> bool:
    """Return True when an ICTRP record should not be inserted.

    A record is skipped when its register is one we ingest directly, when one
    of its ids is a trial we already hold, or when it shares a sponsor
    protocol number with one. The last matters because a European record
    usually names the sponsor's protocol rather than the NCT: TRuE-V1 is
    "INCB18424-306" there and NCT04052425 here, and nothing else links them.
    """
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

    for secondary in meta.get("secondary_ids") or []:
        for token in re.split(r"[;\n]", str(secondary)):
            token = normalize_protocol_id(token.strip())
            if len(token) >= 6 and token in (existing_protocol_ids or ()):
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
            ctis = _CTIS_RE.search(token)
            if ctis:
                keys.add((TrialSourceKind.EUCTR, ctis.group(1)[:19]))
            isrctn = _ISRCTN_RE.search(token)
            if isrctn:
                keys.add((TrialSourceKind.ISRCTN, isrctn.group(0).upper()))
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
    """The phases one ICTRP phase field names, in ClinicalTrials.gov's spelling.

    Registries write a list of phases many ways, and every numeral counts:
    "Phase 2/ Phase 3", "2-3", "Phase I/II", "Phase II,III", PACTR's "Phase-3",
    IRCT's "0 (exploratory trials)". Reading only the first numeral after
    "Phase" had held "Phase I/II", "Phase I,II" and "Phase II,III" as one phase,
    and "Phase-3" (4 trials), "Phase-4" (3) and "0 (exploratory trials)" (1) as
    none. A field that names no phase -- "Retrospective study", "Post-market" --
    is kept as written.
    """
    if not raw:
        return []
    text = " ".join(raw.split()).lower()
    if text in {"not applicable", "na", "n/a", "none", "-"}:
        return []
    flags = _PHASE_FLAG.findall(text)
    if flags:
        return [_PHASE_NUMERAL[numeral] for numeral, answer in flags if answer == "yes"]
    if re.fullmatch(r"early\s*phase\s*1", text):
        return ["EARLY_PHASE1"]
    # "I (Phase I study)" and "0 (exploratory trials)": the gloss restates the phase.
    bare = re.sub(r"\s*\([^)]*\)", "", text)
    parts = [part for part in re.split(r"phase|[\s/,&-]+", bare) if part]
    if parts and all(part in _PHASE_NUMERAL for part in parts):
        found = {_PHASE_NUMERAL[part] for part in parts}
        return sorted(found, key=list(_PHASE_NUMERAL.values()).index)
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
