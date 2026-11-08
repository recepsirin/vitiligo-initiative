"""What trials posted to ClinicalTrials.gov, as measured relations.

A registry's results section reports each group of participants under a title
of its own, not under the interventions it received: "CP-690,550 10 mg" is a
group given tofacitinib, and "Placebo (for Dupilumab)" one given placebo. A
group is read as the regimen it received from its title, matched against the
trial's own interventions and every name a curated drug goes by; its
description is read only when the title names nothing, because a description
names the drug a placebo stands in for. A group that names a control and a
drug and a switch between them, or that pools arms, is left out rather than
guessed.

Adverse events are read from every trial with posted results, since what a
drug does to people in rheumatoid arthritis it does in vitiligo; outcomes only
from vitiligo trials, since "response" in another disease is not
repigmentation. Each row carries the trial's control groups beside it, so a
rate is never read without what the comparator showed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from vitiligo.graph.evidence_seed import outcome_family
from vitiligo.graph.seed import CONTROL
from vitiligo.graph.store import replace_evidence, upsert_entity
from vitiligo.logging import get_logger
from vitiligo.reports.jak import JAK_AGENTS
from vitiligo.sources.mesh import MeshRecord
from vitiligo.storage import Trial
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEntity, RelationKind
from vitiligo.trials.relevance import is_vitiligo_trial

logger = get_logger(__name__)

# Reads the MeSH records of the identifiers asked for (``sources.mesh.load_index``).
MeshLoader = Callable[[set[str]], Mapping[str, MeshRecord]]

SOURCE = "posted_result"
_TYPE = re.compile(
    r"^(?:drug|biological|device|procedure|radiation|behavioral|other|combination product"
    r"|dietary supplement|genetic|diagnostic test)\s*:\s*",
    re.IGNORECASE,
)
_JOINS = frozenset({"and", "or", "with", "plus", "in", "of"})
_EITHER = re.compile(r"\bor\b", re.IGNORECASE)
_SWITCH = re.compile(r"\bto\b|->|→|\bthen\b|switch|re-?randomi", re.IGNORECASE)
_POOLED = re.compile(
    r"^(?:all|total|overall|pooled|combined|entire)\b"
    r"|\ball (?:participants|subjects|patients|treated|randomi[sz]ed)\b",
    re.IGNORECASE,
)
# Dose and form, so "Secukinumab 150mg" is found under "secukinumab". A number
# is a dose only with its unit: "LY3009104" and "CP-690,550" are names.
_DOSE = re.compile(
    r"\s*(?:\b\d[\d.,/]*\s*(?:%|mg/kg|mg|mcg|µg|g|ml|iu|units?)(?![a-z0-9])|\b(?:bid|qd|tid"
    r"|qod|once daily|twice daily|cream|ointment|gel|lotion|foam|solution|tablets?|capsules?"
    r"|injection|prefilled syringe|auto-?injector|oral|topical|s\.?c|i\.?v|po|im|q\d*w|qam|qpm"
    r"|daily|weekly|phosphate|citrate|hydrochloride|hcl|sodium|potassium|mesylate|sulfate)\b)",
    re.IGNORECASE,
)
# Kinds of intervention a drug name can be; a CO2 laser is not carbon dioxide.
_DRUG_TYPES = frozenset({"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT", "DIETARY_SUPPLEMENT"})
# Done to participants without being given to them.
_NOT_TREATMENT = re.compile(
    r"\b(?:analysis|questionnaire|survey|sampl|collection|assessment|biomarker|imaging"
    r"|pharmacological study|quality-of-life|laboratory|no intervention)",
    re.IGNORECASE,
)
# Two drugs set side by side or one after the other, not given together.
# Given together: background methotrexate, a double-dummy placebo.
_JOINED = re.compile(r"\+|\bplus\b|\band\b|\bwith\b|&", re.IGNORECASE)
_EXTENSION = re.compile(r"open[\s-]*label|extension", re.IGNORECASE)
# NB-UVB goes by many spellings, none of them the registry's.
_NBUVB = re.compile(r"narrow[\s-]*band[\s-]*(?:uvb|ultraviolet)|\bnb[\s-]*uvb", re.IGNORECASE)
_PERIOD = re.compile(r"placebo[\s-]+controlled", re.IGNORECASE)
# "Placebo + MTX and Tofacitinib 5mg + MTX": two arms in one group.
_TWO_ARMS = re.compile(r"\+.*\band\b.*\+", re.IGNORECASE)
_APART = re.compile(r"\bvs\.?(?![a-z])|\bversus\b|/", re.IGNORECASE)
_WITHHELD = re.compile(r"\bwith(?:hold|held)|\bdiscontinu|\binterrupt", re.IGNORECASE)


def _nothing(name: str) -> bool:
    """A placebo, a vehicle, or a drug withheld: nothing given."""
    return bool(CONTROL.search(name) or _WITHHELD.search(name))


@dataclass(frozen=True)
class Group:
    """What one results group received: a regimen, a control, or neither."""

    title: str
    regimen: tuple[EntityKind, str] | None = None
    control: bool = False


def _pattern(alias: str) -> re.Pattern[str] | None:
    parts = re.findall(r"[a-z0-9]+", alias.lower())
    if not parts or len("".join(parts)) < 4:
        return None
    body = r"[\s\-_,./()]*".join(re.escape(p) for p in parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])", re.IGNORECASE)


class Vocabulary:
    """Every name a curated drug goes by, mapped to the name of its node.

    Curated means the node carries a MeSH or Open Targets identifier, or is a
    JAK inhibitor of the atlas; a name a registry wrote is not a vocabulary.
    """

    def __init__(self, names: dict[str, set[str]]) -> None:
        pairs = [(alias, node) for node, aliases in names.items() for alias in {node, *aliases}]
        pairs.sort(key=lambda p: -len(p[0]))
        self._patterns = [(p, node) for alias, node in pairs if (p := _pattern(alias))]
        self.aliases = names

    @classmethod
    def load(cls, session: Session, mesh: MeshLoader | None = None) -> Vocabulary:
        """The curated drug nodes and their names, with MeSH's entry terms when
        ``mesh`` reads them: AIN457 and Cosentyx are secukinumab, CNTO 1275 and
        Stelara ustekinumab.
        """
        drugs = [
            entity
            for entity in session.exec(
                select(GraphEntity).where(GraphEntity.kind == EntityKind.DRUG)
            )
            if (entity.external_ids or {}).get("mesh")
            or (entity.external_ids or {}).get("opentargets")
        ]
        records = mesh({str((d.external_ids or {}).get("mesh")) for d in drugs}) if mesh else {}
        names: dict[str, set[str]] = {}
        for entity in drugs:
            names.setdefault(entity.name, set()).update(entity.aliases or [])
            record = records.get(str((entity.external_ids or {}).get("mesh")))
            # A substance's names, not a class's: MeSH's "Acids" lists "acid".
            if record is not None and (record.ui.startswith("C") or record.pharmacological_actions):
                names[entity.name].update(record.terms)
        held = {name.lower(): name for name in names}
        for agent in JAK_AGENTS:
            names.setdefault(held.get(agent.name.lower(), agent.name), set()).update(agent.aliases)
        return cls(names)

    def read(self, text: str) -> list[str]:
        """The drugs ``text`` names, when they are most of what it says.

        "Ruxolitinib 1.5% Phosphate Cream" is ruxolitinib, but "Withhold IS
        (MMF or MPA)" is not mycophenolic acid and "Flotetuzumab, after lead-in
        dose" is not lead: the names found must cover two thirds of its
        words, dose, form and salt aside.
        """
        if _EITHER.search(text):  # "etanercept or adalimumab" is neither
            return []
        rest = _DOSE.sub(" ", text)
        words = len([w for w in re.findall(r"[a-z0-9]+", rest.lower()) if w not in _JOINS])
        nodes: list[str] = []
        covered = 0
        for pattern, node in self._patterns:
            if (hit := pattern.search(rest)) is None:
                continue
            covered += len(re.findall(r"[a-z0-9]+", hit.group(0).lower()))
            rest = rest[: hit.start()] + " " + rest[hit.end() :]
            if node not in nodes:
                nodes.append(node)
        return sorted(nodes, key=str.lower) if words and covered * 3 >= words * 2 else []


def _intervention(
    iv: dict[str, Any], vocabulary: Vocabulary
) -> tuple[tuple[EntityKind, str], list[re.Pattern[str]]]:
    """The node an intervention is, and the patterns a group title names it by."""
    name = str(iv.get("name") or "")
    others = [str(n) for n in iv.get("otherNames") or []]
    if _nothing(name):  # "Placebo to match ruxolitinib" is not ruxolitinib
        return (EntityKind.INTERVENTION, name), [p for p in [_pattern(name)] if p]
    nodes: list[str] = []
    if str(iv.get("type") or "DRUG").upper() in _DRUG_TYPES:
        nodes = next((n for t in (name, *others) if (n := vocabulary.read(t))), [])
    aliases: set[str] = set()
    found: tuple[EntityKind, str]
    if len(nodes) == 1:
        found = (EntityKind.DRUG, nodes[0])
        aliases = {nodes[0], *vocabulary.aliases.get(nodes[0], set())}
    elif nodes:  # a product of two drugs, calcipotriene with betamethasone
        found = (EntityKind.INTERVENTION, " + ".join(nodes))
    else:
        kind = EntityKind.DRUG if str(iv.get("type")).upper() == "DRUG" else EntityKind.INTERVENTION
        found = (kind, name)
    aliases |= {name, _DOSE.sub("", name).strip(), *others}
    if _NBUVB.search(" ".join([name, *others])):
        aliases |= {"NB-UVB", "nbUVB", "narrowband UVB", "narrow-band UVB"}
    return found, [p for a in aliases if (p := _pattern(a))]


def resolve_groups(
    study: dict[str, Any], groups: Iterable[dict[str, Any]], vocabulary: Vocabulary
) -> dict[str, Group]:
    """Each results group of ``study`` by id, as the regimen it received."""
    module = (study.get("protocolSection") or {}).get("armsInterventionsModule") or {}
    ivs = [
        iv
        for iv in module.get("interventions") or []
        if str(iv.get("type")).upper() != "DIAGNOSTIC_TEST"
        and not _NOT_TREATMENT.search(str(iv.get("name")))
    ]
    read = [(iv, *_intervention(iv, vocabulary)) for iv in ivs]
    by_name = {str(iv.get("name")): (node, pats) for iv, node, pats in read}
    arms = {_words(a.get("label")): a for a in module.get("armGroups") or []}
    actives = {node for iv, node, _ in read if not _nothing(str(iv.get("name")))}
    has_control = any(_nothing(str(iv.get("name"))) for iv in ivs)

    def named(text: str) -> tuple[set[tuple[EntityKind, str]], bool]:
        nodes = {node for iv, node, pats in read if any(p.search(text) for p in pats)}
        active = {n for n in nodes if not _nothing(n[1])}
        # "Placebo-controlled period: DEUC 3 mg" names the period, not the arm.
        said = bool(CONTROL.search(_PERIOD.sub("", text)))
        return active, said or len(active) < len(nodes)

    resolved: dict[str, Group] = {}
    for group in groups:
        title = str(group.get("title") or "")
        arm = arms.get(_words(title))
        title_active, title_control = named(title)
        if arm is not None:
            listed = [
                by_name.get(_TYPE.sub("", str(n))) for n in arm.get("interventionNames") or []
            ]
            nodes = {hit[0] for hit in listed if hit}
            active = {n for n in nodes if not _nothing(n[1])}
            control = bool(nodes) and not active  # a double-dummy placebo is not the arm
            if title_control and not title_active and active:
                continue  # "Placebo", listing the drug given after week 12
        else:
            active, control = title_active, title_control
            # A description is read only where one treatment was on trial, and
            # only for it: it names background drugs, the drug a placebo
            # matched, and the placebo phase before a drug.
            if not active and not control and len(actives) == 1:
                active, control = named(str(group.get("description") or ""))
                if control:
                    active, control = set(), False
        if active and control:
            if (
                _SWITCH.search(title)
                or _APART.search(title)
                or _TWO_ARMS.search(title)
                or _EXTENSION.search(title)
            ):
                continue  # one after the other, side by side, or two arms as one
            if not _JOINED.search(title):
                active = set()  # "LEO 29102 Cream Vehicle" is the vehicle
        if len(active) > 1 and (_APART.search(title) or _SWITCH.search(title)):
            continue  # "Etanercept -> Ustekinumab": one after the other
        if control and not active and _EXTENSION.search(title):
            continue  # placebo, then the drug open label: no comparator
        if not active and not control and _POOLED.search(title) and len(actives) == 1:
            active = set(actives) if not has_control else set()
        resolved[str(group.get("id"))] = Group(title, _combined(active), control and not active)
    return resolved


def _combined(nodes: set[tuple[EntityKind, str]]) -> tuple[EntityKind, str] | None:
    if not nodes:
        return None
    if len(nodes) == 1:
        return next(iter(nodes))
    return EntityKind.INTERVENTION, " + ".join(sorted((n for _, n in nodes), key=str.lower))


def _words(text: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


Wanted = dict[tuple[int | None, int | None], tuple[GraphEntity, GraphEntity, list[Any]]]


class _Nodes:
    """Entities by kind and name, made on first use."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._held: dict[tuple[EntityKind, str], GraphEntity] = {}

    def __call__(self, kind: EntityKind, name: str) -> GraphEntity:
        key = (kind, name.lower())
        if key not in self._held:
            self._held[key] = upsert_entity(self.session, kind=kind, name=name)
        return self._held[key]


