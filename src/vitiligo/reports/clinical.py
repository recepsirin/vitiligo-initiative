"""Posted trial results, arranged the way a clinician reads them.

The arm table holds every reported responder rate by arm, endpoint and week —
830 rows, and most of them should never be shown to someone deciding whether
to prescribe. A clinician asks two questions: what happened by six months
against a comparator, and does it hold for a year. This answers both, and
keeps them apart.

**Week 24 against the concurrent control.** Week 24 is the primary endpoint of
every registered JAK trial in vitiligo, so reporting that week — rather than
whatever week each trial last reported — is what makes two drugs comparable.
The comparator comes from the same trial, endpoint and week, or none is shown.

**Later weeks are a continuation, never a column beside the controlled one.**
In TRuE-V both arms receive ruxolitinib after week 24, so the week-52 numbers
describe one group on drug with nobody to compare against, and 177 of the 222
who started. Shown as such, with its denominator, under the week-24 row.

Five rules, because each one was violated by a number this file used to print:

- **The largest arm wins, not the latest week or the highest rate.** Ranking by
  rate let NCT05247489's seven patients (85.7% F-VASI75) outrank TRuE-V2's 222
  (30.9%); ranking by week let week 156 of a four-patient tail outrank week 24.
- **An arm must still be the group that was randomised.** NCT03099304 reads
  45.5% of 33 at week 24 and 100% of 9 at week 156: the rate climbs because the
  denominator collapses. Those rows carry no flag, so the guard is the
  denominator itself, plus the design annotation the model already records.
- **Central reads beat local ones.** Where a trial reports both, the blinded
  central read is lower — 7.0% against 18.4% for ritlecitinib 10 mg — and it is
  the one that counts.
- **Face and body stay apart**, and phototherapy is a different intervention.
  F-VASI is facial, T-VASI whole-body, and ruxolitinib with NB-UVB (76.5%) is
  not ruxolitinib (51.2%).
- **A figure that counts only those assessed is bracketed, not taken at face
  value.** TRuE-V2's 48.0% of 177 is the most favourable reading of that arm;
  over the 222 it had at week 24 the answer is somewhere in 38.3% to 58.6%,
  and nothing in the record narrows it. The continuation column reports the
  bracket, because the gap is the price of the missing data and a clinician
  should see it rather than a single number chosen from one end.
- **Every row says which patients it counted.** The trials differ: most report
  those assessed at the visit, two impute missing results as failures, and
  TRuE-V imputes at week 24 and does not at week 52. A rate means a different
  thing under each, so the page states which rather than dropping the rows it
  cannot harmonise — the model excludes what it cannot combine arithmetically,
  but a reader who can see both denominators can judge, and hiding ritlecitinib
  entirely would say less than labelling it. Only a subgroup is dropped here,
  because a subgroup is not the arm that was randomised.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from vitiligo.reports.bounds import Bounds, bound_rate
from vitiligo.reports.jak_arms import SUBGROUP, ArmEndpointRow

# A drug, as it was given, at one endpoint: agent, route, maintenance dose,
# loading dose, phototherapy, endpoint. Two rows share a cell when a clinician
# would compare them directly. The loading dose belongs in it: ritlecitinib
# 50 mg QD was given three ways in NCT03715829 — plain, after 100 mg for four
# weeks, and after 200 mg — reaching 7.7%, 8.5% and 12.1% F-VASI75. The 200 mg
# arm is the one phase 3 carried forward, and merging the three reports whichever
# happened to enrol one patient more.
Cell = tuple[str, str, str, float | None, bool, str]

# The primary endpoint week of every registered JAK trial in vitiligo, and so
# the only week at which their results can be set beside one another.
PRIMARY_WEEK = 24

# Below this, the confidence interval on a proportion is wider than the effect
# being reported. NCT05247489's seven-patient arm reads 100% at F-VASI50.
MIN_ANALYSED = 20

# An arm reporting materially fewer patients than it randomised is reporting
# the ones who stayed, who are the ones still responding.
MIN_RETENTION = 0.8

# How each analysis population is worth describing to a clinician. The registry
# states it statistically; this says what was counted.
POPULATION_NOTES = {
    "as_observed": "counts only patients assessed at that visit",
    "nri": "patients who left the trial counted as not responding",
    "multiple_imputation": "missing results estimated from the rest of the data",
}

# Rows the model also refuses: arms re-assigned partway through, and separate
# extension studies. ``extension_period`` is the same trial's open-label
# continuation — excluded from the controlled table, then reported on its own.
CONTINUATION_FLAG = "extension_period"
_EXCLUDED_FLAGS = frozenset({"treatment_changes_within_arm", "extension_study", CONTINUATION_FLAG})


@dataclass(frozen=True)
class Replication:
    """Another trial reporting the same drug, dose and endpoint at week 24."""

    trial: str
    percent: float
    analysed: int
    control_percent: float | None


@dataclass(frozen=True)
class Continuation:
    """The same arm after the controlled period ended, with nobody to compare."""

    week: int
    percent: float
    responders: int
    analysed: int
    started: int
    population: str | None
    population_note: str | None

    @property
    def retention(self) -> float | None:
        """Share of the group that started still being counted."""
        return None if not self.started else round(self.analysed / self.started, 3)

    @property
    def bounds(self) -> Bounds | None:
        """What the rate could be over the group the arm started with.

        A continuation figure counting only the patients assessed is the most
        favourable reading of that arm, not a neutral one. Where the trial also
        states how many it had at the controlled endpoint, the two together
        bracket the answer without assuming anything about who left.
        """
        return bound_rate(self.responders, self.analysed, self.started)


@dataclass(frozen=True)
class EvidenceRow:
    """One drug and dose at one endpoint at week 24, with its control."""

    agent: str
    route: str | None
    dose: str | None
    loading_dose: float | None
    phototherapy: bool
    endpoint: str
    region: str
    week: int
    responders: int
    analysed: int
    percent: float
    control_percent: float | None
    control_analysed: int | None
    assessor: str | None
    primary_endpoint: bool
    trial: str
    trial_title: str | None
    population: str | None
    population_note: str | None
    later: Continuation | None
    also_reported: list[Replication]

    @property
    def difference(self) -> float | None:
        """Percentage points over the control arm, where one exists."""
        return (
            None if self.control_percent is None else round(self.percent - self.control_percent, 1)
        )

    @property
    def controlled(self) -> bool:
        """Whether a comparator arm from the same trial and week was reported."""
        return self.control_percent is not None


def _population(row: ArmEndpointRow) -> str | None:
    """Which patients the row's figure counted, as the registry stated it."""
    for flag in row.flags:
        if flag.startswith("population:"):
            return flag.split(":", 1)[1]
    return None


