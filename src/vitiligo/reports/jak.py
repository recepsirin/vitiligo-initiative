"""Open JAK-inhibitor evidence atlas for vitiligo.

Assembles, from the local corpus only, a reusable dataset of every registered
vitiligo trial that tests a named JAK-family inhibitor:

- trial registry metadata (status, phase, sponsor, enrollment, dates),
- posted ClinicalTrials.gov outcome results and adverse-event counts, verbatim,
- linked publications (registry references + papers citing the trial ID),
- per-agent summaries joined with Open Targets clinical stage and mechanisms.

Nothing here is inferred by an LLM. Derived fields that rely on keyword rules
(route, phototherapy co-therapy, outcome domains) are labelled as heuristic in
the output so reviewers know what to verify.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, func, select

from vitiligo import __version__
from vitiligo.corpus_stats import get_corpus_stats
from vitiligo.priors import clinical_stage_rank
from vitiligo.reports.candidates import trial_stage
from vitiligo.storage import (
    Document,
    Prior,
    PriorKind,
    PriorSourceKind,
    SourceKind,
    Trial,
    get_engine,
)

# --------------------------------------------------------------------- agents


@dataclass(frozen=True)
class JakAgent:
    """A JAK-family inhibitor and the names it is registered under."""

    name: str
    aliases: tuple[str, ...] = ()
    note: str | None = None


# Canonical name first, then brand names and development codes. Only aliases
# with an unambiguous, published mapping are listed; matching is word-bounded
# and separator-tolerant ("PF-06651600" == "PF 06651600" == "PF06651600").
JAK_AGENTS: tuple[JakAgent, ...] = (
    JakAgent("ruxolitinib", ("INCB018424", "INCB-18424", "Opzelura", "Jakafi", "Jakavi")),
    JakAgent("povorcitinib", ("INCB054707",)),
    JakAgent("ritlecitinib", ("PF-06651600", "Litfulo")),
    JakAgent("upadacitinib", ("ABT-494", "Rinvoq")),
    JakAgent("baricitinib", ("LY3009104", "INCB028050", "Olumiant")),
    JakAgent("tofacitinib", ("CP-690550", "CP-690,550", "Xeljanz")),
    JakAgent("abrocitinib", ("PF-04965842", "Cibinqo")),
    JakAgent("brepocitinib", ("PF-06700841",)),
    JakAgent("deuruxolitinib", ("CTP-543", "Leqselvi")),
    JakAgent("delgocitinib", ("JTE-052", "Anzupgo")),
    JakAgent("ivarmacitinib", ("SHR0302",)),
    JakAgent("cerdulatinib", ("DMVT-502",)),
    JakAgent(
        "ifidancitinib",
        ("ATI-50002", "ATI-502"),
        note="Development codes ATI-50002 / ATI-502 per Open Targets (ChEMBL) synonyms.",
    ),
    JakAgent(
        "deucravacitinib",
        ("BMS-986165", "Sotyktu"),
        note="Allosteric TYK2 inhibitor (TYK2 is a JAK-family kinase).",
    ),
    JakAgent(
        "zasocitinib",
        ("TAK-279",),
        note="Allosteric TYK2 inhibitor (TYK2 is a JAK-family kinase).",
    ),
)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    parts = re.findall(r"[a-z0-9]+", alias.lower())
    body = r"[\s\-_,]*".join(re.escape(p) for p in parts)
    # Bounded so "ruxolitinib" never matches inside "deuruxolitinib".
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])", re.IGNORECASE)


_AGENT_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (agent.name, tuple(_alias_pattern(a) for a in (agent.name, *agent.aliases)))
    for agent in JAK_AGENTS
)


def match_agents(text: str) -> list[str]:
    """Return canonical names of JAK agents mentioned in ``text`` (catalogue order)."""
    return [name for name, patterns in _AGENT_PATTERNS if any(p.search(text) for p in patterns)]


# ------------------------------------------------------------ heuristic tags

_PLACEBO_RE = re.compile(r"\b(placebo|vehicle|sham|matching|to match)\b", re.IGNORECASE)
_TOPICAL_RE = re.compile(r"\b(cream|ointment|gel|lotion|foam|topical)\b", re.IGNORECASE)
_ORAL_RE = re.compile(r"\b(tablets?|capsules?|oral|orally)\b", re.IGNORECASE)
_PHOTOTHERAPY_RE = re.compile(
    r"(?<![a-z])(nb-?uvb|narrow[\s-]?band|phototherapy|excimer|uvb|puva)(?![a-z])",
    re.IGNORECASE,
)

# Keyword rules for tagging outcome measures; checked against title + description.
_OUTCOME_DOMAIN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("repigmentation", re.compile(r"vasi|repigment|depigment|lesion area", re.IGNORECASE)),
    (
        "patient_reported",
        re.compile(
            r"\bvns\b|noticeab|vitiqol|dlqi|quality of life|patient global|pgic|questionnaire",
            re.IGNORECASE,
        ),
    ),
    (
        "safety",
        re.compile(r"adverse|safety|tolerab|laboratory|vital sign|ecg", re.IGNORECASE),
    ),
    (
        "pharmacokinetics",
        re.compile(r"pharmacokinetic|plasma concentration|\bcmax\b|\bauc\b", re.IGNORECASE),
    ),
    ("biomarker", re.compile(r"biomarker|cxcl|chemokine|gene expression", re.IGNORECASE)),
)

_NCT_RE = re.compile(r"\bNCT\d{8}\b")
_CTIS_RE = re.compile(r"\b20\d{2}-\d{6}-\d{2}-\d{2}\b")


def outcome_domains(title: str, description: str | None) -> list[str]:
    text = f"{title} {description or ''}"
    return [domain for domain, rule in _OUTCOME_DOMAIN_RULES if rule.search(text)]


def trial_url(source: str, source_id: str) -> str | None:
    if source == "ctgov":
        return f"https://clinicaltrials.gov/study/{source_id}"
    if source == "euctr":
        return f"https://euclinicaltrials.eu/ctis-public/view/{source_id}"
    if source == "ictrp":
        return f"https://trialsearch.who.int/Trial2.aspx?TrialID={source_id}"
    return None


# -------------------------------------------------------------- data shapes


@dataclass
class Measurement:
    group_id: str
    group_title: str | None
    class_title: str | None
    category_title: str | None
    value: str | None
    spread: str | None
    lower_limit: str | None
    upper_limit: str | None
    n_analyzed: str | None


@dataclass
class OutcomeResult:
    type: str | None
    title: str
    description: str | None
    time_frame: str | None
    param_type: str | None
    dispersion_type: str | None
    unit: str | None
    reporting_status: str | None
    domains: list[str]
    measurements: list[Measurement]
    analyses: list[dict[str, Any]]
    # How the registry says missing data were handled, verbatim. A responder
    # rate means a different thing under each, so the text travels with the row.
    population_description: str | None = None


@dataclass
class AdverseEventGroup:
    group_id: str
    title: str | None
    serious_affected: int | None
    serious_at_risk: int | None
    other_affected: int | None
    other_at_risk: int | None
    deaths_affected: int | None
    deaths_at_risk: int | None


@dataclass
class AdverseEvents:
    time_frame: str | None
    other_frequency_threshold: str | None
    groups: list[AdverseEventGroup]


@dataclass
class PublicationRef:
    pmid: str | None
    source_ref: str | None  # corpus record (e.g. "pmc:PMC123") when there is no PMID
    relation: str  # registry:RESULT | registry:DERIVED | cites_trial_id
    title: str | None
    in_corpus: bool


@dataclass
class JakTrial:
    """One registry record. Records of the same study share ``study_id``."""

    study_id: str
    linked_records: list[str]
    agents: list[str]
    match_basis: str  # "registry_text" | "linked_registry_record"
    source: str
    source_id: str
    url: str | None
    title: str | None
    status: str | None
    phases: list[str]
    stage: str | None
    study_type: str | None
    jak_arm_types: list[str]
    routes: list[str]
    phototherapy_in_trial: bool
    jak_with_phototherapy_arm: bool | None
    lead_sponsor: str | None
    sponsor_class: str | None
    enrollment: int | None
    start_date: str | None
    completion_date: str | None
    countries: list[str]
    has_results: bool
    outcomes: list[OutcomeResult]
    adverse_events: AdverseEvents | None
    publications: list[PublicationRef]


@dataclass
class AgentSummary:
    name: str
    note: str | None
    prior_stage: str | None
    prior_source_id: str | None
    mechanisms: list[str]
    studies: int
    registry_records: int
    studies_with_posted_results: int
    max_trial_stage: str | None
    routes: list[str]
    statuses: dict[str, int]
    lead_sponsors: list[str]
    papers_mentioning: int


@dataclass
class JakAtlas:
    generated_at: str
    engine_version: str
    corpus: dict[str, Any]
    methodology: str
    caveats: list[str]
    agents: list[AgentSummary]
    trials: list[JakTrial] = field(default_factory=list)


# ------------------------------------------------------------- CT.gov results


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _denom_counts(denoms: list[dict[str, Any]] | None) -> dict[str, str]:
    """Map groupId -> participant count from a CT.gov ``denoms`` block."""
    for denom in denoms or []:
        units = str(denom.get("units") or "").lower()
        if units in {"participants", ""}:
            return {
                str(c.get("groupId")): str(c.get("value"))
                for c in denom.get("counts") or []
                if c.get("groupId") is not None
            }
    return {}


_ANALYSIS_KEYS = (
    "groupIds",
    "statisticalMethod",
    "pValue",
    "paramType",
    "paramValue",
    "ciPctValue",
    "ciNumSides",
    "ciLowerLimit",
    "ciUpperLimit",
    "nonInferiorityType",
)


def parse_ctgov_outcomes(study: dict[str, Any]) -> list[OutcomeResult]:
    """Extract posted outcome measures from a CT.gov v2 study, values verbatim."""
    results = study.get("resultsSection") or {}
    measures = (results.get("outcomeMeasuresModule") or {}).get("outcomeMeasures") or []
    parsed: list[OutcomeResult] = []
    for om in measures:
        title = _str_or_none(om.get("title")) or "(untitled outcome)"
        description = _str_or_none(om.get("description"))
        group_titles = {
            str(g.get("id")): _str_or_none(g.get("title")) for g in om.get("groups") or []
        }
        measure_denoms = _denom_counts(om.get("denoms"))

        measurements: list[Measurement] = []
        for cls in om.get("classes") or []:
            class_denoms = _denom_counts(cls.get("denoms")) or measure_denoms
            for cat in cls.get("categories") or []:
                for m in cat.get("measurements") or []:
                    gid = str(m.get("groupId"))
                    measurements.append(
                        Measurement(
                            group_id=gid,
                            group_title=group_titles.get(gid),
                            class_title=_str_or_none(cls.get("title")),
                            category_title=_str_or_none(cat.get("title")),
                            value=_str_or_none(m.get("value")),
                            spread=_str_or_none(m.get("spread")),
                            lower_limit=_str_or_none(m.get("lowerLimit")),
                            upper_limit=_str_or_none(m.get("upperLimit")),
                            n_analyzed=class_denoms.get(gid),
                        )
                    )

        analyses = [
            {key: a[key] for key in _ANALYSIS_KEYS if a.get(key) is not None}
            for a in om.get("analyses") or []
        ]
        parsed.append(
            OutcomeResult(
                type=_str_or_none(om.get("type")),
                title=title,
                description=description,
                time_frame=_str_or_none(om.get("timeFrame")),
                param_type=_str_or_none(om.get("paramType")),
                dispersion_type=_str_or_none(om.get("dispersionType")),
                unit=_str_or_none(om.get("unitOfMeasure")),
                reporting_status=_str_or_none(om.get("reportingStatus")),
                domains=outcome_domains(title, description),
                measurements=measurements,
                analyses=analyses,
                population_description=_str_or_none(om.get("populationDescription")),
            )
        )
    return parsed


def parse_ctgov_adverse_events(study: dict[str, Any]) -> AdverseEvents | None:
    """Extract per-group serious / other / death counts from a CT.gov v2 study."""
    module = (study.get("resultsSection") or {}).get("adverseEventsModule")
    if not module:
        return None
    groups = [
        AdverseEventGroup(
            group_id=str(g.get("id")),
            title=_str_or_none(g.get("title")),
            serious_affected=_int_or_none(g.get("seriousNumAffected")),
            serious_at_risk=_int_or_none(g.get("seriousNumAtRisk")),
            other_affected=_int_or_none(g.get("otherNumAffected")),
            other_at_risk=_int_or_none(g.get("otherNumAtRisk")),
            deaths_affected=_int_or_none(g.get("deathsNumAffected")),
            deaths_at_risk=_int_or_none(g.get("deathsNumAtRisk")),
        )
        for g in module.get("eventGroups") or []
    ]
    return AdverseEvents(
        time_frame=_str_or_none(module.get("timeFrame")),
        other_frequency_threshold=_str_or_none(module.get("frequencyThreshold")),
        groups=groups,
    )


def _registry_references(study: dict[str, Any]) -> list[tuple[str, str]]:
    """(pmid, relation) for CT.gov references describing this trial's results."""
    refs = ((study.get("protocolSection") or {}).get("referencesModule") or {}).get(
        "references"
    ) or []
    out: list[tuple[str, str]] = []
    for ref in refs:
        ref_type = str(ref.get("type") or "").upper()
        pmid = _str_or_none(ref.get("pmid"))
        if pmid and ref_type in {"RESULT", "DERIVED"}:
            out.append((pmid, f"registry:{ref_type}"))
    return out