def _adverse_events(
    study: dict[str, Any], vocabulary: Vocabulary
) -> Iterator[tuple[tuple[EntityKind, str], str, dict[str, Any]]]:
    module = (study.get("resultsSection") or {}).get("adverseEventsModule") or {}
    groups = resolve_groups(study, module.get("eventGroups") or [], vocabulary)
    for serious, events in (
        (True, module.get("seriousEvents")),
        (False, module.get("otherEvents")),
    ):
        for event in events or []:
            stats = {str(s.get("groupId")): s for s in event.get("stats") or []}
            versus = [
                {"group": g.title, "affected": s.get("numAffected"), "at_risk": s.get("numAtRisk")}
                for gid, g in groups.items()
                if g.control and (s := stats.get(gid))
            ]
            for gid, s in stats.items():
                group = groups.get(gid)
                if group is None or group.regimen is None or not s.get("numAffected"):
                    continue
                row = {
                    "result_type": "adverse event",
                    "serious": serious,
                    "term": event.get("term"),
                    "organ_system": event.get("organSystem"),
                    "group": group.title,
                    "affected": s.get("numAffected"),
                    "at_risk": s.get("numAtRisk"),
                    "events": s.get("numEvents"),
                    "time_frame": module.get("timeFrame"),
                }
                if versus:
                    row["versus"] = versus
                yield group.regimen, str(event.get("term") or "").strip(), row


