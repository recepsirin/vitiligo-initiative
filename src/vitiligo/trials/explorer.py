"""One row per vitiligo trial, for the public trial explorer.

The explorer on the Hugging Face Space lists every vitiligo trial this corpus
holds, registered or only published, and lets a reader narrow them by what
they test. This module turns ``Trial`` records into those rows;
``scripts/export_space_trials.py`` reads the store and writes ``trials.json``.

**Which trials.** A row is a trial in the vitiligo corpus
(``in_vitiligo_corpus``) whose record names the disease
(``is_vitiligo_trial``). The second test removes the 20 records that searches
brought in from past the disease: gingival depigmentation, keloids, a breast
cancer radiotherapy trial, an atopic dermatitis trial that lists vitiligo
among its exclusions. All 20 are right to go.

**One row per trial.** Nineteen trials are held twice. Twelve EU CTIS trials
are read from CTIS and again through WHO ICTRP, which writes the number with
a ``CTIS`` prefix; seven ISRCTN trials are read from ISRCTN and through ICTRP.
The registry's own record is kept, and a field it leaves empty is filled from
the ICTRP copy.

**Which registry.** ICTRP is a search portal, not a registry. Its records come
from CTRI, ChiCTR, IRCT and others, and the identifier says which. A record is
credited to the registry that holds it, and its link goes to WHO's copy.

**What a trial tests.** ``treatment_groups`` reads the intervention names and
the titles -- never the eligibility criteria or a summary's background, which
name treatments a trial does not give. A study registered as observational is
marked so and keeps the groups its record names, because a real-world study
of ruxolitinib cream is about a JAK inhibitor. Of the 55 observational
studies that take a group, 39 are labelled rightly; the other 16 are surveys
and laboratory studies that name a tradition or a nutrient without giving it
("Vitamin D levels in patients with autoimmune disorders"). Withholding groups
from every observational study would have traded those 39 for the 16.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

from vitiligo.reports.jak import match_agents, trial_url
from vitiligo.storage import Trial
from vitiligo.trials.relevance import fold, in_vitiligo_corpus, is_registered, is_vitiligo_trial

PUBLISHED = "Published, not registered"
OBSERVATIONAL = "Observational study"


def in_explorer(trial: Trial) -> bool:
    """True when the trial is a row of the explorer."""
    return in_vitiligo_corpus(trial) and is_vitiligo_trial(trial)


# ------------------------------------------------------------------ registry

_SOURCE_REGISTRIES = {"ctgov": "ClinicalTrials.gov", "euctr": "EU CTIS", "isrctn": "ISRCTN"}

# The registry an ICTRP record comes from, read off its identifier. Every
# entry names at least one record in the corpus; the order matters only where
# one prefix begins another, and none does.
_ICTRP_REGISTRIES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(prefix, re.IGNORECASE))
    for name, prefix in (
        ("CTRI (India)", r"^CTRI/"),
        ("IRCT (Iran)", r"^IRCT"),
        ("ChiCTR (China)", r"^ChiCTR"),
        ("ITMCTR (China, traditional medicine)", r"^ITMCTR"),
        ("UMIN (Japan)", r"^JPRN-UMIN"),
        ("jRCT (Japan)", r"^JPRN-jRCT"),
        ("EU CTIS", r"^CTIS"),
        ("OMON (Netherlands)", r"^NL-OMON"),
        ("TCTR (Thailand)", r"^TCTR"),
        ("PACTR (Africa)", r"^PACTR"),
        ("DRKS (Germany)", r"^DRKS"),
        ("ISRCTN", r"^ISRCTN"),
        ("EU CTR (EudraCT)", r"^EUCTR"),
        ("ANZCTR (Australia, NZ)", r"^ACTRN"),
        ("ReBEC (Brazil)", r"^RBR-"),
        ("CRIS (Korea)", r"^KCT"),
        ("SLCTR (Sri Lanka)", r"^SLCTR"),
        ("RPCEC (Cuba)", r"^RPCEC"),
    )
)


def registry_of(trial: Trial) -> str:
    """The registry that holds the trial, or ``PUBLISHED`` when none does."""
    if not is_registered(trial):
        return PUBLISHED
    source = trial.source.value
    if source in _SOURCE_REGISTRIES:
        return _SOURCE_REGISTRIES[source]
    for name, pattern in _ICTRP_REGISTRIES:
        if pattern.search(trial.source_id):
            return name
    return "WHO ICTRP"


def _same_trial_key(source_id: str) -> str:
    """The identifier with ICTRP's ``CTIS`` prefix removed, so both copies agree."""
    return re.sub(r"^CTIS", "", source_id.strip().upper())


