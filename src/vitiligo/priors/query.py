"""Structured queries over the `priors` table."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import case, desc, func
from sqlmodel import Session, select

from vitiligo.storage import Prior, PriorKind, PriorSourceKind, get_engine

DEFAULT_VITILIGO_EFO_ID = "EFO_0004208"

# Ordinal rank of clinical-stage labels (higher = further along). Stage strings
# must never be sorted lexically: "APPROVAL" < "PHASE_1" < "UNKNOWN" as text.
# Unlisted labels (UNKNOWN, WITHDRAWN, None) rank 0.
_STAGE_RANK: dict[str, int] = {
    "APPROVAL": 8,
    "PHASE_4": 7,
    "PHASE_3": 6,
    "PHASE_2_3": 5,
    "PHASE_2": 4,
    "PHASE_1_2": 3,
    "PHASE_1": 2,
    "EARLY_PHASE_1": 1,
}

# Drugs at or beyond this stage count as meaningful development activity.
_HIGH_SIGNAL_MIN_RANK = _STAGE_RANK["PHASE_2"]


def clinical_stage_rank(stage: str | None) -> int:
    """Return the ordinal rank of a clinical-stage label (0 when unknown)."""
    return _STAGE_RANK.get((stage or "").upper(), 0)


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
            .order_by(
                desc(case(_STAGE_RANK, value=Prior.clinical_stage, else_=0)),
                Prior.name,
            )
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
    Open Targets supplies clinical stage; DrugBank adds mechanism depth.
    """
    ot_drugs = list_drug_priors(
        disease_id=disease_id,
        sources=(PriorSourceKind.OPENTARGETS,),
        limit=drug_limit * 3,
    )
    db_drugs = list_drug_priors(
        disease_id=disease_id,
        sources=(PriorSourceKind.DRUGBANK,),
        limit=drug_limit * 2,
    )
    merged_drugs = _merge_drug_priors(ot_drugs, db_drugs, limit=drug_limit)

    ot_targets = list_target_priors(
        disease_id=disease_id,
        sources=(PriorSourceKind.OPENTARGETS,),
        limit=target_limit,
        min_score=0.25,
    )
    db_targets = list_target_priors(
        disease_id=disease_id,
        sources=(PriorSourceKind.DRUGBANK,),
        limit=target_limit,
        min_score=0.0,
    )
    merged_targets = _merge_target_priors(ot_targets, db_targets, limit=target_limit)
    return merged_drugs + merged_targets


def _normalize_prior_name(name: str) -> str:
    return name.upper().strip()


def _merge_drug_priors(
    primary: list[Prior],
    secondary: list[Prior],
    *,
    limit: int,
) -> list[Prior]:
    filtered_primary = [
        d for d in primary if clinical_stage_rank(d.clinical_stage) >= _HIGH_SIGNAL_MIN_RANK
    ] or primary
    seen = {_normalize_prior_name(d.name) for d in filtered_primary}
    merged = list(filtered_primary[:limit])
    for drug in secondary:
        key = _normalize_prior_name(drug.name)
        if key in seen:
            continue
        seen.add(key)
        merged.append(drug)
        if len(merged) >= limit:
            break
    return merged[:limit]


def _merge_target_priors(
    primary: list[Prior],
    secondary: list[Prior],
    *,
    limit: int,
) -> list[Prior]:
    seen = {t.source_id for t in primary}
    merged = list(primary[:limit])
    for target in sorted(secondary, key=lambda t: t.score or 0.0, reverse=True):
        if target.source_id in seen:
            continue
        seen.add(target.source_id)
        merged.append(target)
        if len(merged) >= limit:
            break
    return merged[:limit]


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