def _outcomes(
    study: dict[str, Any], vocabulary: Vocabulary
) -> Iterator[tuple[tuple[EntityKind, str], str, dict[str, Any]]]:
    module = (study.get("resultsSection") or {}).get("outcomeMeasuresModule") or {}
    for measure in module.get("outcomeMeasures") or []:
        groups = resolve_groups(study, measure.get("groups") or [], vocabulary)
        title = str(measure.get("title") or "")
        family = outcome_family({"outcome": title})
        common = {
            "outcome": title,
            "outcome_type": measure.get("type"),
            "time_frame": measure.get("timeFrame"),
            "param_type": measure.get("paramType"),
            "dispersion": measure.get("dispersionType"),
            "unit": measure.get("unitOfMeasure"),
        }
        denoms = _denoms(measure.get("denoms"))
        for cls in measure.get("classes") or []:
            n = _denoms(cls.get("denoms")) or denoms
            for category in cls.get("categories") or []:
                cells = {str(m.get("groupId")): m for m in category.get("measurements") or []}
                versus = [
                    {"group": g.title, "value": m.get("value"), "n": n.get(gid)}
                    for gid, g in groups.items()
                    if g.control and (m := cells.get(gid))
                ]
                for gid, m in cells.items():
                    group = groups.get(gid)
                    if group is None or group.regimen is None or m.get("value") is None:
                        continue
                    row = {
                        "result_type": "outcome",
                        **common,
                        "class": cls.get("title"),
                        "category": category.get("title"),
                        "group": group.title,
                        "value": m.get("value"),
                        "spread": m.get("spread"),
                        "lower": m.get("lowerLimit"),
                        "upper": m.get("upperLimit"),
                        "n": n.get(gid),
                    }
                    if versus:
                        row["versus"] = versus
                    yield group.regimen, family, {k: v for k, v in row.items() if v is not None}
        for analysis in measure.get("analyses") or []:
            ids = [str(i) for i in analysis.get("groupIds") or []]
            named = [groups[i] for i in ids if i in groups]
            if len(named) != len(ids):
                continue
            row = {
                "result_type": "comparison",
                **common,
                "groups": [g.title for g in named],
                "p": analysis.get("pValue"),
                "method": analysis.get("statisticalMethod"),
                "estimate": analysis.get("paramType"),
                "estimate_value": analysis.get("paramValue"),
                "ci_low": analysis.get("ciLowerLimit"),
                "ci_high": analysis.get("ciUpperLimit"),
            }
            row = {k: v for k, v in row.items() if v is not None}
            for group in named:
                if group.regimen is not None:
                    yield group.regimen, family, row