def record_url(trial: Trial) -> str | None:
    """Where a reader can see the record: the registry entry or the paper."""
    source = trial.source.value
    if source == "isrctn":
        return f"https://www.isrctn.com/{trial.source_id}"
    if source == "publication":
        meta = trial.raw_metadata or {}
        if meta.get("pmid"):
            return f"https://pubmed.ncbi.nlm.nih.gov/{meta['pmid']}/"
        if meta.get("doi"):
            return f"https://doi.org/{meta['doi']}"
        return None
    return trial_url(source, trial.source_id)


# --------------------------------------------------------- phase and status

_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
_NOT_APPLICABLE = re.compile(r"n/?a|not[\s_]applicable", re.IGNORECASE)


def _phase_numbers(value: str) -> list[int]:
    """The phase numbers one registry value names.

    Registries write a phase five ways: ``PHASE2`` and ``EARLY_PHASE1``
    (ClinicalTrials.gov), ``Phase I/II`` (ISRCTN, one string for two
    phases), and ``0`` (ChiCTR's own scale). ChiCTR's design categories --
    retrospective study, pilot clinical trial -- arrive in the same field and
    name no phase.
    """
    numbers = []
    for part in re.split(r"[/,]", value):
        token = re.sub(r"^(?:early[\s_]*)?phase[\s_]*", "", part.strip().lower())
        if token.isdigit() and int(token) <= 4:
            numbers.append(int(token))
        elif token in _ROMAN:
            numbers.append(_ROMAN[token])
    return numbers


def phase_label(phases: Sequence[str]) -> tuple[str, list[int]]:
    """``("Phase 2/3", [2, 3])``, ``("Not applicable", [])`` or ``("Not specified", [])``."""
    numbers = sorted({n for value in phases for n in _phase_numbers(value)})
    if numbers:
        if numbers == [1] and any(v.strip().upper().startswith("EARLY") for v in phases):
            return "Early phase 1", numbers
        return "Phase " + "/".join(str(n) for n in numbers), numbers
    if any(_NOT_APPLICABLE.fullmatch(v.strip()) for v in phases):
        return "Not applicable", []
    return "Not specified", []


_STATUS = {
    "COMPLETED": "Completed",
    "UNKNOWN": "Unknown",
    "RECRUITING": "Recruiting",
    "NOT_YET_RECRUITING": "Not yet recruiting",
    "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "TERMINATED": "Terminated",
    "WITHDRAWN": "Withdrawn",
    "SUSPENDED": "Suspended",
    "AVAILABLE": "Available",
    # ICTRP says only whether a trial recruits, so this covers trials that
    # finished and trials that never started alike.
    "NOT_RECRUITING": "Not recruiting",
    "AUTHORISED": "Authorised",
    "NOT_AUTHORISED": "Not authorised",
    "ENDED": "Ended",
    "COMPLETED_RECRUITMENT": "Recruitment completed",
}


def status_label(trial: Trial) -> str:
    """The recruitment status in words. A paper with no registration has none."""
    if not is_registered(trial):
        return "Published"
    code = (trial.status or "").strip()
    return _STATUS.get(code.upper()) or code.replace("_", " ").capitalize() or "Not stated"


# ICTRP writes dates day first. Read the other way, 345 of its 692 start dates
# would have a month above 12, and none does read this way.
_DAY_FIRST = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_ISO = re.compile(r"\d{4}(?:-\d{2}(?:-\d{2})?)?")


def iso_date(value: str | None) -> str | None:
    """A registry date as ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD``; None when unreadable."""
    text = (value or "").strip()
    day_first = _DAY_FIRST.fullmatch(text)
    if day_first:
        day, month, year = day_first.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return text if _ISO.fullmatch(text) else None