# ------------------------------------------------------------------ assembly


def _source_value(value: Any) -> str:
    return str(value.value if hasattr(value, "value") else value)


def _trial_match_text(trial: Trial) -> str:
    """Titles + intervention names/other names/descriptions + arm intervention names.

    Summaries are deliberately excluded: they often name JAK inhibitors as
    background or comparators without testing them.
    """
    parts = [trial.brief_title or "", trial.official_title or ""]
    for iv in trial.interventions or []:
        parts.append(str(iv.get("name") or ""))
        parts.append(str(iv.get("description") or ""))
        parts.extend(str(n) for n in iv.get("other_names") or [])
    for arm in trial.arm_groups or []:
        parts.extend(str(n) for n in arm.get("intervention_names") or [])
    return " \n ".join(parts)


def _is_placebo(text: str) -> bool:
    return bool(_PLACEBO_RE.search(text))


def _jak_intervention_texts(trial: Trial) -> list[str]:
    """Text of each active (non-placebo) intervention that names a JAK agent."""
    texts: list[str] = []
    for iv in trial.interventions or []:
        text = " ".join(
            [
                str(iv.get("name") or ""),
                str(iv.get("description") or ""),
                *(str(n) for n in iv.get("other_names") or []),
            ]
        )
        name = str(iv.get("name") or "")
        if match_agents(text) and not _is_placebo(name):
            texts.append(text)
    return texts


