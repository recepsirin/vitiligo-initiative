"""Who is funded to work on vitiligo now.

The roadmap's slowest items are not waiting on code or data. They wait on a
person: a clinician to review the JAK findings, a biostatistician to co-sign
the patient-level data request, a clinical lead for the maintenance trial.
Papers name people who finished something years ago. Active grants name
people doing the work today, at an institution, with money to do it.

Two cautions the summary keeps in view. A grant is a plan, so nothing here
says a treatment works. And RePORTER's search matches any mention, so a
melanoma project that cites vitiligo as an immune side effect comes back
too; ``is_vitiligo_centred`` keeps the ones actually about the disease.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from vitiligo.storage import ResearchProject

# A passing mention is not a vitiligo project. Either the title says so, or
# the body returns to it.
MIN_ABSTRACT_MENTIONS = 2


def is_vitiligo_centred(project: ResearchProject, term: str = "vitiligo") -> bool:
    """True when the project is about the disease, not merely mentioning it."""
    needle = term.lower()
    if needle in (project.title or "").lower():
        return True
    return (project.abstract or "").lower().count(needle) >= MIN_ABSTRACT_MENTIONS


@dataclass
class InvestigatorSummary:
    """One principal investigator's recent funding on the topic."""

    name: str
    organization: str | None
    state: str | None
    awards: int
    total_award: int
    has_active_award: bool
    latest_fiscal_year: int | None
    titles: list[str] = field(default_factory=list)
    project_urls: list[str] = field(default_factory=list)


def active_investigators(
    projects: Iterable[ResearchProject],
    *,
    since_fiscal_year: int,
    term: str = "vitiligo",
    limit: int | None = None,
) -> list[InvestigatorSummary]:
    """Investigators with topic-centred funding since ``since_fiscal_year``.

    Ranked by money, which is a proxy for how much of a group's work the topic
    occupies — not for the quality of that work.
    """
    grouped: dict[str, list[ResearchProject]] = {}
    for project in projects:
        if (project.fiscal_year or 0) < since_fiscal_year:
            continue
        if not is_vitiligo_centred(project, term):
            continue
        name = (project.contact_pi or "").strip()
        if not name:
            continue
        grouped.setdefault(name, []).append(project)

    summaries = [
        InvestigatorSummary(
            name=name,
            organization=next((p.organization for p in items if p.organization), None),
            state=next((p.org_state for p in items if p.org_state), None),
            awards=len(items),
            total_award=sum(p.award_amount or 0 for p in items),
            has_active_award=any(p.is_active for p in items),
            latest_fiscal_year=max((p.fiscal_year or 0) for p in items) or None,
            titles=sorted({p.title for p in items if p.title}),
            project_urls=sorted({p.project_url for p in items if p.project_url}),
        )
        for name, items in grouped.items()
    ]
    summaries.sort(key=lambda s: (-s.total_award, s.name))
    return summaries[:limit] if limit else summaries


def topic_counts(
    projects: Sequence[ResearchProject], terms: Sequence[str], *, since_fiscal_year: int
) -> dict[str, int]:
    """How many recent vitiligo-centred projects mention each term."""
    recent = [
        p for p in projects if (p.fiscal_year or 0) >= since_fiscal_year and is_vitiligo_centred(p)
    ]
    counts: dict[str, int] = {}
    for term in terms:
        needle = term.lower()
        counts[term] = sum(
            1 for p in recent if needle in f"{p.title or ''} {p.abstract or ''}".lower()
        )
    return counts
