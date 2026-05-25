"""Structured queries over the `trials` table.

Trials are queried structurally rather than semantically: status, phase,
country, intervention name. A free-text term is matched against title,
summary, and conditions with simple SQL `LIKE`. This is honest about what
the data is — operational metadata, not narrative — and avoids pretending
embeddings are doing useful retrieval where they aren't.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, desc, func
from sqlmodel import Session, select

from vitiligo.storage import Trial, TrialSourceKind, get_engine


@dataclass(frozen=True)
class TrialFilter:
    """Parameters for filtering the trials table."""

    query: str | None = None
    status: str | None = None  # e.g. RECRUITING, COMPLETED
    phase: str | None = None  # e.g. PHASE2
    country: str | None = None
    sources: tuple[TrialSourceKind, ...] = (TrialSourceKind.CTGOV,)
    has_results: bool | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class TrialStatsRow:
    label: str
    count: int


def _apply_filter(stmt: Any, filt: TrialFilter) -> Any:
    if filt.sources:
        stmt = stmt.where(Trial.source.in_(list(filt.sources)))  # type: ignore[attr-defined]
    if filt.status:
        stmt = stmt.where(func.upper(Trial.status) == filt.status.upper())
    if filt.has_results is not None:
        stmt = stmt.where(Trial.has_results.is_(filt.has_results))  # type: ignore[attr-defined]
    if filt.phase:
        # phases / countries / conditions / keywords are JSON lists; in SQLite
        # they're stored as JSON strings, so a case-insensitive LIKE on the
        # serialized form is correct and adequately fast at this scale.
        stmt = stmt.where(
            func.lower(cast(Trial.phases, String)).like(f'%"{filt.phase.lower()}"%')
        )
    if filt.country:
        stmt = stmt.where(
            func.lower(cast(Trial.countries, String)).like(f'%"{filt.country.lower()}"%')
        )
    if filt.query:
        like = f"%{filt.query.lower()}%"
        stmt = stmt.where(
            (func.lower(func.coalesce(Trial.brief_title, "")).like(like))
            | (func.lower(func.coalesce(Trial.official_title, "")).like(like))
            | (func.lower(func.coalesce(Trial.summary, "")).like(like))
            | (func.lower(cast(Trial.conditions, String)).like(like))
            | (func.lower(cast(Trial.keywords, String)).like(like))
        )
    return stmt


def list_trials(filt: TrialFilter) -> list[Trial]:
    """Return trials matching `filt`, newest-first."""
    with Session(get_engine(), expire_on_commit=False) as session:
        stmt = select(Trial)
        stmt = _apply_filter(stmt, filt)
        stmt = stmt.order_by(
            desc(Trial.last_update_date),  # type: ignore[arg-type]
            desc(Trial.id),  # type: ignore[arg-type]
        )
        stmt = stmt.offset(filt.offset).limit(filt.limit)
        return list(session.exec(stmt))


def count_trials(filt: TrialFilter) -> int:
    with Session(get_engine(), expire_on_commit=False) as session:
        stmt = select(func.count()).select_from(Trial)
        stmt = _apply_filter(stmt, filt)
        return int(session.exec(stmt).one() or 0)


def summarize_trials(
    sources: Iterable[TrialSourceKind] = (TrialSourceKind.CTGOV,),
) -> dict[str, list[TrialStatsRow]]:
    """Return high-level stats: total, by status, by phase, by country."""
    src_list = list(sources)

    with Session(get_engine(), expire_on_commit=False) as session:
        total = int(
            session.exec(
                select(func.count())
                .select_from(Trial)
                .where(Trial.source.in_(src_list))  # type: ignore[attr-defined]
            ).one()
            or 0
        )

        status_rows = session.exec(
            select(Trial.status, func.count())
            .where(Trial.source.in_(src_list))  # type: ignore[attr-defined]
            .group_by(Trial.status)
            .order_by(desc(func.count()))
        ).all()

        results_rows = session.exec(
            select(Trial.has_results, func.count())
            .where(Trial.source.in_(src_list))  # type: ignore[attr-defined]
            .group_by(Trial.has_results)  # type: ignore[arg-type]
            .order_by(desc(func.count()))
        ).all()

    return {
        "total": [TrialStatsRow(label="all", count=total)],
        "by_status": [
            TrialStatsRow(label=str(status or "UNKNOWN"), count=int(count))
            for status, count in status_rows
        ],
        "by_results": [
            TrialStatsRow(
                label="has_results=true" if bool(flag) else "has_results=false",
                count=int(count),
            )
            for flag, count in results_rows
        ],
    }
