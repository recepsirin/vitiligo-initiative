"""Harmonized arm-level efficacy table for JAK inhibitors in vitiligo.

Turns the verbatim ClinicalTrials.gov results in the JAK atlas into one row
per (trial arm x responder endpoint x week): the input a scenario model
needs. Registries report the same thing many ways (endpoint in the outcome
title or in a result row label, week in the row label / title / time frame,
percentages or participant counts, arms that switch treatment mid-trial), so
every parsed field is kept next to the raw text, and anything ambiguous is
left empty and flagged for expert review rather than guessed.

Scope (v0): responder endpoints only — F-VASI / T-VASI thresholds and VNS
"4 or 5" responders — reported as a percentage or count of participants.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from vitiligo.reports.jak import JakAtlas, JakTrial, Measurement, OutcomeResult, match_agents

# ------------------------------------------------------------------ endpoints

_VASI_RE = re.compile(r"\b([FT])\s?-?\s?VASI\s?-?\s?(\d{2,3})((?:\s?/\s?\d{2,3})*)", re.IGNORECASE)
_VASI_LONG_RE = re.compile(
    r"≥\s?%?\s?(\d{2,3})\s?%?\s+Improvement.*?\b(Face|Facial|Total Body)\b", re.IGNORECASE
)
_VNS_RE = re.compile(r"Noticeability Scale|\bVNS\b", re.IGNORECASE)
_VNS_RESPONDER_RE = re.compile(r"\b4\b.*\bor\b.*\b5\b", re.IGNORECASE)
_ASSESSOR_RE = re.compile(r"\b(central|local)\b", re.IGNORECASE)
_RESPONDER_PARAMS = frozenset({"NUMBER", "COUNT_OF_PARTICIPANTS"})
_EXTENSION_RE = re.compile(r"extension|withdrawal|long[\s-]term", re.IGNORECASE)


@dataclass(frozen=True)
class Endpoint:
    instrument: str  # F-VASI | T-VASI | VNS
    threshold: int | None  # % improvement for VASI; None for VNS responders
    body_region: str | None  # face | total body | genital | None

    @property
    def label(self) -> str:
        if self.instrument == "VNS":
            region = f" ({self.body_region})" if self.body_region else ""
            return f"VNS 4-5 responder{region}"
        return f"{self.instrument}{self.threshold}"


def _vasi_endpoint(text: str) -> Endpoint | None | str:
    """Endpoint named in ``text``; "multiple" when several thresholds are listed."""
    match = _VASI_RE.search(text)
    if match:
        if match.group(3):  # e.g. "F-VASI25/50/75/90"
            return "multiple"
        instrument = f"{match.group(1).upper()}-VASI"
        region = "face" if instrument == "F-VASI" else "total body"
        return Endpoint(instrument, int(match.group(2)), region)
    if len(set(re.findall(r"≥\s?%?\s?(\d{2,3})", text))) > 1:
        return "multiple"  # e.g. "≥ 25%, ≥ 50%, and ≥ 75% Improvement"
    long_matches = _VASI_LONG_RE.findall(text)
    if long_matches:
        threshold, region = long_matches[0]
        face = region.lower() in {"face", "facial"}
        return Endpoint("F-VASI" if face else "T-VASI", threshold, "face" if face else "total body")
    return None


def parse_endpoint(outcome_title: str, class_title: str | None) -> Endpoint | None:
    """Responder endpoint of one result row (row label wins over outcome title)."""
    if class_title:
        from_class = _vasi_endpoint(class_title)
        if isinstance(from_class, Endpoint):
            return from_class
    if _VNS_RE.search(outcome_title):
        if not _VNS_RESPONDER_RE.search(outcome_title):
            return None  # category distributions, means: not a responder rate
        lowered = outcome_title.lower()
        region = next(
            (r for r in ("genital", "face", "facial", "total body") if r in lowered), None
        )
        return Endpoint("VNS", None, "face" if region == "facial" else region)
    from_title = _vasi_endpoint(outcome_title)
    return from_title if isinstance(from_title, Endpoint) else None


# ---------------------------------------------------------------------- weeks

_WEEK_ONLY_RE = re.compile(r"^\s*Week\s+(\d+)\s*$", re.IGNORECASE)
_WEEK_IN_TEXT_RE = re.compile(
    r"\bWeeks?\s+((?:\d+(?:\s*,\s*and\s+|\s*,\s*|\s+and\s+)?)+)", re.IGNORECASE
)


def _weeks_in(text: str | None) -> list[int]:
    weeks: list[int] = []
    for group in _WEEK_IN_TEXT_RE.findall(text or ""):
        weeks.extend(int(n) for n in re.findall(r"\d+", group))
    return sorted(set(weeks))


def parse_week(
    class_title: str | None, outcome_title: str, time_frame: str | None
) -> tuple[int | None, str | None]:
    """(week, source) — row label, then outcome title, then time frame.

    Returns (None, None) when the assessment week cannot be pinned to one value
    (e.g. "up to Week 48" or "Weeks 4, 8, ... 24" without per-row labels).
    """
    if class_title:
        match = _WEEK_ONLY_RE.match(class_title)
        if match:
            return int(match.group(1)), "row_label"
    title_weeks = _weeks_in(outcome_title)
    if len(title_weeks) == 1:
        return title_weeks[0], "outcome_title"
    if title_weeks:
        return None, None
    if time_frame and "up to" not in time_frame.lower():
        frame_weeks = _weeks_in(time_frame)
        if len(frame_weeks) == 1:
            return frame_weeks[0], "time_frame"
    return None, None


# ----------------------------------------------------------------------- arms

_PLACEBO_RE = re.compile(r"\b(placebo|vehicle)\b", re.IGNORECASE)
_LOADING_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mg\s*-\s*(\d+(?:\.\d+)?)\s*mg", re.IGNORECASE)
_DOSE_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(mg|%)", re.IGNORECASE)
_PERIOD_PREFIX_RE = re.compile(r"^(.*?\b(?:Period|Cohort)\b[^:]*):\s*(.+)$", re.IGNORECASE)
_PERIOD_IN_LABEL_RE = re.compile(r"\bPeriod\s+\d+\b", re.IGNORECASE)
_BID_RE = re.compile(r"\bBID\b|twice daily", re.IGNORECASE)
_QD_RE = re.compile(r"\bQD\b|once daily", re.IGNORECASE)
_TOPICAL_RE = re.compile(r"\b(cream|ointment|gel|topical|solution|foam|lotion)\b", re.IGNORECASE)
_ORAL_RE = re.compile(r"\b(tablets?|capsules?|oral)\b", re.IGNORECASE)
_PHOTOTHERAPY_RE = re.compile(
    r"(?<![a-z])(nb-?uvb|narrow[\s-]?band|phototherapy|excimer|uvb|puva)(?![a-z])", re.IGNORECASE
)


@dataclass(frozen=True)
class ArmSpec:
    label: str
    period: str | None
    role: str  # active | placebo | sequence
    agent: str | None
    dose_value: float | None
    dose_unit: str | None
    loading_dose_value: float | None
    frequency: str | None
    route: str | None
    phototherapy: bool
    flags: tuple[str, ...]


_PERIOD_SPLIT_RE = re.compile(r"\bto\b|,?\s*\bthen\b|:", re.IGNORECASE)


def _regimen_signature(part: str) -> tuple[frozenset[tuple[float, str]], str | None]:
    """Doses + dosing frequency of one period's regimen text."""
    doses = frozenset((float(v), u.lower()) for v, u in _DOSE_RE.findall(part))
    frequency = "BID" if _BID_RE.search(part) else ("QD" if _QD_RE.search(part) else None)
    return doses, frequency