def _control_percent(control: ArmEndpointRow | None) -> float | None:
    return None if control is None else round(float(control.percent or 0), 1)


def _design_caps() -> dict[str, int]:
    """Trials whose later arms the model records as post-randomisation subsets."""
    from vitiligo.models.jak_mbma import DESIGN_ANNOTATIONS

    return {t: int(a["max_week"]) for t, a in DESIGN_ANNOTATIONS.items()}


def _central_reads(rows: Sequence[ArmEndpointRow]) -> set[tuple[str, str]]:
    """Trial and instrument pairs for which a blinded central read exists."""
    return {(r.source_id, r.instrument) for r in rows if r.assessor == "central"}


def _reported(row: ArmEndpointRow) -> bool:
    """Whether the row carries the numbers needed to state a rate."""
    return not (
        row.week is None
        or row.threshold is None
        or row.percent is None
        or row.responders is None
        or not row.n_analyzed
    )


def _usable(
    row: ArmEndpointRow,
    central: set[tuple[str, str]],
    caps: dict[str, int],
    *,
    allow: frozenset[str] = frozenset(),
) -> bool:
    """Whether a row may be shown at all, whatever week it reports."""
    if not _reported(row) or row.instrument not in ("F-VASI", "T-VASI"):
        return False
    assert row.week is not None
    if (_EXCLUDED_FLAGS - allow).intersection(row.flags):
        return False
    # A subgroup is not the randomised arm, whatever rate it reports.
    if _population(row) == SUBGROUP:
        return False
    if (row.source_id, row.instrument) in central and row.assessor != "central":
        return False
    cap = caps.get(row.source_id)
    if cap is not None and row.week > cap and "from_publication" not in row.flags:
        return False
    return int(row.n_analyzed or 0) >= MIN_ANALYSED


