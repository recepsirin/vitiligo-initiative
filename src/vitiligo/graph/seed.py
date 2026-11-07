"""Deterministic graph seeding from priors, trials, and the vitiligo anchor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, func, or_, select

from vitiligo.graph.normalize import VITILIGO_ENTITY_KEY, VITILIGO_ENTITY_NAME
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.logging import get_logger
from vitiligo.storage import Prior, PriorKind, Trial, session_scope
from vitiligo.storage.models import EntityKind, GraphEdge, GraphEntity, RelationKind
from vitiligo.trials.curated_results import records
from vitiligo.trials.relevance import is_vitiligo_trial

logger = get_logger(__name__)

_HIGH_CONFIDENCE_STAGES = frozenset({"PHASE_3", "PHASE_4", "APPROVAL"})
# A comparator that is nothing: tested in a trial, never a treatment.
CONTROL = re.compile(
    r"\b(?:placebos?|vehicles?|sham)\b|^(?:(?:normal\s+)?saline|control(?:\s+group)?|no\s+treatment)$",
    re.IGNORECASE,
)
# "NB-UVB twice weekly" and "NB-UVB thrice weekly" are one treatment given twice.
_SCHEDULE = re.compile(
    r"\s*,?\s*\b(?:once|twice|thrice|two times|three times|(?:\d+\s*-\s*)?\d+\s*times|daily|weekly|every)\b.*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GraphSeedStats:
    entities: int
    edges_inserted: int
    edges_merged: int
    edges_removed: int = 0


def seed_graph_from_structured_sources() -> GraphSeedStats:
    """Build the knowledge graph from priors and trials without LLM calls."""
    inserted = 0
    merged = 0
    with session_scope() as session:
        vitiligo = upsert_entity(
            session,
            kind=EntityKind.DISEASE,
            name=VITILIGO_ENTITY_NAME,
            external_ids={"efo": "EFO_0004208", "key": VITILIGO_ENTITY_KEY},
        )
        priors = list(session.exec(select(Prior)).all())
        # The trials table also holds trials kept for their drug -- ruxolitinib
        # in myelofibrosis -- and each would otherwise become a trial of vitiligo.
        trials = [t for t in session.exec(select(Trial)).all() if is_vitiligo_trial(t)]
        curated = _curated_interventions()

        for prior in priors:
            ins, mer = _seed_prior(session, prior, vitiligo)
            inserted += ins
            merged += mer

        for trial in trials:
            ins, mer = _seed_trial(session, trial, vitiligo, curated.get(trial.source_id, []))
            inserted += ins
            merged += mer

        removed = _drop_untrue_trial_claims(session, {_trial_ref(t) for t in trials})
        entities = int(session.exec(select(func.count()).select_from(GraphEntity)).one() or 0)

    logger.info(
        "Graph seed complete: entities=%d edges_inserted=%d edges_merged=%d edges_removed=%d",
        entities,
        inserted,
        merged,
        removed,
    )
    return GraphSeedStats(
        entities=entities, edges_inserted=inserted, edges_merged=merged, edges_removed=removed
    )


def _trial_ref(trial: Trial) -> str:
    """How a trial is cited in edge evidence: ``source:source_id``."""
    src = trial.source.value if hasattr(trial.source, "value") else str(trial.source)
    return f"{src}:{trial.source_id}"


def _curated_interventions() -> dict[str, list[dict[str, Any]]]:
    """What each curated trial's arms gave: agents, procedures and phototherapy.

    A trial known only from its paper lists no interventions in the trials
    table; ``curation/trial-results.jsonl`` records each arm as the paper
    describes it. Keyed by the trial's source id.
    """
    found: dict[str, list[dict[str, Any]]] = {}
    for record in records():
        items = [t for arm in record.get("arms") or [] for t in arm_treatments(arm)]
        found.setdefault(record["trial"].split(":", 1)[-1], []).extend(items)
    return found


def arm_treatments(arm: dict[str, Any]) -> list[dict[str, Any]]:
    """A curated arm's agents, procedure and phototherapy, each named once.

    "NB-UVB twice weekly" and "NBUVB" are both NB-UVB: the schedule is not
    part of the treatment's name.
    """
    items = [
        {"type": "DRUG", "name": c["agent"]} for c in arm.get("components") or [] if c.get("agent")
    ]
    for field in ("procedure", "phototherapy"):
        if arm.get(field):
            name = _SCHEDULE.sub("", str(arm[field])).strip()
            items.append({"type": field.upper(), "name": re.sub(r"\bNBUVB\b", "NB-UVB", name)})
    return items


def _drop_untrue_trial_claims(session: Session, kept: set[str]) -> int:
    """Take out what trials put into the graph that they do not show.

    An earlier seed read every row of the trials table, so trials held only for
    their drug became trials investigating vitiligo and their drugs became
    treatments for it; and every arm of a vitiligo trial became a treatment,
    its placebo and vehicle included. That evidence leaves every edge, an edge
    left with none is deleted, and so is the node of a trial that is not a
    vitiligo trial. Returns the edges deleted.
    """
    removed = 0
    controls = {
        e.id for e in session.exec(select(GraphEntity)).all() if CONTROL.search(e.name or "")
    }
    for edge in session.exec(select(GraphEdge)).all():
        evidence = list(edge.evidence or [])
        nothing = edge.predicate == RelationKind.TREATS and edge.subject_id in controls
        remaining = [
            e
            for e in evidence
            if e.get("source_type") != "trial" or (e.get("source_id") in kept and not nothing)
        ]
        if len(remaining) == len(evidence):
            continue
        if remaining:
            edge.evidence = remaining
            session.add(edge)
        else:
            session.delete(edge)
            removed += 1
    kept_ids = {ref.split(":", 1)[1] for ref in kept}
    stale = session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.TRIAL)).all()
    for entity in stale:
        if entity.name in kept_ids:
            continue
        touching = or_(GraphEdge.subject_id == entity.id, GraphEdge.object_id == entity.id)
        for edge in session.exec(select(GraphEdge).where(touching)).all():
            session.delete(edge)
            removed += 1
        session.delete(entity)
    session.flush()
    return removed


def _seed_prior(session: Session, prior: Prior, vitiligo: GraphEntity) -> tuple[int, int]:
    inserted = 0
    merged = 0
    src = prior.source.value if hasattr(prior.source, "value") else str(prior.source)
    external = {src: prior.source_id, "disease_id": prior.disease_id}

    if prior.kind == PriorKind.DRUG:
        drug = upsert_entity(
            session,
            kind=EntityKind.DRUG,
            name=prior.name,
            aliases=list(prior.synonyms or [])[:20],
            external_ids=external,
        )
        conf = 0.88 if (prior.clinical_stage or "") in _HIGH_CONFIDENCE_STAGES else 0.82
        _, ins = upsert_edge(
            session,
            subject=drug,
            predicate=RelationKind.TREATS,
            obj=vitiligo,
            confidence=conf,
            extraction_method="structured",
            evidence={
                "source_type": "prior",
                "source_id": f"{src}:{prior.source_id}",
                "clinical_stage": prior.clinical_stage,
            },
        )
        inserted += int(ins)
        merged += int(not ins)

        for mech in prior.mechanisms or []:
            action = str(mech.get("action_type") or "").upper()
            predicate = _action_to_predicate(action)
            for target in mech.get("targets") or []:
                target_name = target.get("symbol") or target.get("name") or target.get("id") or ""
                if not target_name:
                    continue
                target_entity = upsert_entity(
                    session,
                    kind=EntityKind.TARGET,
                    name=str(target_name),
                    external_ids={"ensembl": str(target.get("id") or "")},
                )
                _, ins = upsert_edge(
                    session,
                    subject=drug,
                    predicate=predicate,
                    obj=target_entity,
                    confidence=0.84,
                    extraction_method="structured",
                    evidence={
                        "source_type": "prior",
                        "source_id": f"{src}:{prior.source_id}",
                        "mechanism": mech.get("mechanism"),
                    },
                )
                inserted += int(ins)
                merged += int(not ins)
    else:
        target = upsert_entity(
            session,
            kind=EntityKind.TARGET,
            name=prior.name,
            aliases=[prior.description] if prior.description else [],
            external_ids=external,
        )
        score = prior.score if prior.score is not None else 0.5
        conf = min(0.95, 0.45 + float(score))
        _, ins = upsert_edge(
            session,
            subject=target,
            predicate=RelationKind.ASSOCIATED_WITH,
            obj=vitiligo,
            confidence=conf,
            extraction_method="structured",
            evidence={
                "source_type": "prior",
                "source_id": f"{src}:{prior.source_id}",
                "score": prior.score,
            },
        )
        inserted += int(ins)
        merged += int(not ins)

    return inserted, merged


def _seed_trial(
    session: Session, trial: Trial, vitiligo: GraphEntity, curated: list[dict[str, Any]]
) -> tuple[int, int]:
    inserted = 0
    merged = 0
    src = _trial_ref(trial).split(":", 1)[0]
    trial_title = trial.brief_title or trial.official_title or trial.source_id
    trial_entity = upsert_entity(
        session,
        kind=EntityKind.TRIAL,
        name=trial.source_id,
        aliases=[trial_title] if trial_title else [],
        external_ids={src: trial.source_id},
    )
    _, ins = upsert_edge(
        session,
        subject=trial_entity,
        predicate=RelationKind.INVESTIGATES,
        obj=vitiligo,
        confidence=0.78,
        extraction_method="structured",
        evidence={
            "source_type": "trial",
            "source_id": f"{src}:{trial.source_id}",
            "status": trial.status,
            "phases": trial.phases,
        },
    )
    inserted += int(ins)
    merged += int(not ins)

    # The registry's list when it has one; otherwise what the paper's arms gave.
    read_from = {} if trial.interventions else {"read_from": "curation/trial-results.jsonl"}
    for iv in trial.interventions or curated:
        name = (iv.get("name") or "").strip()
        if not name:
            continue
        kind = (
            EntityKind.DRUG
            if str(iv.get("type", "")).upper() == "DRUG"
            else EntityKind.INTERVENTION
        )
        intervention = upsert_entity(
            session,
            kind=kind,
            name=name,
            aliases=list(iv.get("other_names") or [])[:10],
        )
        _, ins = upsert_edge(
            session,
            subject=intervention,
            predicate=RelationKind.TESTED_IN,
            obj=trial_entity,
            confidence=0.8,
            extraction_method="structured",
            evidence={
                "source_type": "trial",
                "source_id": f"{src}:{trial.source_id}",
                "intervention_type": iv.get("type"),
                **read_from,
            },
        )
        inserted += int(ins)
        merged += int(not ins)
        if CONTROL.search(name):
            continue

        _, ins = upsert_edge(
            session,
            subject=intervention,
            predicate=RelationKind.TREATS,
            obj=vitiligo,
            confidence=0.68,
            extraction_method="structured",
            evidence={
                "source_type": "trial",
                "source_id": f"{src}:{trial.source_id}",
            },
        )
        inserted += int(ins)
        merged += int(not ins)

    return inserted, merged


def _action_to_predicate(action: str) -> RelationKind:
    if "INHIB" in action or action in {"ANTAGONIST", "BLOCKER"}:
        return RelationKind.INHIBITS
    if "AGON" in action or action in {"ACTIVATOR", "STIMULATOR"}:
        return RelationKind.ACTIVATES
    return RelationKind.TARGETS