def parse_arm(label: str, trial: JakTrial) -> ArmSpec:
    """Interpret a result-group label such as "Double-Blind Period: Ruxolitinib Cream 1.5% BID"."""
    flags: list[str] = []
    period: str | None = None
    body = label.strip()
    prefixed = _PERIOD_PREFIX_RE.match(body)
    if prefixed:
        period, body = prefixed.group(1).strip(), prefixed.group(2).strip()

    has_placebo = bool(_PLACEBO_RE.search(body))
    agents = match_agents(body)
    doses = {(float(v), u.lower()) for v, u in _DOSE_RE.findall(body)}
    loading = _LOADING_RE.search(body)  # "200 mg - 50 mg": pre-specified loading regimen
    # Arm labels describe consecutive periods as "A to B", "A, then B" or "A: B".
    parts = [p for p in re.split(_PERIOD_SPLIT_RE, body) if p.strip()]
    switch = len(parts) > 1 or (len(doses) > 1 and not loading) or (has_placebo and bool(agents))

    if switch:
        # "Upa 6 mg Period 1, Then Upa 6 mg Period 2", "Rux 1.5% BID to Rux 1.5% BID"
        # and "1.5% BID: 1.5% BID" continue one regimen; "1.5% QD: 1.5% BID" switches.
        same_regimen = (
            len(parts) > 1 and not has_placebo and len({_regimen_signature(p) for p in parts}) == 1
        )
        role = "active" if same_regimen else "sequence"
        if role == "sequence":
            flags.append("treatment_changes_within_arm")
    elif has_placebo:
        role = "placebo"
    else:
        role = "active"

    agent: str | None = None
    if role != "placebo":
        if agents:
            agent = agents[0]
        elif len(trial.agents) == 1:
            agent = trial.agents[0]
            flags.append("agent_inferred_from_trial")
        if len(agents) > 1:
            flags.append("multiple_agents_in_arm")

    dose_value = dose_unit = loading_dose = None
    if role == "active" and loading:
        loading_dose = float(loading.group(1))
        dose_value, dose_unit = float(loading.group(2)), "mg"
        flags.append("loading_dose_regimen")
    elif role == "active" and len(doses) == 1:
        dose_value, dose_unit = next(iter(doses))

    frequency = "BID" if _BID_RE.search(body) else ("QD" if _QD_RE.search(body) else None)

    route: str | None = None
    if role != "placebo":
        if _TOPICAL_RE.search(body):
            route = "topical"
        elif _ORAL_RE.search(body):
            route = "oral"
        elif len(trial.routes) == 1:
            route = trial.routes[0]
            flags.append("route_inferred_from_trial")

    return ArmSpec(
        label=label,
        period=period,
        role=role,
        agent=agent,
        dose_value=dose_value,
        dose_unit=dose_unit,
        loading_dose_value=loading_dose,
        frequency=frequency,
        route=route,
        phototherapy=bool(_PHOTOTHERAPY_RE.search(body)),
        flags=tuple(flags),
    )