def _dose(row: ArmEndpointRow) -> str | None:
    if row.dose_value is None:
        return None
    unit = row.dose_unit or ""
    frequency = f" {row.frequency}" if row.frequency else ""
    return f"{row.dose_value:g}{unit}{frequency}".strip()


def _cell(row: ArmEndpointRow) -> Cell:
    """The drug, as given, at one endpoint: what a clinician compares."""
    return (
        (row.arm_agent or "").lower(),
        row.route or "",
        _dose(row) or "",
        row.loading_dose_value,
        bool(row.phototherapy),
        row.endpoint,
    )


def _better(row: ArmEndpointRow, held: ArmEndpointRow | None) -> bool:
    """Whether ``row`` is the firmer of two reports of the same cell.

    Size first: the largest arm is the one whose rate is worth stating. Then
    the registry's primary endpoint, then a central read.
    """
    if held is None:
        return True
    mine = (
        int(row.n_analyzed or 0),
        row.outcome_type == "PRIMARY",
        row.assessor == "central",
    )
    theirs = (
        int(held.n_analyzed or 0),
        held.outcome_type == "PRIMARY",
        held.assessor == "central",
    )
    return mine > theirs


def build_evidence_rows(rows: Sequence[ArmEndpointRow]) -> list[EvidenceRow]:
    """One row per drug, dose and endpoint at week 24, with its control."""
    caps = _design_caps()
    central = _central_reads(rows)

    def ok(row: ArmEndpointRow, *, allow: frozenset[str] = frozenset()) -> bool:
        return _usable(row, central, caps, allow=allow)

    # The largest group each arm ever reported at an endpoint, to catch an arm
    # that is no longer reporting the group it enrolled. Central and local reads
    # are separate measurement sets, not attrition from one another: pooling
    # them made ritlecitinib's central read of 52 look like a loss from the
    # local read of 67, and dropped the arm.
    def series(row: ArmEndpointRow) -> tuple[str, str, str, str | None]:
        return (row.source_id, row.arm_label, row.endpoint, row.assessor)

    peak: dict[tuple[str, str, str, str | None], int] = {}
    for row in rows:
        if _reported(row):
            peak[series(row)] = max(peak.get(series(row), 0), int(row.n_analyzed or 0))

    def retained(row: ArmEndpointRow) -> bool:
        started = peak.get(series(row), 0)
        return not started or int(row.n_analyzed or 0) >= started * MIN_RETENTION

    controls: dict[tuple[str, str], ArmEndpointRow] = {}
    for row in rows:
        if row.arm_role == "placebo" and row.week == PRIMARY_WEEK and ok(row):
            trial_endpoint = (row.source_id, row.endpoint)
            if _better(row, controls.get(trial_endpoint)):
                controls[trial_endpoint] = row

    # Every eligible report of a cell, best first. Two pivotal trials agreeing is
    # stronger than one: TRuE-V1 read 29.8% of 221 and TRuE-V2 30.9% of 222, and
    # showing only the larger would hide the replication.
    eligible: dict[Cell, dict[str, ArmEndpointRow]] = {}
    for row in rows:
        if row.arm_role != "active" or not row.arm_agent or row.week != PRIMARY_WEEK:
            continue
        if not ok(row) or not retained(row):
            continue
        per_trial = eligible.setdefault(_cell(row), {})
        if _better(row, per_trial.get(row.source_id)):
            per_trial[row.source_id] = row

    best: dict[Cell, ArmEndpointRow] = {}
    for cell, per_trial in eligible.items():
        winner = None
        for row in per_trial.values():
            if _better(row, winner):
                winner = row
        assert winner is not None
        best[cell] = winner

    # The open-label continuation of a chosen arm, from the same trial, so its
    # denominator can be read against the group that was randomised.
    allow_continuation = frozenset({CONTINUATION_FLAG})
    later: dict[Cell, ArmEndpointRow] = {}
    for row in rows:
        if row.arm_role != "active" or not row.arm_agent or (row.week or 0) <= PRIMARY_WEEK:
            continue
        if CONTINUATION_FLAG not in row.flags or not ok(row, allow=allow_continuation):
            continue
        cell = _cell(row)
        chosen = best.get(cell)
        if chosen is None or row.source_id != chosen.source_id:
            continue
        held = later.get(cell)
        if held is None or (row.week or 0) > (held.week or 0):
            later[cell] = row

    out: list[EvidenceRow] = []
    for cell, row in best.items():
        assert row.week is not None
        control = controls.get((row.source_id, row.endpoint))
        tail = later.get(cell)
        others = [
            other for trial, other in sorted(eligible[cell].items()) if trial != row.source_id
        ]
        out.append(
            EvidenceRow(
                agent=(row.arm_agent or "").title(),
                route=row.route,
                dose=_dose(row),
                loading_dose=row.loading_dose_value,
                phototherapy=bool(row.phototherapy),
                endpoint=row.endpoint,
                region="Face" if row.instrument == "F-VASI" else "Whole body",
                week=row.week,
                responders=int(row.responders or 0),
                analysed=int(row.n_analyzed or 0),
                percent=round(float(row.percent or 0), 1),
                control_percent=_control_percent(control),
                control_analysed=None if control is None else control.n_analyzed,
                assessor=row.assessor,
                primary_endpoint=row.outcome_type == "PRIMARY",
                trial=row.source_id,
                trial_title=row.study_id if row.study_id != row.source_id else None,
                population=_population(row),
                population_note=POPULATION_NOTES.get(_population(row) or ""),
                also_reported=[
                    Replication(
                        trial=other.source_id,
                        percent=round(float(other.percent or 0), 1),
                        analysed=int(other.n_analyzed or 0),
                        control_percent=_control_percent(
                            controls.get((other.source_id, other.endpoint))
                        ),
                    )
                    for other in others
                ],
                later=None
                if tail is None
                else Continuation(
                    week=int(tail.week or 0),
                    percent=round(float(tail.percent or 0), 1),
                    responders=int(tail.responders or 0),
                    analysed=int(tail.n_analyzed or 0),
                    started=int(row.n_analyzed or 0),
                    population=_population(tail),
                    population_note=POPULATION_NOTES.get(_population(tail) or ""),
                ),
            )
        )
    # Controlled results first, ranked by the effect over their own comparator.
    # A rate on its own is not an effect: ruxolitinib with NB-UVB reports 76.5%
    # and no control arm, and would otherwise head the table.
    out.sort(
        key=lambda r: (
            r.region,
            r.controlled is False,
            -(r.difference if r.difference is not None else r.percent),
            r.agent,
        )
    )
    return out