def _routes(trial: Trial) -> list[str]:
    """Routes of the JAK interventions themselves (placebo/vehicle ignored)."""
    routes: set[str] = set()
    for text in _jak_intervention_texts(trial):
        if _TOPICAL_RE.search(text):
            routes.add("topical")
        if _ORAL_RE.search(text):
            routes.add("oral")
    return sorted(routes)


def _jak_arms(trial: Trial) -> list[dict[str, Any]]:
    """Registry arms that give an active JAK agent (by arm intervention names or label)."""
    arms: list[dict[str, Any]] = []
    for arm in trial.arm_groups or []:
        names = [str(n) for n in arm.get("intervention_names") or []]
        label = str(arm.get("label") or "")
        if any(match_agents(t) and not _is_placebo(t) for t in [label, *names]):
            arms.append(arm)
    return arms


def _arm_text(arm: dict[str, Any]) -> str:
    names = " ".join(str(n) for n in arm.get("intervention_names") or [])
    return f"{arm.get('label') or ''} {names}"


def _phototherapy_in_trial(trial: Trial) -> bool:
    texts = [trial.brief_title or "", trial.official_title or ""]
    texts += [str(iv.get("name") or "") for iv in trial.interventions or []]
    texts += [_arm_text(arm) for arm in trial.arm_groups or []]
    return any(_PHOTOTHERAPY_RE.search(t) for t in texts)