# ------------------------------------------------------------------------ rows


@dataclass
class ArmEndpointRow:
    study_id: str
    source_id: str
    trial_agents: str
    arm_label: str
    period: str | None
    arm_role: str
    arm_agent: str | None
    dose_value: float | None
    dose_unit: str | None
    loading_dose_value: float | None
    frequency: str | None
    route: str | None
    phototherapy: bool
    endpoint: str
    instrument: str
    threshold: int | None
    body_region: str | None
    assessor: str | None
    week: int | None
    week_source: str | None
    outcome_type: str | None
    n_analyzed: int | None
    percent: float | None
    responders: int | None
    responders_derived: bool
    value_raw: str | None
    outcome_title: str
    row_label: str | None
    flags: list[str] = field(default_factory=list)


def _to_float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None and number.is_integer() else None


def _rows_for_outcome(trial: JakTrial, outcome: OutcomeResult) -> list[ArmEndpointRow]:
    if (outcome.param_type or "").upper() not in _RESPONDER_PARAMS:
        return []
    rows: list[ArmEndpointRow] = []
    is_count = (outcome.param_type or "").upper() == "COUNT_OF_PARTICIPANTS"
    unit = (outcome.unit or "").lower()
    if not is_count and "percent" not in unit and "percentage" not in outcome.title.lower():
        return []
    assessor_match = _ASSESSOR_RE.search(outcome.title)
    for m in outcome.measurements:
        endpoint = parse_endpoint(outcome.title, m.class_title)
        if endpoint is None:
            continue
        n = _to_int(m.n_analyzed)
        if n == 0:
            continue  # group not analysed for this outcome
        rows.append(_build_row(trial, outcome, m, endpoint, n, is_count, assessor_match))
    return rows