def evidence_to_dict(rows: Sequence[EvidenceRow]) -> dict[str, Any]:
    """The payload the web API serves."""
    serialised: list[dict[str, Any]] = []
    for r in rows:
        item = asdict(r)
        item["difference"] = r.difference
        item["controlled"] = r.controlled
        if r.later is not None:
            item["later"]["retention"] = r.later.retention
            bounds = r.later.bounds
            item["later"]["bounds"] = (
                None
                if bounds is None or bounds.identified
                else {
                    "floor": bounds.floor,
                    "ceiling": bounds.ceiling,
                    "group": bounds.group,
                    "missing": bounds.missing,
                    "width": bounds.width,
                }
            )
        serialised.append(item)
    return {
        "rows": serialised,
        "count": len(rows),
        "week": PRIMARY_WEEK,
        "note": (
            f"Registry-posted results at week {PRIMARY_WEEK}, the primary endpoint of these "
            "trials. Each row states which patients its figure counted, because the trials "
            "differ: most report those assessed at the visit, two impute missing results as "
            "failures, and TRuE-V imputes at week 24 but not at week 52. Rates measured on "
            "different populations should not be read against each other. Each control is "
            "the comparator arm of the same trial and endpoint; where none is shown, the "
            "trial had no comparator. Where a trial reported both a blinded central read "
            "and a local one, the central read is used. Facial and whole-body measures are "
            "separate scales. A continuation figure is the same arm after the controlled "
            "period ended, when every patient was receiving the drug and some had left; "
            "where it counts only the patients assessed, it is bracketed by what the "
            "patients it does not cover could have done, which assumes nothing about them."
        ),
    }