# ------------------------------------------------------------ treatment groups

# Registered study types that test no treatment. A study of one of these
# types is marked ``OBSERVATIONAL`` beside its treatment groups.
NON_TREATMENT_TYPES = frozenset({"OBSERVATIONAL", "BASIC SCIENCE", "DIAGNOSTIC TEST", "SCREENING"})

# What a trial gives, by group. Patterns run over folded text (lower case,
# diacritics removed). The number after each is how many of the corpus's
# 2,258 explorer trials that pattern alone puts in its group, measured
# 2026-11-20: remove the pattern and those trials lose the label. Every
# pattern here moves at least one trial, and its sole matches were read and
# are right; tests/unit/test_trial_explorer.py re-measures that on the corpus.
#
# Some words were tried and left out. "Punch" is mostly punch biopsy for
# research, "antibod" mostly antibody levels, a bare "UV" or "ultraviolet"
# mostly UV photography, and "-cept" matched "proof of concept". "Surgery"
# matched ISRCTN's intervention type "Procedure/Surgery" on a laser trial, so
# only "surgical treatment" and its like stay. Fourteen names of Ayurvedic
# formulations went once "Shwitra" was in: a trial that calls the disease by
# its Ayurvedic name is an Ayurvedic trial, and every one of them did.
TREATMENT_GROUPS: dict[str, tuple[str, ...]] = {
    # Plus every name and code in ``reports.jak.JAK_AGENTS`` (173 alone).
    "JAK inhibitor": (
        r"\bjak(?:[\s-]*\d)?\s+inhibit",  # 5
        r"janus\s+kinase(?:[\s-]*\d)?\s+inhibit",  # 4
        # Ivarmacitinib's code run into its formulation, "SHR0302Base", which
        # the agent list's word-bounded alias does not reach.
        r"\bshr[\s-]?0302",  # 1
    ),
    "Phototherapy & laser": (
        r"nb[\s-]?uvb",  # 7
        r"narrow[\s-]?band",  # 5
        r"\buv[\s-]?[ab]\b",  # 16
        r"ultraviolet[\s-]*[ab]\b",  # 2
        r"\bpuva",  # 41
        r"photo\s*therap",  # 67
        r"excimer",  # 36
        r"308\s*nm",  # 1
        r"laser",  # 88
        r"light\s+therap",  # 3
        r"photo\s*chemo",  # 6
        r"sun\s*light|heliotherap|climatotherap",  # 13
        r"\b(?:red|blue|green|purple)\s+light",  # 3
        r"photodynamic",  # 2
        r"\bkhellin\b",  # 2
        # A psoralen is given only to be activated by light; the Unani
        # trials' control arm is methoxsalen solution and daily sun.
        r"psoralen|methoxsalen|8[\s-]?mop\b|trioxsalen",  # 17
    ),
    "Grafting & cell therapy": (
        r"graft",  # 73
        r"transplant",  # 31
        r"melanocyte[\s-]+keratinocyte",  # 1
        r"cell\s+suspension",  # 2
        r"suction\s+blister",  # 4
        r"\brecell\b",  # 5
        r"hair\s+follic",  # 3
        r"epidermal\s+cell",  # 1
        r"non[\s-]?cultured",  # 2
        r"cultured\s+melanocyte",  # 2
        r"stem\s+cell",  # 4
        r"exosome",  # 2
        r"\bsurgical\s+(?:treatment|therap|approach|modalit|combination)",  # 8
    ),
    "Microneedling & dermabrasion": (
        r"micro[\s-]?needl",  # 88
        r"dermabrasion",  # 48
        # Not fire needling, the acupuncture technique: two trials.
        r"(?<!fire )(?<!fire-)\bneedling",  # 18
    ),
    "Calcineurin inhibitor": (
        r"tacrolimus",  # 181
        r"pimecrolimus",  # 21
        r"calcineurin",  # 8
    ),
    "Corticosteroid": (
        # Not "steroidal": one ibuprofen trial is "non steroidal".
        r"steroid(?!al)",  # 42
        r"clobetasol",  # 30
        r"betamethasone",  # 40
        r"mometasone",  # 19
        r"dexamethasone",  # 4
        r"prednisolone",  # 6
        r"prednisone",  # 4
        r"triamcinolone",  # 14
        r"fluticasone",  # 8
        r"hydrocortisone",  # 2
        r"minipulse|mini[\s-]pulse",  # 2
        r"glucocorticoid",  # 5
        r"halometasone",  # 6
    ),
    "PDE4 inhibitor": (
        r"apremilast",  # 11
        r"roflumilast",  # 1
        r"crisaborole",  # 8
    ),
    "Vitamin D": (
        r"calcipotri",  # 44
        r"tacalcitol",  # 7
        r"vitamin\s+d",  # 17
        r"cholecalciferol",  # 1
    ),
    "Prostaglandin analogue": (
        r"latanoprost",  # 20
        r"bimatoprost",  # 24
        r"travoprost",  # 2
    ),
    "Biologic": (
        r"\b[a-z]+mab\b",  # 7
        r"abatacept|etanercept|alefacept",  # 3
        r"\bamg[\s-]?714\b",  # 1
    ),
    "Other immunomodulator": (
        r"methotrexate",  # 27
        r"cyclospor|ciclospor",  # 5
        r"azathioprin",  # 14
        r"mycophenol",  # 3
        r"minocyclin",  # 7
        r"hydroxychloroquin",  # 3
        r"rapamycin|sirolimus",  # 3
    ),
    "Traditional & herbal medicine": (
        r"\bsh?w?itra|shvitra",  # 46
        r"ayurved",  # 5
        r"siddha",  # 4
        r"unani",  # 14
        r"homo?eopath",  # 16
        r"herbal",  # 2
        r"granule",  # 6
        r"bakuchi|babchi|psoralea",  # 3
        r"\blepa\b",  # 3
        r"acupunct|fire[\s-]?needl",  # 16
        r"\bbaras\b",  # 1
        r"venpulli|venkutta",  # 7
        r"中药|中医",  # 1
    ),
    "Antioxidant & supplement": (
        r"ginkgo",  # 3
        r"polypodium",  # 5
        r"vitamin\s+e\b",  # 2
        r"superoxide",  # 8
        r"\bzinc\b",  # 2
        r"phenylalanine",  # 8
        r"antioxidant",  # 10
    ),
    "Platelet-rich plasma": (r"platelet[\s-]+rich|\bprp\b",),  # 53
    "5-fluorouracil": (r"fluorouracil|\b5[\s-]?fu\b",),  # 68
    "Depigmentation therapy": (
        r"monobenzone|monobenzyl|depigmentation\s+therap|depigmenting",
    ),  # 9
}