def _build_row(
    trial: JakTrial,
    outcome: OutcomeResult,
    m: Measurement,
    endpoint: Endpoint,
    n: int | None,
    is_count: bool,
    assessor_match: re.Match[str] | None,
) -> ArmEndpointRow:
    arm = parse_arm(m.group_title or m.group_id, trial)
    flags = list(arm.flags)
    week, week_source = parse_week(m.class_title, outcome.title, outcome.time_frame)
    if week is None:
        flags.append("week_ambiguous")
    if n is None:
        flags.append("n_missing")

    value = _to_float(m.value)
    percent: float | None = None
    responders: int | None = None
    derived = False
    if value is None:
        flags.append("value_not_numeric")
    elif is_count:
        responders = int(value)
        if n:
            percent = round(100.0 * value / n, 2)
    else:
        percent = value
        if n:
            responders = round(value * n / 100.0)
            derived = True
    if _EXTENSION_RE.search(trial.title or ""):
        # A separate extension / randomized-withdrawal study: participants enter
        # already treated, so responses are not comparable with arms that start
        # from baseline.
        flags.append("extension_study")
    elif _EXTENSION_RE.search(arm.period or ""):
        # An extension period inside the parent trial (e.g. TRuE-V weeks 24-52):
        # completers continuing their arm; usable as time-course data when the
        # regimen does not change.
        flags.append("extension_period")
    if arm.role == "placebo" and week is not None and week > 24:
        # e.g. vehicle "withdrawal" arms of extension studies: participants were
        # previously treated, so this is not a naive placebo response.
        flags.append("placebo_after_week_24_check_design")

    return ArmEndpointRow(
        study_id=trial.study_id,
        source_id=trial.source_id,
        trial_agents=";".join(trial.agents),
        arm_label=arm.label,
        period=arm.period,
        arm_role=arm.role,
        arm_agent=arm.agent,
        dose_value=arm.dose_value,
        dose_unit=arm.dose_unit,
        loading_dose_value=arm.loading_dose_value,
        frequency=arm.frequency,
        route=arm.route,
        phototherapy=arm.phototherapy,
        endpoint=endpoint.label,
        instrument=endpoint.instrument,
        threshold=endpoint.threshold,
        body_region=endpoint.body_region,
        assessor=assessor_match.group(1).lower() if assessor_match else None,
        week=week,
        week_source=week_source,
        outcome_type=outcome.type,
        n_analyzed=n,
        percent=percent,
        responders=responders,
        responders_derived=derived,
        value_raw=m.value,
        outcome_title=outcome.title,
        row_label=m.class_title,
        flags=flags,
    )


def harmonize_arms(atlas: JakAtlas) -> list[ArmEndpointRow]:
    """All responder rows from the atlas's posted results, in atlas order."""
    return arm_rows(atlas.trials)


def arm_rows(trials: Sequence[JakTrial]) -> list[ArmEndpointRow]:
    """Responder rows from the posted results of the given atlas records."""
    rows: list[ArmEndpointRow] = []
    for trial in trials:
        for outcome in trial.outcomes:
            rows.extend(_rows_for_outcome(trial, outcome))
    _flag_duplicates(rows)
    return rows


def _flag_duplicates(rows: list[ArmEndpointRow]) -> None:
    """Mark the same arm/endpoint/assessor/week reported by more than one outcome."""
    groups: dict[tuple[Any, ...], list[ArmEndpointRow]] = {}
    for row in rows:
        if row.week is None:
            continue
        key = (row.source_id, row.arm_label, row.endpoint, row.assessor, row.week)
        groups.setdefault(key, []).append(row)
    for group in groups.values():
        if len(group) < 2:
            continue
        differ = len({(r.percent, r.n_analyzed) for r in group}) > 1
        for row in group:
            row.flags.append("reported_twice_values_differ" if differ else "reported_twice")


def summarize_arms(rows: list[ArmEndpointRow]) -> dict[str, Any]:
    """Coverage numbers for the console and for review."""
    usable = [
        r
        for r in rows
        if r.week is not None
        and r.n_analyzed
        and r.percent is not None
        and r.arm_role != "sequence"
    ]
    return {
        "rows": len(rows),
        "trials": len({r.source_id for r in rows}),
        "arms": len({(r.source_id, r.arm_label) for r in rows}),
        "model_ready_rows": len(usable),
        "model_ready_trials": len({r.source_id for r in usable}),
        "by_endpoint": dict(Counter(r.endpoint for r in usable).most_common()),
        "by_agent": dict(Counter(r.arm_agent or "placebo/vehicle" for r in usable).most_common()),
        "by_week": dict(sorted(Counter(r.week for r in usable if r.week is not None).items())),
        "flags": dict(Counter(f for r in rows for f in r.flags).most_common()),
    }


_CSV_FIELDS = [f.name for f in fields(ArmEndpointRow)]


def write_arms_csv(rows: list[ArmEndpointRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            data = asdict(row)
            data["flags"] = ";".join(row.flags)
            writer.writerow({k: "" if v is None else v for k, v in data.items()})