def _jak_with_phototherapy_arm(trial: Trial) -> bool | None:
    """Whether one arm combines a JAK agent with phototherapy.

    None (undetermined) when the registry publishes no arms, or when
    phototherapy appears only in the title — arms then do not itemize it.
    """
    if not trial.arm_groups:
        return None
    if any(_PHOTOTHERAPY_RE.search(_arm_text(arm)) for arm in _jak_arms(trial)):
        return True
    listed = [str(iv.get("name") or "") for iv in trial.interventions or []]
    listed += [_arm_text(arm) for arm in trial.arm_groups or []]
    if _phototherapy_in_trial(trial) and not any(_PHOTOTHERAPY_RE.search(t) for t in listed):
        return None
    return False


def _lead_sponsor(trial: Trial) -> tuple[str | None, str | None]:
    for sponsor in trial.sponsors or []:
        if sponsor.get("role") == "lead":
            return _str_or_none(sponsor.get("name")), _str_or_none(sponsor.get("class"))
    return None, None


def _corpus_paper_index(
    session: Session,
) -> tuple[dict[str, list[tuple[str, str | None]]], dict[str, str | None], Counter[str]]:
    """One pass over the documents table.

    Returns (trial id -> [(pmid-or-source-ref, title)], pmid -> title, agent -> paper
    count). A paper held as both a PubMed and a PMC record counts once.
    """
    cites: dict[str, list[tuple[str, str | None]]] = {}
    pmid_titles: dict[str, str | None] = {}
    agent_refs: dict[str, set[str]] = {}
    # PMC full-text records carry their PubMed ID; resolve to it so the same paper
    # is not listed twice. (SQLite JSON1 — avoids loading PMC full text.)
    pmc_pmids = {
        source_id: str(pmid)
        for source_id, pmid in session.exec(
            select(Document.source_id, func.json_extract(Document.raw_metadata, "$.pmid")).where(
                Document.source == SourceKind.PMC
            )
        ).all()
        if pmid is not None and str(pmid).isdigit()
    }
    rows = session.exec(
        select(Document.source, Document.source_id, Document.title, Document.abstract)
    ).all()
    for source, source_id, title, abstract in rows:
        src = _source_value(source)
        text = f"{title or ''} {abstract or ''}"
        if src == SourceKind.PUBMED.value:
            pmid_titles[source_id] = title
            ref = source_id
        elif src == SourceKind.PMC.value and source_id in pmc_pmids:
            ref = pmc_pmids[source_id]
        else:
            ref = f"{src}:{source_id}"
        for trial_id in set(_NCT_RE.findall(text)) | set(_CTIS_RE.findall(text)):
            refs = cites.setdefault(trial_id, [])
            if all(existing != ref for existing, _ in refs):
                refs.append((ref, title))
        for agent in match_agents(text):
            agent_refs.setdefault(agent, set()).add(ref)
    return cites, pmid_titles, Counter({a: len(refs) for a, refs in agent_refs.items()})


def _publications(
    trial: Trial,
    study: dict[str, Any] | None,
    cites: dict[str, list[tuple[str, str | None]]],
    pmid_titles: dict[str, str | None],
) -> list[PublicationRef]:
    pubs: list[PublicationRef] = []
    seen: set[str] = set()
    for pmid, relation in _registry_references(study or {}):
        if pmid in seen:
            continue
        seen.add(pmid)
        pubs.append(
            PublicationRef(
                pmid=pmid,
                source_ref=None,
                relation=relation,
                title=pmid_titles.get(pmid),
                in_corpus=pmid in pmid_titles,
            )
        )
    for ref, title in cites.get(trial.source_id, []):
        if ref in seen:
            continue
        seen.add(ref)
        is_pmid = ref.isdigit()
        pubs.append(
            PublicationRef(
                pmid=ref if is_pmid else None,
                source_ref=None if is_pmid else ref,
                relation="cites_trial_id",
                title=title,
                in_corpus=True,
            )
        )
    return pubs


def _ot_drug_priors(session: Session) -> dict[str, Prior]:
    """Most advanced Open Targets drug prior per JAK agent (salt forms folded in)."""
    best: dict[str, Prior] = {}
    priors = session.exec(
        select(Prior).where(
            Prior.kind == PriorKind.DRUG, Prior.source == PriorSourceKind.OPENTARGETS
        )
    ).all()
    for prior in priors:
        names = " ".join([prior.name, *(prior.synonyms or [])])
        for agent in match_agents(names):
            current = best.get(agent)
            if current is None or clinical_stage_rank(prior.clinical_stage) > clinical_stage_rank(
                current.clinical_stage
            ):
                best[agent] = prior
    return best


