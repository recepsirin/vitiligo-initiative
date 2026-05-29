"""Deterministic graph seeding from priors, trials, and the vitiligo anchor."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, func, select

from vitiligo.graph.normalize import VITILIGO_ENTITY_KEY, VITILIGO_ENTITY_NAME
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.logging import get_logger
from vitiligo.storage import Prior, PriorKind, Trial, session_scope
from vitiligo.storage.models import EntityKind, GraphEntity, RelationKind

logger = get_logger(__name__)

_HIGH_CONFIDENCE_STAGES = frozenset({"PHASE_3", "PHASE_4", "APPROVAL"})


@dataclass(frozen=True)
class GraphSeedStats:
    entities: int
    edges_inserted: int
    edges_merged: int


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
        trials = list(session.exec(select(Trial)).all())

        for prior in priors:
            ins, mer = _seed_prior(session, prior, vitiligo)
            inserted += ins
            merged += mer

        for trial in trials:
            ins, mer = _seed_trial(session, trial, vitiligo)
            inserted += ins
            merged += mer

        entities = int(session.exec(select(func.count()).select_from(GraphEntity)).one() or 0)

    logger.info(
        "Graph seed complete: entities=%d edges_inserted=%d edges_merged=%d",
        entities,
        inserted,
        merged,
    )
    return GraphSeedStats(entities=entities, edges_inserted=inserted, edges_merged=merged)


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


def _seed_trial(session: Session, trial: Trial, vitiligo: GraphEntity) -> tuple[int, int]:
    inserted = 0
    merged = 0
    src = trial.source.value if hasattr(trial.source, "value") else str(trial.source)
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

    for iv in trial.interventions or []:
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
            },
        )
        inserted += int(ins)
        merged += int(not ins)

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
