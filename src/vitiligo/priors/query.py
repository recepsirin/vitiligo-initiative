"""Structured queries over the `priors` table."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import desc, func
from sqlmodel import Session, select

from vitiligo.storage import Prior, PriorKind, PriorSourceKind, get_engine

DEFAULT_VITILIGO_EFO_ID = "EFO_0004208"

# Clinical stages that indicate meaningful drug development activity.
_HIGH_SIGNAL_STAGES: frozenset[str] = frozenset(
    {"PHASE_2", "PHASE_2_3", "PHASE_3", "PHASE_4", "APPROVAL"}
)


@dataclass(frozen=True)
class PriorStatsRow:
    label: str
    count: int


def list_drug_priors(
    disease_id: str = DEFAULT_VITILIGO_EFO_ID,
    sources: Iterable[PriorSourceKind] = (PriorSourceKind.OPENTARGETS,),
    limit: int = 50,
) -> list[Prior]:
    src_list = list(sources)
    with Session(get_engine(), expire_on_commit=False) as session:
        stmt = (
            select(Prior)
            .where(Prior.kind == PriorKind.DRUG)
            .where(Prior.disease_id == disease_id)
            .where(Prior.source.in_(src_list))  # type: ignore[attr-defined]
            .order_by(desc(Prior.clinical_stage), Prior.name)
            .limit(limit)
        )
        return list(session.exec(stmt))


def list_target_priors(
    disease_id: str = DEFAULT_VITILIGO_EFO_ID,
    sources: Iterable[PriorSourceKind] = (PriorSourceKind.OPENTARGETS,),
    limit: int = 30,
    min_score: float = 0.0,
) -> list[Prior]:
    src_list = list(sources)
    with Session(get_engine(), expire_on_commit=False) as session:
        stmt = (
            select(Prior)
            .where(Prior.kind == PriorKind.TARGET)
            .where(Prior.disease_id == disease_id)
            .where(Prior.source.in_(src_list))  # type: ignore[attr-defined]
            .where(Prior.score >= min_score)  # type: ignore[operator]
            .order_by(desc(Prior.score))
            .limit(limit)
        )
        return list(session.exec(stmt))


def retrieve_priors_for_hypothesize(
    disease_id: str = DEFAULT_VITILIGO_EFO_ID,
    drug_limit: int = 15,
    target_limit: int = 12,
) -> list[Prior]:
    """Return drug + target priors to inject into the Hypothesize prompt.

    Drugs are filtered to those with at least Phase 2 clinical activity
    (or approved drugs). Targets are the top-scoring associations.
    """
    drugs = list_drug_priors(disease_id=disease_id, limit=drug_limit * 3)
    high_signal_drugs = [
        d
        for d in drugs
        if (d.clinical_stage or "") in _HIGH_SIGNAL_STAGES
        or (d.clinical_stage or "").startswith("PHASE")
    ]
    selected_drugs = (high_signal_drugs or drugs)[:drug_limit]
    selected_targets = list_target_priors(
        disease_id=disease_id, limit=target_limit, min_score=0.25
    )
    return selected_drugs + selected_targets


def summarize_priors(
    disease_id: str = DEFAULT_VITILIGO_EFO_ID,
    sources: Iterable[PriorSourceKind] | None = None,
) -> dict[str, list[PriorStatsRow]]:
    src_list = list(sources) if sources is not None else list(PriorSourceKind)

    with Session(get_engine(), expire_on_commit=False) as session:
        total = int(
            session.exec(
                select(func.count())
                .select_from(Prior)
                .where(Prior.disease_id == disease_id)
                .where(Prior.source.in_(src_list))  # type: ignore[attr-defined]
            ).one()
            or 0
        )
        kind_rows = session.exec(
            select(Prior.kind, func.count())
            .where(Prior.disease_id == disease_id)
            .where(Prior.source.in_(src_list))  # type: ignore[attr-defined]
            .group_by(Prior.kind)
            .order_by(desc(func.count()))
        ).all()
        stage_rows = session.exec(
            select(Prior.clinical_stage, func.count())
            .where(Prior.kind == PriorKind.DRUG)
            .where(Prior.disease_id == disease_id)
            .where(Prior.source.in_(src_list))  # type: ignore[attr-defined]
            .group_by(Prior.clinical_stage)
            .order_by(desc(func.count()))
        ).all()

    return {
        "total": [PriorStatsRow(label="all", count=total)],
        "by_kind": [
            PriorStatsRow(
                label=str(kind.value if hasattr(kind, "value") else kind),
                count=int(count),
            )
            for kind, count in kind_rows
        ],
        "by_clinical_stage": [
            PriorStatsRow(label=str(stage or "UNKNOWN"), count=int(count))
            for stage, count in stage_rows
        ],
    }
