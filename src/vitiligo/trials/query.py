"""Structured queries over the `trials` table.

Trials are queried structurally rather than semantically: status, phase,
country, intervention name. A free-text term is matched against title,
summary, conditions, keywords, and intervention names with simple SQL `LIKE`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, desc, func, or_
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
        stmt = stmt.where(func.lower(cast(Trial.phases, String)).like(f'%"{filt.phase.lower()}"%'))
    if filt.country:
        stmt = stmt.where(
            func.lower(cast(Trial.countries, String)).like(f'%"{filt.country.lower()}"%')
        )
    if filt.query:
        stmt = stmt.where(_text_match(filt.query))
    return stmt


def _text_match(term: str) -> Any:
    """Case-insensitive substring match of ``term`` across the trial text fields."""
    like = f"%{term.lower()}%"
    return (
        (func.lower(func.coalesce(Trial.brief_title, "")).like(like))
        | (func.lower(func.coalesce(Trial.official_title, "")).like(like))
        | (func.lower(func.coalesce(Trial.summary, "")).like(like))
        | (func.lower(cast(Trial.conditions, String)).like(like))
        | (func.lower(cast(Trial.keywords, String)).like(like))
        | (func.lower(cast(Trial.interventions, String)).like(like))
    )


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


# Words that carry no discriminating signal when matching an intent against a
# vitiligo-only trial store ("vitiligo" itself matches every record).
_INTENT_STOPWORDS: frozenset[str] = frozenset(
    {
        "and",
        "are",
        "for",
        "from",
        "into",
        "the",
        "that",
        "this",
        "with",
        "vitiligo",
    }
)

# Upper bound on trials pulled for Python-side re-scoring of a multi-token intent.
_CANDIDATE_POOL_CAP = 1000


def _intent_tokens(intent: str) -> list[str]:
    """Split an intent into lowercase match tokens (hyphenated words stay whole)."""
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", intent.lower())
    return list(
        dict.fromkeys(tok for tok in tokens if len(tok) > 2 and tok not in _INTENT_STOPWORDS)
    )


# What a trial *tests* (titles, conditions, keywords, intervention names) counts
# fully; free prose (summary, intervention descriptions) often names other
# drugs as background, so a match there counts half.
_PRIMARY_FIELD_WEIGHT = 1.0
_PROSE_FIELD_WEIGHT = 0.5


def _trial_fields(trial: Trial) -> tuple[str, str]:
    """Return (primary text, prose text), lowercased, for intent scoring."""
    interventions = [iv for iv in trial.interventions or [] if isinstance(iv, dict)]
    primary = [
        trial.brief_title or "",
        trial.official_title or "",
        *(str(c) for c in trial.conditions or []),
        *(str(k) for k in trial.keywords or []),
        *(str(iv.get("name") or "") for iv in interventions),
        *(str(n) for iv in interventions for n in iv.get("other_names") or []),
    ]
    prose = [trial.summary or "", *(str(iv.get("description") or "") for iv in interventions)]
    return " \n ".join(primary).lower(), " \n ".join(prose).lower()


def _token_pattern(token: str) -> re.Pattern[str]:
    """Match ``token`` at a word start; hyphens also match a space or nothing.

    Word-start anchoring stops "active" matching "inactive" while still letting
    "inhibitor" match "inhibitors"; "non-segmental" also matches "nonsegmental".
    """
    body = r"[\s\-]?".join(re.escape(part) for part in token.split("-"))
    return re.compile(rf"(?<![a-z0-9]){body}")


def _token_like_variants(token: str) -> list[str]:
    """SQL LIKE terms covering the spellings ``_token_pattern`` accepts."""
    return list(dict.fromkeys([token, token.replace("-", ""), token.replace("-", " ")]))


def retrieve_relevant_trials(
    intent: str,
    limit: int = 15,
    require_high_signal: bool = True,
) -> list[Trial]:
    """Return trials most relevant to a research intent.

    Until trials are embedded, "relevance" is:
    - candidates: trials matching ANY intent token at a word start in title /
      summary / conditions / keywords / interventions (a multi-word intent is
      never matched as one literal phrase), then
    - quality filter: high-signal phase (>=Phase 2) OR reported results, then
    - ranking: intent tokens matched at word starts, each weighted by rarity
      across the candidate pool (smoothed IDF) and by field — titles,
      conditions, keywords and intervention names count fully; summary and
      intervention-description prose counts half — then phase/results bonus.

    An intent with no discriminating tokens (e.g. just "vitiligo") falls back
    to a literal match on the whole intent, newest first.
    """
    intent = (intent or "").strip()
    if not intent:
        return []

    intent_tokens = _intent_tokens(intent)
    if intent_tokens:
        with Session(get_engine(), expire_on_commit=False) as session:
            terms = [v for tok in intent_tokens for v in _token_like_variants(tok)]
            stmt = (
                select(Trial)
                .where(or_(*(_text_match(term) for term in terms)))
                .order_by(
                    desc(Trial.last_update_date),  # type: ignore[arg-type]
                    desc(Trial.id),  # type: ignore[arg-type]
                )
                .limit(_CANDIDATE_POOL_CAP)
            )
            candidates = list(session.exec(stmt))
    else:
        candidates = list_trials(
            TrialFilter(
                query=intent,
                sources=_ALL_SOURCES,
                limit=limit * 4 if limit else 60,
            )
        )

    # Per-token field weight for each trial: 1.0 if the token appears in a
    # primary field, 0.5 if only in prose, absent otherwise.
    patterns = {tok: _token_pattern(tok) for tok in intent_tokens}
    field_weights: dict[int, dict[str, float]] = {}
    for trial in candidates:
        primary, prose = _trial_fields(trial)
        hits: dict[str, float] = {}
        for tok, pattern in patterns.items():
            if pattern.search(primary):
                hits[tok] = _PRIMARY_FIELD_WEIGHT
            elif pattern.search(prose):
                hits[tok] = _PROSE_FIELD_WEIGHT
        field_weights[id(trial)] = hits

    if intent_tokens:
        # The SQL prefilter is a raw substring match (e.g. "active" in
        # "inactive"); keep only trials with a word-start match.
        candidates = [t for t in candidates if field_weights[id(t)]]

    # Rarity weights come from the whole candidate pool (before the quality
    # filter) so a specific term ("ruxolitinib") outweighs a common one
    # ("topical", "combination") — a smoothed inverse document frequency.
    pool_size = len(candidates)
    idf = {
        tok: math.log((pool_size + 1) / (sum(tok in hits for hits in field_weights.values()) + 1))
        + 1.0
        for tok in intent_tokens
    }

    if require_high_signal:
        filtered = [
            t
            for t in candidates
            if t.has_results or any(p in _HIGH_SIGNAL_PHASES for p in (t.phases or []))
        ]
        # If the high-signal filter wipes out all candidates, fall back to
        # the unfiltered list so the user always gets *something* back.
        candidates = filtered or candidates

    if not intent_tokens:
        return candidates[:limit]

    def score(trial: Trial) -> tuple[float, int, int]:
        hits = field_weights[id(trial)]
        relevance = round(sum(idf[tok] * weight for tok, weight in hits.items()), 9)
        phase_bonus = sum(1 for p in (trial.phases or []) if p in _HIGH_SIGNAL_PHASES)
        results_bonus = 1 if trial.has_results else 0
        return (relevance, phase_bonus + results_bonus, trial.id or 0)

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
                select(func.count()).select_from(Trial).where(Trial.source.in_(src_list))  # type: ignore[attr-defined]
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
