"""Structured queries over the `trials` table.

Trials are queried structurally rather than semantically: status, phase,
country, intervention name. A free-text term is matched against title,
summary, conditions, keywords, and intervention names with simple SQL `LIKE`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, desc, func
from sqlmodel import Session, select

from vitiligo.storage import Trial, TrialSourceKind, get_engine

_ALL_SOURCES: tuple[TrialSourceKind, ...] = tuple(TrialSourceKind)


@dataclass(frozen=True)
class TrialFilter:
    """Parameters for filtering the trials table."""

    query: str | None = None
    status: str | None = None  # e.g. RECRUITING, COMPLETED, AUTHORISED
    phase: str | None = None  # e.g. PHASE2
    country: str | None = None
    sources: tuple[TrialSourceKind, ...] = _ALL_SOURCES
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
            | (func.lower(cast(Trial.interventions, String)).like(like))
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


# Phases that lift a trial above pilot/early-stage, used as a quality
# filter when retrieving trials as evidence for hypothesis generation.
_HIGH_SIGNAL_PHASES: tuple[str, ...] = (
    "PHASE2",
    "PHASE3",
    "PHASE4",
    "PHASE2/PHASE3",
)


def retrieve_relevant_trials(
    intent: str,
    limit: int = 15,
    require_high_signal: bool = True,
) -> list[Trial]:
    """Return trials most relevant to a research intent.

    Until trials are embedded, "relevance" is the union of:
    - free-text term match in title / summary / conditions / interventions, AND
    - quality filter: high-signal phase (>=Phase 2) OR reported results.

    Trials are ordered by last update date so the most current evidence
    surfaces first.
    """
    intent = (intent or "").strip()
    if not intent:
        return []

    # Pull a generous candidate set; we re-score and trim in Python so we
    # can score by token overlap rather than relying solely on SQL LIKE.
    candidates = list_trials(
        TrialFilter(
            query=intent,
            sources=_ALL_SOURCES,
            limit=limit * 4 if limit else 60,
        )
    )

    if require_high_signal:
        filtered = [
            t
            for t in candidates
            if t.has_results
            or any(p in _HIGH_SIGNAL_PHASES for p in (t.phases or []))
        ]
        # If the high-signal filter wipes out all candidates, fall back to
        # the unfiltered list so the user always gets *something* back.
        candidates = filtered or candidates

    intent_tokens = {tok for tok in intent.lower().split() if len(tok) > 2}
    if not intent_tokens:
        return candidates[:limit]

    def score(trial: Trial) -> tuple[int, int, int]:
        haystack = " ".join(
            filter(
                None,
                [
                    (trial.brief_title or ""),
                    (trial.official_title or ""),
                    (trial.summary or ""),
                    " ".join(trial.conditions or []),
                    " ".join(trial.keywords or []),
                    " ".join(
                        (iv.get("name") or "") for iv in (trial.interventions or [])
                    ),
                ],
            )
        ).lower()
        token_overlap = sum(1 for tok in intent_tokens if tok in haystack)
        phase_bonus = sum(
            1 for p in (trial.phases or []) if p in _HIGH_SIGNAL_PHASES
        )
        results_bonus = 1 if trial.has_results else 0
        return (token_overlap, phase_bonus + results_bonus, trial.id or 0)

    candidates.sort(key=score, reverse=True)
    return candidates[:limit]


def summarize_trials(
    sources: Iterable[TrialSourceKind] | None = None,
) -> dict[str, list[TrialStatsRow]]:
    """Return high-level stats: total, by source, by status, by reported-results."""
    src_list = list(sources) if sources is not None else list(TrialSourceKind)

    with Session(get_engine(), expire_on_commit=False) as session:
        total = int(
            session.exec(
                select(func.count())
                .select_from(Trial)
                .where(Trial.source.in_(src_list))  # type: ignore[attr-defined]
            ).one()
            or 0
        )

        source_rows = session.exec(
            select(Trial.source, func.count())
            .where(Trial.source.in_(src_list))  # type: ignore[attr-defined]
            .group_by(Trial.source)
            .order_by(desc(func.count()))
        ).all()

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
        "by_source": [
            TrialStatsRow(
                label=str(src.value if hasattr(src, "value") else src),
                count=int(count),
            )
            for src, count in source_rows
        ],
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