_COMPILED: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (group, tuple(re.compile(p) for p in patterns)) for group, patterns in TREATMENT_GROUPS.items()
)


def treatment_text(trial: Trial) -> str:
    """What the trial gives: intervention names and titles.

    An ICTRP intervention reads as the registry wrote it (``free_text``): its
    name is only the label, and the treatment is often in the rest.
    """
    texts = [str(i.get("free_text") or i.get("name") or "") for i in (trial.interventions or [])]
    return " | ".join([*dict.fromkeys(texts), trial.brief_title or "", trial.official_title or ""])


def is_treatment_study(trial: Trial) -> bool:
    """False for a study registered as observational, basic science, diagnostic or screening."""
    return (trial.study_type or "").strip().upper() not in NON_TREATMENT_TYPES


def treatment_groups(text: str) -> list[str]:
    """The groups whose treatments ``text`` names, in ``TREATMENT_GROUPS`` order."""
    folded = fold(text)
    groups = []
    for group, patterns in _COMPILED:
        named = any(p.search(folded) for p in patterns)
        if group == "JAK inhibitor":
            named = named or bool(match_agents(text))
        if named:
            groups.append(group)
    return groups


# -------------------------------------------------------------------- rows

_MAX_INTERVENTIONS = 200


def _interventions(trial: Trial) -> list[str]:
    """Intervention names worth showing.

    ISRCTN records write the intervention type where a name belongs ("Other",
    "Procedure/Surgery"), and CTRI records write "nil" for an empty arm.
    """
    names: list[str] = []
    for item in trial.interventions or []:
        name = " ".join(str(item.get("name") or "").split())
        kind = str(item.get("type") or "")
        if not name or name.lower() == kind.lower() or name.lower() in {"nil", "nil: nil", "none"}:
            continue
        if name.lower() not in (n.lower() for n in names):
            names.append(name)
    return names


