"""The vitiligo trials with readable results that are not JAK trials.

``jak.py`` builds an atlas of JAK-inhibitor trials, and everything downstream
of it — the arm table, the clinician's evidence table, the scenario model —
inherited that scope. It is a reasonable scope for a model of one drug class
and a poor one for a clinician, because it means the engine says nothing
about the treatments most people with vitiligo are actually given.

Of 1,072 registered vitiligo trials, fifteen report a responder rate that can
be read from the record, and nine of those are JAK. This module is the other
side of that list: the trials with real numbers that the JAK vocabulary does
not match.

Two things shape it.

**It builds records, not an atlas.** ``build_jak_atlas`` ranks and summarises
by the JAK agent order, which has no meaning here. ``_build_record`` does not;
it takes the agents as an argument. So these records are assembled directly
and handed to ``arm_rows``, the same function the JAK atlas uses, and come out
as the same ``ArmEndpointRow`` with the same denominators and flags.

**Nothing here reaches the scenario model, by construction.** The model's
callers build their rows from ``build_jak_atlas`` alone, which this module
does not touch. That matters because AMG 714 reports F-VASI and T-VASI at
thresholds, so its rows would otherwise be eligible for a fit whose
pre-registration describes a JAK-only dataset. Keeping the two apart at the
call site is safer than filtering them apart afterwards.

The trials are named explicitly rather than discovered. Fourteen is a list
that can be read and checked; a rule that selected them would be a rule
nobody could audit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlmodel import Session, select

from vitiligo.logging import get_logger
from vitiligo.reports.jak import JakTrial, _build_record, _link_registry_records
from vitiligo.reports.jak_arms import ArmEndpointRow, arm_rows
from vitiligo.storage import Trial, get_engine

logger = get_logger(__name__)


@dataclass(frozen=True)
class NonJakTrial:
    """A trial outside the JAK class whose posted results can be read."""

    source_id: str
    agent: str
    mechanism: str
    route: str | None = None
    dose_value: float | None = None
    dose_unit: str | None = None
    frequency: str | None = None
    note: str = ""


# Every non-JAK vitiligo trial found to post a responder rate against a
# threshold. Two others post responder counts and are deliberately absent:
# NCT01517893 counts "participants with a decrease in VASI", and
# NCT04374435 "patients who had a percent change in body surface area".
# Neither names a threshold, so neither is comparable with an F-VASI50, and
# putting them in the same table would invite exactly that comparison.
NON_JAK_TRIALS: tuple[NonJakTrial, ...] = (
    NonJakTrial(
        "NCT04338581",
        "AMG 714",
        "anti-IL-15",
        route="subcutaneous",
        dose_value=300.0,
        dose_unit="mg",
        frequency="Q2W",
        note=(
            "ITN086AI, phase 2a, completed. The only placebo-controlled responder "
            "data in the corpus for a mechanism other than JAK inhibition, and it "
            "runs to week 48. F-VASI and T-VASI at 25, 35, 50, 75 and 90."
        ),
    ),
)

_BY_ID = {t.source_id: t for t in NON_JAK_TRIALS}


def build_non_jak_records() -> list[JakTrial]:
    """Atlas records for the named non-JAK trials, in the order listed."""
    wanted = [t.source_id for t in NON_JAK_TRIALS]
    with Session(get_engine(), expire_on_commit=False) as session:
        trials = list(session.exec(select(Trial).where(Trial.source_id.in_(wanted))))  # type: ignore[attr-defined]

    found = {t.source_id: t for t in trials}
    missing = [sid for sid in wanted if sid not in found]
    if missing:
        logger.warning("Non-JAK trials absent from the corpus: %s", ", ".join(missing))

    study_ids = _link_registry_records(trials)
    records: list[JakTrial] = []
    for source_id in wanted:
        trial = found.get(source_id)
        if trial is None:
            continue
        records.append(
            _build_record(
                trial,
                agents=[_BY_ID[source_id].agent],
                match_basis="named_non_jak",
                study_id=study_ids.get(source_id, source_id),
                linked=[],
                cites={},
                pmid_titles={},
            )
        )
    return records


def non_jak_arm_rows() -> list[ArmEndpointRow]:
    """Responder rows from the non-JAK trials, shaped like every other row.

    The regimen is applied from the table above rather than parsed from the
    arm label. ``parse_arm`` reads a dose out of labels like "Ruxolitinib
    Cream 1.5% BID"; this trial labels its arms "AMG 714" and "Placebo", and
    puts "300 mg AMG 714 subcutaneously every 2 weeks" in the description,
    where nothing reads it. Three fields stated once here is more auditable
    than a parser for one trial's prose.
    """
    rows = arm_rows(build_non_jak_records())
    out: list[ArmEndpointRow] = []
    for row in rows:
        spec = _BY_ID.get(row.source_id)
        if spec is None or row.arm_role != "active":
            out.append(row)
            continue
        out.append(
            replace(
                row,
                arm_agent=spec.agent,
                route=spec.route,
                dose_value=spec.dose_value,
                dose_unit=spec.dose_unit,
                frequency=spec.frequency,
            )
        )
    return out