def _norm_code(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


# Sponsor protocol codes shorter than this are too generic to link registries on.
_MIN_PROTOCOL_CODE_LEN = 5


def _link_registry_records(trials: list[Trial]) -> dict[str, str]:
    """Group registry records describing the same study; return source_id -> study_id.

    Links come only from identifiers the registries publish:
    - ClinicalTrials.gov ``secondaryIdInfos`` naming another stored record,
    - a CT.gov sponsor protocol ID (``orgStudyIdInfo``) equal to a CTIS short
      title (CTIS stores the sponsor protocol code there),
    - ICTRP cross-registry keys recorded at ingestion.
    The study_id is the CT.gov NCT number when the group has one.
    """
    parent: dict[str, str] = {t.source_id: t.source_id for t in trials}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    source_of = {t.source_id: _source_value(t.source) for t in trials}

    def union(a: str, b: str) -> None:
        # Only cross-registry links: a CT.gov record citing another NCT (e.g. a
        # parent trial of an extension study) is a different study, not a twin.
        if a in parent and b in parent and source_of[a] != source_of[b]:
            parent[find(a)] = find(b)

    ctis_codes: dict[str, str] = {}
    for trial in trials:
        if _source_value(trial.source) == "euctr":
            code = _norm_code(((trial.raw_metadata or {}).get("search") or {}).get("shortTitle"))
            if len(code) >= _MIN_PROTOCOL_CODE_LEN:
                ctis_codes[code] = trial.source_id

    for trial in trials:
        source = _source_value(trial.source)
        meta = trial.raw_metadata or {}
        if source == "ctgov":
            ident = ((meta.get("study") or {}).get("protocolSection") or {}).get(
                "identificationModule"
            ) or {}
            for sec in ident.get("secondaryIdInfos") or []:
                union(trial.source_id, str(sec.get("id") or "").strip())
            org = _norm_code((ident.get("orgStudyIdInfo") or {}).get("id"))
            if len(org) >= _MIN_PROTOCOL_CODE_LEN and org in ctis_codes:
                union(trial.source_id, ctis_codes[org])
        elif source == "ictrp":
            for key in meta.get("cross_registry_keys") or []:
                union(trial.source_id, str(key).split(":", 1)[-1])

    groups: dict[str, list[Trial]] = {}
    for trial in trials:
        groups.setdefault(find(trial.source_id), []).append(trial)
    study_ids: dict[str, str] = {}
    for members in groups.values():
        ranked = sorted(
            members,
            key=lambda t: (_SOURCE_PRIORITY.get(_source_value(t.source), 9), t.source_id),
        )
        for member in members:
            study_ids[member.source_id] = ranked[0].source_id
    return study_ids


_SOURCE_PRIORITY = {"ctgov": 0, "euctr": 1, "ictrp": 2}


def _build_record(
    trial: Trial,
    *,
    agents: list[str],
    match_basis: str,
    study_id: str,
    linked: list[str],
    cites: dict[str, list[tuple[str, str | None]]],
    pmid_titles: dict[str, str | None],
) -> JakTrial:
    source = _source_value(trial.source)
    study = (trial.raw_metadata or {}).get("study") if source == "ctgov" else None
    lead, lead_class = _lead_sponsor(trial)
    return JakTrial(
        study_id=study_id,
        linked_records=linked,
        agents=agents,
        match_basis=match_basis,
        source=source,
        source_id=trial.source_id,
        url=trial_url(source, trial.source_id),
        title=trial.brief_title or trial.official_title,
        status=trial.status,
        phases=list(trial.phases or []),
        stage=trial_stage(trial.phases or []),
        study_type=trial.study_type,
        jak_arm_types=sorted({str(a.get("type")) for a in _jak_arms(trial) if a.get("type")}),
        routes=_routes(trial),
        phototherapy_in_trial=_phototherapy_in_trial(trial),
        jak_with_phototherapy_arm=_jak_with_phototherapy_arm(trial),
        lead_sponsor=lead,
        sponsor_class=lead_class,
        enrollment=trial.enrollment_count,
        start_date=trial.start_date,
        completion_date=trial.completion_date,
        countries=list(trial.countries or []),
        has_results=bool(trial.has_results),
        outcomes=parse_ctgov_outcomes(study) if study else [],
        adverse_events=parse_ctgov_adverse_events(study) if study else None,
        publications=_publications(trial, study, cites, pmid_titles),
    )


def jak_record_from_ctgov(study: dict[str, Any]) -> JakTrial | None:
    """An atlas record for one raw ClinicalTrials.gov study, without the corpus.

    Registry linking and corpus publications are left empty; outcomes and
    adverse events are parsed exactly as in the atlas.
    """
    from vitiligo.sources.ctgov import parse_ctgov_study

    trial = parse_ctgov_study(study)
    if trial is None:
        return None
    return _build_record(
        trial,
        agents=match_agents(_trial_match_text(trial)),
        match_basis="registry_text",
        study_id=trial.source_id,
        linked=[],
        cites={},
        pmid_titles={},
    )


def build_jak_atlas() -> JakAtlas:
    """Build the JAK-inhibitor atlas from the configured local corpus."""
    with Session(get_engine(), expire_on_commit=False) as session:
        all_trials = list(session.exec(select(Trial)).all())
        cites, pmid_titles, agent_papers = _corpus_paper_index(session)
        priors = _ot_drug_priors(session)

    study_ids = _link_registry_records(all_trials)
    own_agents = {t.source_id: match_agents(_trial_match_text(t)) for t in all_trials}

    group_agents: dict[str, list[str]] = {}
    group_members: dict[str, list[str]] = {}
    for trial in all_trials:
        sid = study_ids[trial.source_id]
        group_members.setdefault(sid, []).append(trial.source_id)
        for agent in own_agents[trial.source_id]:
            group_agents.setdefault(sid, [])
            if agent not in group_agents[sid]:
                group_agents[sid].append(agent)

    records: list[JakTrial] = []
    for trial in all_trials:
        sid = study_ids[trial.source_id]
        if sid not in group_agents:
            continue
        own = own_agents[trial.source_id]
        records.append(
            _build_record(
                trial,
                agents=own or sorted(group_agents[sid], key=JAK_AGENT_ORDER.__getitem__),
                match_basis="registry_text" if own else "linked_registry_record",
                study_id=sid,
                linked=sorted(m for m in group_members[sid] if m != trial.source_id),
                cites=cites,
                pmid_titles=pmid_titles,
            )
        )

    study_rank = {
        sid: max(clinical_stage_rank(r.stage) for r in records if r.study_id == sid)
        for sid in {r.study_id for r in records}
    }
    records.sort(
        key=lambda r: (
            min(JAK_AGENT_ORDER[a] for a in group_agents[r.study_id]),
            -study_rank[r.study_id],
            r.study_id,
            _SOURCE_PRIORITY.get(r.source, 9),
            r.source_id,
        )
    )

    summaries = [
        _summarize_agent(agent, records, priors.get(agent.name), agent_papers[agent.name])
        for agent in JAK_AGENTS
    ]
    summaries = [s for s in summaries if s.studies or s.prior_stage or s.papers_mentioning]
    summaries.sort(
        key=lambda s: (
            -clinical_stage_rank(s.prior_stage),
            -clinical_stage_rank(s.max_trial_stage),
            -s.studies,
            s.name,
        )
    )

    return JakAtlas(
        generated_at=datetime.now(UTC).isoformat(),
        engine_version=__version__,
        corpus=get_corpus_stats(),
        methodology=_METHODOLOGY,
        caveats=list(_CAVEATS),
        agents=summaries,
        trials=records,
    )


JAK_AGENT_ORDER: dict[str, int] = {agent.name: idx for idx, agent in enumerate(JAK_AGENTS)}


def _summarize_agent(
    agent: JakAgent,
    records: list[JakTrial],
    prior: Prior | None,
    papers: int,
) -> AgentSummary:
    mine = [r for r in records if agent.name in r.agents]
    study_ids = list(dict.fromkeys(r.study_id for r in mine))
    # Status per study comes from its primary record (CT.gov when available).
    primary = {r.study_id: r for r in mine if r.source_id == r.study_id}
    statuses = Counter(
        (primary[sid].status if sid in primary else None) or "UNKNOWN" for sid in study_ids
    )
    stages = [r.stage for r in mine if r.stage]
    mechanisms = [
        str(m.get("mechanism"))
        for m in (prior.mechanisms if prior else []) or []
        if isinstance(m, dict) and m.get("mechanism")
    ]
    return AgentSummary(
        name=agent.name,
        note=agent.note,
        prior_stage=prior.clinical_stage if prior else None,
        prior_source_id=prior.source_id if prior else None,
        mechanisms=mechanisms,
        studies=len(study_ids),
        registry_records=len(mine),
        studies_with_posted_results=len({r.study_id for r in mine if r.outcomes}),
        max_trial_stage=max(stages, key=clinical_stage_rank) if stages else None,
        routes=sorted({route for r in mine for route in r.routes}),
        statuses=dict(statuses.most_common()),
        lead_sponsors=_dedupe_sponsors(r.lead_sponsor for r in mine if r.lead_sponsor),
        papers_mentioning=papers,
    )


_CORPORATE_SUFFIXES = frozenset({"co", "corp", "corporation", "inc", "llc", "ltd", "limited"})


def _sponsor_key(name: str) -> str:
    """Case/punctuation-insensitive key that ignores trailing corporate suffixes."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    while len(words) > 1 and words[-1] in _CORPORATE_SUFFIXES:
        words.pop()
    return " ".join(words)


def _dedupe_sponsors(names: Iterable[str]) -> list[str]:
    """Registries spell sponsors differently ("Pfizer" / "Pfizer Inc."); keep the first."""
    seen: dict[str, str] = {}
    for name in names:
        seen.setdefault(_sponsor_key(name), name)
    return list(seen.values())


_METHODOLOGY = (
    "Registry records are every trial in the local corpus (ClinicalTrials.gov, EU CTIS, "
    "WHO ICTRP) whose title, intervention names/descriptions/other names, or arm "
    "intervention names mention a catalogued JAK-family inhibitor by name, brand, or "
    "development code. Records of the same study are linked only through identifiers the "
    "registries publish (CT.gov secondary IDs, CT.gov sponsor protocol ID equal to the CTIS "
    "short title, ICTRP cross-registry IDs); a linked record with no drug text of its own "
    "inherits the study's agents. Outcome results and adverse-event counts are copied "
    "verbatim from posted ClinicalTrials.gov results; nothing is re-analysed or pooled. "
    "Publications are registry RESULT/DERIVED references plus corpus papers whose title or "
    "abstract cites the trial identifier. Agent clinical stage and mechanisms come from "
    "Open Targets drug priors for vitiligo (EFO_0004208)."
)

_CAVEATS: tuple[str, ...] = (
    "Research dataset — not medical advice, not a treatment recommendation.",
    "Posted registry results are sponsor-reported and not peer reviewed; values are "
    "verbatim strings, including 'NA'.",
    "Only ClinicalTrials.gov exposes structured results; EU CTIS and ICTRP records carry "
    "registry metadata only.",
    "Adverse-event 'other' counts include only events above the trial's reporting "
    "frequency threshold.",
    "Heuristic fields (keyword rules — verify before citing): routes, "
    "phototherapy_in_trial, jak_with_phototherapy_arm, outcome domains. "
    "jak_with_phototherapy_arm is null when the registry publishes no arm data or names "
    "phototherapy only in the title.",
    "jak_arm_types is the registry's own arm type (e.g. EXPERIMENTAL, ACTIVE_COMPARATOR); "
    "a JAK inhibitor can be the comparator rather than the drug under test.",
    "Coverage is limited to the corpus snapshot; trials registered after the last "
    "ingestion, and JAK inhibitors outside the catalogue, are absent.",
    "Agent counts are unique studies; a study testing several agents counts once per agent.",
)


# ------------------------------------------------------------------ renderers


def atlas_to_dict(atlas: JakAtlas) -> dict[str, Any]:
    return asdict(atlas)


def render_jak_atlas_markdown(atlas: JakAtlas) -> str:
    lines: list[str] = [
        "# JAK Inhibitors in Vitiligo — Open Evidence Atlas",
        "",
        f"**Generated:** {atlas.generated_at}  ",
        f"**Engine:** v{atlas.engine_version}  ",
        f"**Corpus snapshot:** {atlas.corpus.get('documents', 0):,} documents, "
        f"{atlas.corpus.get('trials', 0)} trials, {atlas.corpus.get('priors', 0)} priors  ",
        "**Status:** Research dataset — not medical advice, not a treatment recommendation.",
        "",
        "## Methodology",
        "",
        atlas.methodology,
        "",
        "## Caveats",
        "",
        *[f"- {c}" for c in atlas.caveats],
        "",
        "## Agents",
        "",
        "| Agent | Open Targets stage | Highest trial phase | Studies | Registry records "
        "| Studies with posted results | Routes | Papers | Lead sponsors |",
        "|---|---|---|---:|---:|---:|---|---:|---|",
    ]
    for s in atlas.agents:
        name = f"{s.name} ¹" if s.note else s.name
        lines.append(
            f"| {name} | {s.prior_stage or '—'} | {s.max_trial_stage or '—'} | {s.studies} "
            f"| {s.registry_records} | {s.studies_with_posted_results} "
            f"| {', '.join(s.routes) or '—'} | {s.papers_mentioning} "
            f"| {_md(', '.join(s.lead_sponsors[:4])) or '—'} |"
        )
    notes = [s for s in atlas.agents if s.note]
    if notes:
        lines.append("")
        lines.extend(f"¹ **{s.name}:** {s.note}  " for s in notes)
    lines.extend(
        [
            "",
            "## Studies",
            "",
            "One row per study; metadata from the primary record (CT.gov when available).",
            "",
            "| Agent(s) | Study | Also registered as | Phase | Status | Route | JAK arm type "
            "| JAK + phototherapy arm | Lead sponsor | N | Results | Publications |",
            "|---|---|---|---|---|---|---|---|---|---:|---|---:|",
        ]
    )
    for study in _studies(atlas.trials):
        p = study[0]
        ref = f"[{p.source_id}]({p.url})" if p.url else p.source_id
        others = ", ".join(f"[{r.source_id}]({r.url})" if r.url else r.source_id for r in study[1:])
        routes = sorted({route for r in study for route in r.routes})
        combo = {True: "yes", False: "no", None: "—"}[p.jak_with_phototherapy_arm]
        pubs = {pub.pmid or pub.source_ref for r in study for pub in r.publications}
        lines.append(
            f"| {', '.join(p.agents)} | {ref} | {others or '—'} | {', '.join(p.phases) or '—'} "
            f"| {p.status or '—'} | {', '.join(routes) or '—'} "
            f"| {', '.join(p.jak_arm_types) or '—'} | {combo} | {_md(p.lead_sponsor or '—')} "
            f"| {p.enrollment if p.enrollment is not None else '—'} "
            f"| {'posted' if any(r.outcomes for r in study) else '—'} | {len(pubs)} |"
        )

    lines.extend(["", "## Posted primary outcomes (ClinicalTrials.gov, verbatim)", ""])
    for t in atlas.trials:
        primary = [o for o in t.outcomes if (o.type or "").upper() == "PRIMARY"]
        if not primary:
            continue
        lines.append(f"### {t.source_id} — {_md(t.title or '(untitled)')}")
        lines.append("")
        for o in primary:
            unit = f" ({o.unit})" if o.unit else ""
            lines.append(f"**{_md(o.title)}**{unit} — {o.param_type or 'value'}")
            if o.time_frame:
                lines.append(f"  _Time frame: {_md(o.time_frame)}_")
            lines.append("")
            lines.append("| Group | Timepoint / class | Value | Spread / CI | N |")
            lines.append("|---|---|---|---|---:|")
            for m in o.measurements:
                if m.n_analyzed == "0" and m.value is None:
                    continue
                interval = m.spread or (
                    f"{m.lower_limit} to {m.upper_limit}" if m.lower_limit or m.upper_limit else ""
                )
                label = " / ".join(x for x in (m.class_title, m.category_title) if x)
                lines.append(
                    f"| {_md(m.group_title or m.group_id)} | {_md(label) or '—'} "
                    f"| {m.value or '—'} | {interval or '—'} | {m.n_analyzed or '—'} |"
                )
            lines.append("")
    lines.extend(
        [
            "## Reproduce",
            "",
            "`vitiligo report jak --json exports/jak-atlas.json "
            "--markdown exports/jak-atlas.md --csv-dir exports/jak-atlas`",
            "",
        ]
    )
    return "\n".join(lines)


def _studies(records: list[JakTrial]) -> list[list[JakTrial]]:
    """Group records by study (input order kept); the primary record comes first."""
    groups: dict[str, list[JakTrial]] = {}
    for record in records:
        groups.setdefault(record.study_id, []).append(record)
    return [sorted(members, key=lambda r: r.source_id != r.study_id) for members in groups.values()]


def _md(text: str) -> str:
    """Escape characters that break Markdown table cells."""
    return text.replace("|", "\\|").replace("\n", " ")


def write_jak_atlas_csv(atlas: JakAtlas, directory: Path) -> list[Path]:
    """Write trials.csv, outcomes.csv and adverse_events.csv; return written paths."""
    directory.mkdir(parents=True, exist_ok=True)
    trials_path = directory / "trials.csv"
    outcomes_path = directory / "outcomes.csv"
    ae_path = directory / "adverse_events.csv"

    with trials_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "study_id",
                "linked_records",
                "agents",
                "match_basis",
                "source",
                "source_id",
                "url",
                "title",
                "status",
                "phases",
                "stage",
                "study_type",
                "jak_arm_types",
                "routes_heuristic",
                "phototherapy_in_trial_heuristic",
                "jak_with_phototherapy_arm_heuristic",
                "lead_sponsor",
                "sponsor_class",
                "enrollment",
                "start_date",
                "completion_date",
                "countries",
                "has_results",
                "posted_outcomes",
                "publication_pmids",
            ]
        )
        for t in atlas.trials:
            writer.writerow(
                [
                    t.study_id,
                    ";".join(t.linked_records),
                    ";".join(t.agents),
                    t.match_basis,
                    t.source,
                    t.source_id,
                    t.url or "",
                    t.title or "",
                    t.status or "",
                    ";".join(t.phases),
                    t.stage or "",
                    t.study_type or "",
                    ";".join(t.jak_arm_types),
                    ";".join(t.routes),
                    t.phototherapy_in_trial,
                    "" if t.jak_with_phototherapy_arm is None else t.jak_with_phototherapy_arm,
                    t.lead_sponsor or "",
                    t.sponsor_class or "",
                    "" if t.enrollment is None else t.enrollment,
                    t.start_date or "",
                    t.completion_date or "",
                    ";".join(t.countries),
                    t.has_results,
                    len(t.outcomes),
                    ";".join(p.pmid for p in t.publications if p.pmid),
                ]
            )

    with outcomes_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "source_id",
                "agents",
                "outcome_type",
                "outcome_title",
                "domains_heuristic",
                "time_frame",
                "param_type",
                "dispersion_type",
                "unit",
                "group_id",
                "group_title",
                "class_title",
                "category_title",
                "value",
                "spread",
                "lower_limit",
                "upper_limit",
                "n_analyzed",
            ]
        )
        for t in atlas.trials:
            for o in t.outcomes:
                for m in o.measurements:
                    writer.writerow(
                        [
                            t.source_id,
                            ";".join(t.agents),
                            o.type or "",
                            o.title,
                            ";".join(o.domains),
                            o.time_frame or "",
                            o.param_type or "",
                            o.dispersion_type or "",
                            o.unit or "",
                            m.group_id,
                            m.group_title or "",
                            m.class_title or "",
                            m.category_title or "",
                            m.value or "",
                            m.spread or "",
                            m.lower_limit or "",
                            m.upper_limit or "",
                            m.n_analyzed or "",
                        ]
                    )

    with ae_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "source_id",
                "agents",
                "time_frame",
                "other_frequency_threshold_pct",
                "group_id",
                "group_title",
                "serious_affected",
                "serious_at_risk",
                "other_affected",
                "other_at_risk",
                "deaths_affected",
                "deaths_at_risk",
            ]
        )
        for t in atlas.trials:
            if t.adverse_events is None:
                continue
            ae = t.adverse_events
            for g in ae.groups:
                writer.writerow(
                    [
                        t.source_id,
                        ";".join(t.agents),
                        ae.time_frame or "",
                        ae.other_frequency_threshold or "",
                        g.group_id,
                        g.title or "",
                        *(
                            "" if v is None else v
                            for v in (
                                g.serious_affected,
                                g.serious_at_risk,
                                g.other_affected,
                                g.other_at_risk,
                                g.deaths_affected,
                                g.deaths_at_risk,
                            )
                        ),
                    ]
                )
    return [trials_path, outcomes_path, ae_path]