def _denoms(denoms: list[dict[str, Any]] | None) -> dict[str, Any]:
    for denom in denoms or []:
        if str(denom.get("units") or "").lower() in {"participants", ""}:
            return {str(c.get("groupId")): c.get("value") for c in denom.get("counts") or []}
    return {}


def seed_posted_results(
    session: Session, trials: Iterable[Trial], mesh: MeshLoader | None = None
) -> tuple[int, int]:
    """Regimen-outcome and regimen-adverse-event edges from posted results.

    Returns the edges inserted and the evidence rows written.
    """
    vocabulary = Vocabulary.load(session, mesh)
    nodes = _Nodes(session)
    wanted: Wanted = {}
    rows = 0
    for trial in trials:
        study = (trial.raw_metadata or {}).get("study") or {}
        if not study.get("resultsSection"):
            continue
        source = f"{trial.source.value}:{trial.source_id}"
        found = [
            (r, EntityKind.DISEASE, t, row) for r, t, row in _adverse_events(study, vocabulary)
        ]
        if is_vitiligo_trial(trial):
            found += [(r, EntityKind.OUTCOME, f, row) for r, f, row in _outcomes(study, vocabulary)]
        for regimen, kind, target, row in found:
            if not target:
                continue
            subject, obj = nodes(*regimen), nodes(kind, target)
            entry = wanted.setdefault((subject.id, obj.id), (subject, obj, []))
            entry[2].append({"source_type": SOURCE, "source_id": source, **row})
            rows += 1
    inserted, removed = replace_evidence(
        session,
        SOURCE,
        wanted,
        predicate=RelationKind.CHANGES,
        extraction_method=SOURCE,
        confidence=0.9,
        claim=ClaimKind.OBSERVED,
        causal_level="perturbation_in_human",
    )
    logger.info(
        "Posted results: %d rows on %d edges, %d inserted, %d removed",
        rows,
        len(wanted),
        inserted,
        removed,
    )
    return inserted, rows