def _shorten(text: str, limit: int = _MAX_INTERVENTIONS) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return cut + "…"


def _lead_sponsor(trial: Trial) -> str | None:
    sponsors = trial.sponsors or []
    lead = next((s for s in sponsors if s.get("role") == "lead"), sponsors[0] if sponsors else None)
    name = " ".join(str((lead or {}).get("name") or "").split())
    return name or None


def _titles(trial: Trial) -> tuple[str, str | None, str | None]:
    """``(title, official title, acronym)``.

    EU CTIS keeps a protocol code in the short-title field ("25-AOI-MED-02",
    "B7981041"), so a short title of one or two words gives way to the
    official one and is kept as the acronym.
    """
    brief = " ".join((trial.brief_title or "").split())
    official = " ".join((trial.official_title or "").split()) or None
    if official and len(brief.split()) <= 2:
        return official, None, brief or None
    return brief or official or trial.source_id, (official if official != brief else None), None


def _row(trial: Trial, copy: Trial | None) -> dict[str, Any]:
    """The explorer row for ``trial``, with blanks filled from an ICTRP ``copy``."""
    registered = is_registered(trial)
    title, official, acronym = _titles(trial)
    names = _interventions(trial) or (_interventions(copy) if copy else [])
    phase, numbers = phase_label(trial.phases or [])
    text = treatment_text(trial) + (" | " + treatment_text(copy) if copy else "")
    enrollment = trial.enrollment_count or (copy.enrollment_count if copy else None) or None

    row: dict[str, Any] = {
        "id": trial.source_id,
        "registry": registry_of(trial),
        "title": title,
        "official_title": official,
        "acronym": acronym,
        "groups": treatment_groups(text) + ([] if is_treatment_study(trial) else [OBSERVATIONAL]),
        "phase": phase,
        "phases": numbers,
        "status": status_label(trial),
        "interventions": _shorten("; ".join(names)) or None,
        "sponsor": _lead_sponsor(trial) or (_lead_sponsor(copy) if copy else None),
        "enrollment": enrollment,
        "countries": list(trial.countries or (copy.countries if copy else []) or []),
        "results": bool(trial.has_results or (copy.has_results if copy else False)),
        "url": record_url(trial),
    }
    if registered:
        row["via"] = "WHO ICTRP" if trial.source.value == "ictrp" else None
        row["study_type"] = (trial.study_type or "").strip().capitalize() or None
        row["start"] = iso_date(trial.start_date) or (iso_date(copy.start_date) if copy else None)
        row["completion"] = iso_date(trial.completion_date or trial.primary_completion_date)
    else:
        meta = trial.raw_metadata or {}
        row["journal"] = meta.get("journal")
        row["year"] = meta.get("year")
        row["pmid"] = meta.get("pmid")
        row["doi"] = meta.get("doi")
    return {k: v for k, v in row.items() if v not in (None, "", [])}


def explorer_rows(trials: Iterable[Trial]) -> tuple[list[dict[str, Any]], int]:
    """``(rows, merged)``: one row per trial, newest first, and how many copies merged."""
    chosen = [t for t in trials if in_explorer(t)]
    by_key: dict[str, list[Trial]] = {}
    for trial in chosen:
        key = _same_trial_key(trial.source_id) if is_registered(trial) else f"pub:{trial.source_id}"
        by_key.setdefault(key, []).append(trial)

    rows = []
    merged = 0
    for copies in by_key.values():
        # The registry's own record first; ICTRP's copy fills its blanks.
        copies.sort(key=lambda t: t.source.value == "ictrp")
        primary, *rest = copies
        merged += len(rest)
        rows.append(_row(primary, rest[0] if rest else None))

    def when(row: dict[str, Any]) -> str:
        return str(row.get("start") or row.get("year") or row.get("completion") or "")

    rows.sort(key=lambda r: r["id"])
    rows.sort(key=when, reverse=True)
    return rows, merged
