"""Tier-2 evidence: sealed forecasts for every unreported trial, and their scoring.

``registry_targets`` reads the *registered* design of each JAK trial without
posted results (ClinicalTrials.gov protocol: arms, doses, primary outcomes)
and returns forecastable targets — an active arm paired with the placebo arm
of the same (sub-)study, for each VASI responder endpoint in a primary
outcome — plus an explicit reason for everything it skips. Nothing is
guessed: an unstated dosing frequency becomes an equal QD/BID mixture and the
assumption is sealed into the record.

``resolve`` scores sealed forecasts once results are posted (after a corpus
refresh): interval coverage and, when the predictive draws were sealed,
the log predictive score of the observed counts.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo.discovery.ledger import Ledger, verify_seal
from vitiligo.models.jak_mbma import (
    Interval,
    Posterior,
    Scenario,
    _extrapolation_notes,
    daily_dose,
    freeze,
    predict_draws,
)
from vitiligo.reports.jak import JAK_AGENTS, jak_record_from_ctgov, match_agents
from vitiligo.reports.jak_arms import ArmEndpointRow, _weeks_in, arm_rows

# "F-VASI75", "F-VASI 75", and "(T-VASI) 50" as registries write them.
_ENDPOINT_RE = re.compile(r"\b([FT])\s?-?\s?VASI\)?\s?-?\s?(\d{2,3})\b", re.IGNORECASE)
_LONG_ENDPOINT_RE = re.compile(
    r"(?:≥|>=)\s?(\d{2,3})\s?%\s+Improvement.*?\b(Facial|Face|Total)\b", re.IGNORECASE
)
_WEEK_RE = re.compile(r"\bweeks?\s*(\d{1,3})\b|\b(\d{1,3})\s*weeks?\b", re.IGNORECASE)
_DOSE_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(mg|milligrams?|%)", re.IGNORECASE)
_PLACEBO_RE = re.compile(r"\b(placebo|vehicle|sham)\b", re.IGNORECASE)
# Excluded when in the arm *label* (a description may mention a later extension
# of a randomized arm, as Tranquillo 2's do) ...
_EXCLUDED_LABEL_RE = re.compile(r"open[\s-]label|extension|optional|period b", re.IGNORECASE)
# ... or anywhere in label + description.
_NON_RANDOMIZED_RE = re.compile(r"non[\s-]randomi[sz]ed", re.IGNORECASE)
_QD_RE = re.compile(r"\bQD\b|once daily|once a day", re.IGNORECASE)
_BID_RE = re.compile(r"\bBID\b|twice daily|twice a day", re.IGNORECASE)
_PHOTOTHERAPY_RE = re.compile(
    r"nb-?uvb|narrow[\s-]?band|phototherapy|excimer|\buvb\b", re.IGNORECASE
)
_GROUP_RE = re.compile(
    r"^(.*?\b(?:study|part|cohort)\s*\w+(?:,\s*period\s*\w+)?)\s*:", re.IGNORECASE
)


@dataclass(frozen=True)
class ForecastTarget:
    trial: str
    group: str | None
    arm_label: str
    control_label: str
    agent: str
    dose_value: float
    dose_unit: str
    frequency: str | None
    phototherapy: bool
    instrument: str
    threshold: int
    week: int
    registry_measure: str
    assumptions: tuple[str, ...] = ()
    phase3: bool = False  # used by model v0.3

    @property
    def key(self) -> str:
        return (
            f"{self.trial}|{self.arm_label}|{self.dose_value:g}{self.dose_unit}"
            f"|{self.instrument}{self.threshold}|wk{self.week}"
        )


@dataclass
class Skip:
    trial: str
    reason: str


def registry_endpoints(measure: str) -> list[tuple[str, int]]:
    """Every VASI responder endpoint named in a registered outcome measure."""
    found = {(f"{m[0].upper()}-VASI", int(m[1])) for m in _ENDPOINT_RE.findall(measure)}
    if not found:
        for threshold, region in _LONG_ENDPOINT_RE.findall(measure):
            instrument = "T-VASI" if region.lower() == "total" else "F-VASI"
            found.add((instrument, int(threshold)))
    if re.search(
        r"percent(age)?\s+change|change from baseline|mean", measure, re.IGNORECASE
    ) and not re.search(
        r"proportion|percentage of participants|response|achiev", measure, re.IGNORECASE
    ):
        return []  # continuous endpoint, not a responder rate
    return sorted(found)


def registry_week(time_frame: str | None, measure: str) -> int | None:
    """The single assessment week of a registered outcome, or None if ambiguous."""
    for text in (time_frame or "", measure):
        # "Week 24", "52 Weeks", and lists such as "Weeks 24 and 36" (ambiguous).
        weeks = {int(a or b) for a, b in _WEEK_RE.findall(text)} | set(_weeks_in(text))
        if len(weeks) == 1:
            return weeks.pop()
        if len(weeks) > 1:
            return None
    return None


@dataclass(frozen=True)
class _RegistryArm:
    label: str
    description: str
    kind: str | None
    group: str | None

    @property
    def text(self) -> str:
        return f"{self.label} {self.description}"


def _parse_arms(protocol: dict[str, Any]) -> list[_RegistryArm]:
    arms = []
    for arm in (protocol.get("armsInterventionsModule") or {}).get("armGroups") or []:
        label = str(arm.get("label") or "")
        group = _GROUP_RE.match(label)
        arms.append(
            _RegistryArm(
                label=label,
                description=str(arm.get("description") or ""),
                kind=arm.get("type"),
                group=group.group(1).strip() if group else None,
            )
        )
    return arms


def _dose(text: str) -> tuple[float, str] | None:
    doses = {(float(v), "%" if u == "%" else "mg") for v, u in _DOSE_RE.findall(text)}
    return doses.pop() if len(doses) == 1 else None


def registry_targets(
    trials: Sequence[tuple[str, str, dict[str, Any]]],
) -> tuple[list[ForecastTarget], list[Skip]]:
    """Targets from (trial id, status, CT.gov protocolSection) of unreported JAK trials."""
    targets: list[ForecastTarget] = []
    skips: list[Skip] = []
    known_agents = {a.name for a in JAK_AGENTS}
    for trial_id, status, protocol in trials:
        if status in {"TERMINATED", "WITHDRAWN", "UNKNOWN"}:
            skips.append(Skip(trial_id, f"status {status}"))
            continue
        endpoints: list[tuple[str, int, int, str]] = []
        for outcome in (protocol.get("outcomesModule") or {}).get("primaryOutcomes") or []:
            measure = str(outcome.get("measure") or "")
            week = registry_week(outcome.get("timeFrame"), measure)
            for instrument, threshold in registry_endpoints(measure):
                if week is not None:
                    endpoints.append((instrument, threshold, week, measure))
        # One target per endpoint and week, even if several primaries name it
        # (e.g. US and global primaries both on F-VASI75 at week 52).
        endpoints = list({(e[0], e[1], e[2]): e for e in reversed(endpoints)}.values())[::-1]
        if not endpoints:
            skips.append(Skip(trial_id, "no VASI responder primary endpoint with a single week"))
            continue

        arms = _parse_arms(protocol)
        groups: dict[str | None, list[_RegistryArm]] = {}
        for arm in arms:
            if _EXCLUDED_LABEL_RE.search(arm.label) or _NON_RANDOMIZED_RE.search(arm.text):
                continue
            groups.setdefault(arm.group, []).append(arm)
        made_any = False
        for group, members in groups.items():
            controls = [
                a
                for a in members
                if (a.kind == "PLACEBO_COMPARATOR" or _PLACEBO_RE.search(a.label))
                and not set(match_agents(a.label)) & known_agents
            ]
            switching = [
                a for a in members if _PLACEBO_RE.search(a.label) and match_agents(a.label)
            ]
            if switching:
                skips.append(
                    Skip(trial_id, f"placebo arm switches to active ({switching[0].label})")
                )
                continue
            if not controls:
                continue
            for arm in members:
                if arm in controls or arm.kind not in {"EXPERIMENTAL", "ACTIVE_COMPARATOR", None}:
                    continue
                agents = match_agents(arm.text)
                if len(agents) != 1:
                    skips.append(Skip(trial_id, f"arm '{arm.label}': agent not identified"))
                    continue
                dose = _dose(arm.label) or _dose(arm.description)
                if dose is None:
                    skips.append(Skip(trial_id, f"arm '{arm.label}': dose not disclosed"))
                    continue
                frequency = (
                    "QD"
                    if _QD_RE.search(arm.text)
                    else ("BID" if _BID_RE.search(arm.text) else None)
                )
                assumptions = (
                    ("dosing frequency not stated in the registry: equal QD/BID mixture",)
                    if frequency is None
                    else ()
                )
                for instrument, threshold, week, measure in endpoints:
                    targets.append(
                        ForecastTarget(
                            trial=trial_id,
                            group=group,
                            arm_label=arm.label,
                            control_label=controls[0].label,
                            agent=agents[0],
                            dose_value=dose[0],
                            dose_unit=dose[1],
                            frequency=frequency,
                            phototherapy=bool(_PHOTOTHERAPY_RE.search(arm.text)),
                            instrument=instrument,
                            threshold=threshold,
                            week=week,
                            registry_measure=measure,
                            assumptions=assumptions,
                            phase3="PHASE3"
                            in ((protocol.get("designModule") or {}).get("phases") or []),
                        )
                    )
                    made_any = True
        if not made_any and not any(s.trial == trial_id for s in skips):
            skips.append(Skip(trial_id, "no randomized active arm paired with a placebo arm"))
    return targets, skips


# ------------------------------------------------------------------ forecasting


def forecast_target(
    posterior: Posterior,
    target: ForecastTarget,
    *,
    routes: dict[str, str],
    seed: int = 7,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Predictive summary and draws for one target (new trial; QD/BID mixed if unknown)."""
    frequencies = [target.frequency] if target.frequency else ["QD", "BID"]
    active_parts, control_parts = [], []
    scenario = None
    for frequency in frequencies:
        scenario = Scenario(
            agent=target.agent,
            dose=target.dose_value,
            dose_unit=target.dose_unit,
            frequency=frequency,
            week=target.week,
            threshold=target.threshold,
            phototherapy=target.phototherapy,
            route=routes.get(target.agent),
            phase3=target.phase3,
        )
        p_active, p_control = predict_draws(posterior, scenario, seed=seed)
        half = len(p_active) // len(frequencies)
        active_parts.append(p_active[:half])
        control_parts.append(p_control[:half])
    assert scenario is not None
    p_active = np.concatenate(active_parts)
    p_control = np.concatenate(control_parts)
    summary = {
        "p_active": asdict(Interval.of(p_active)),
        "p_control": asdict(Interval.of(p_control)),
        "difference": asdict(Interval.of(p_active - p_control)),
        "p_active_beats_control": float(np.mean(p_active > p_control)),
        "extrapolation": _extrapolation_notes(posterior, scenario),
    }
    return summary, p_active, p_control


def write_forecast(
    target: ForecastTarget,
    summary: dict[str, Any],
    p_active: np.ndarray,
    p_control: np.ndarray,
    directory: Path,
    *,
    context: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Seal a forecast: draws to .npz (hash sealed into the record) + record JSON."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", target.key).strip("-").lower()
    draws_path = directory / f"{stem}.npz"
    np.savez_compressed(
        draws_path, p_active=p_active.astype(np.float32), p_control=p_control.astype(np.float32)
    )
    record = freeze(
        {
            "label": (
                f"{target.trial}: {target.arm_label} vs {target.control_label}, "
                f"{target.instrument}{target.threshold} at week {target.week}"
            ),
            "target": {**asdict(target), "key": target.key},
            "prediction": summary,
            "draws_file": draws_path.name,
            "draws_sha256": hashlib.sha256(draws_path.read_bytes()).hexdigest(),
            **context,
        }
    )
    path = directory / f"{stem}.json"
    path.write_text(json.dumps(record, indent=2, default=str) + "\n")
    return path, record


# ------------------------------------------------------------------- resolution


@dataclass
class Resolution:
    sha256: str
    label: str
    resolved: bool
    detail: dict[str, Any] = field(default_factory=dict)


def _target_of(record: dict[str, Any]) -> dict[str, Any] | None:
    """Target fields of an automatic record, or reconstructed from a manual one."""
    if "target" in record:
        return dict(record["target"])
    scenario = (record.get("prediction") or {}).get("scenario")
    trial = re.search(r"\bNCT\d{8}\b", str(record.get("label", "")))
    instrument = (record.get("dataset") or {}).get("instrument")
    if not (scenario and trial and instrument):
        return None
    return {
        "trial": trial.group(0),
        "agent": scenario["agent"],
        "dose_value": scenario["dose"],
        "frequency": scenario.get("frequency"),
        "instrument": instrument,
        "threshold": scenario["threshold"],
        "week": scenario["week"],
    }


def _observed(rows: Sequence[ArmEndpointRow], target: dict[str, Any]) -> dict[str, Any] | None:
    """Posted active/control counts matching a forecast target, if any."""

    def matches(r: ArmEndpointRow) -> bool:
        return (
            target["trial"] in (r.source_id, r.study_id)
            and r.instrument == target["instrument"]
            and r.threshold == target["threshold"]
            and r.week == target["week"]
            and r.n_analyzed is not None
            and r.responders is not None
            and "treatment_changes_within_arm" not in r.flags
        )

    frequency = target.get("frequency")
    wanted = daily_dose(target["dose_value"], frequency) if frequency else None
    active = [
        r
        for r in rows
        if matches(r)
        and r.arm_role == "active"
        and r.arm_agent == target["agent"]
        and r.dose_value is not None
        and (
            daily_dose(r.dose_value, r.frequency) == wanted
            if wanted is not None
            else r.dose_value == target["dose_value"]
        )
    ]
    control = [r for r in rows if matches(r) and r.arm_role == "placebo"]
    if not active or not control:
        return None
    a, c = active[0], control[0]
    assert a.n_analyzed and c.n_analyzed and a.responders is not None and c.responders is not None
    return {
        "responders_active": a.responders,
        "n_active": a.n_analyzed,
        "responders_control": c.responders,
        "n_control": c.n_analyzed,
        "rate_active": a.responders / a.n_analyzed,
        "rate_control": c.responders / c.n_analyzed,
    }


def _log_score(obs: dict[str, Any], p_active: np.ndarray, p_control: np.ndarray) -> float:
    """log of the predictive probability of the observed counts (binomial x binomial)."""
    pa = np.clip(p_active.astype(float), 1e-12, 1 - 1e-12)
    pc = np.clip(p_control.astype(float), 1e-12, 1 - 1e-12)

    def log_binom(r: int, n: int, p: np.ndarray) -> np.ndarray:
        const = math.lgamma(n + 1) - math.lgamma(r + 1) - math.lgamma(n - r + 1)
        return np.asarray(const + r * np.log(p) + (n - r) * np.log1p(-p))

    terms = log_binom(obs["responders_active"], obs["n_active"], pa) + log_binom(
        obs["responders_control"], obs["n_control"], pc
    )
    peak = float(terms.max())
    return peak + math.log(float(np.mean(np.exp(terms - peak))))


def score_record(
    record: dict[str, Any],
    file: str,
    rows: Sequence[ArmEndpointRow],
    *,
    base_dir: Callable[[str], Path] = Path,
) -> Resolution:
    """Score one sealed forecast against posted results (unresolved if none match)."""
    sha, label = str(record.get("sha256", "")), str(record.get("label", ""))
    target = _target_of(record)
    if target is None:
        return Resolution(sha, label, False, {"reason": "target not reconstructable"})
    obs = _observed(rows, target)
    if obs is None:
        return Resolution(sha, label, False, {"reason": "results not posted yet"})
    pred = record["prediction"]
    diff = obs["rate_active"] - obs["rate_control"]
    detail: dict[str, Any] = {
        "observed": obs,
        "active_in80": pred["p_active"]["lo80"] <= obs["rate_active"] <= pred["p_active"]["hi80"],
        "active_in95": pred["p_active"]["lo95"] <= obs["rate_active"] <= pred["p_active"]["hi95"],
        "difference_in80": pred["difference"]["lo80"] <= diff <= pred["difference"]["hi80"],
        "direction_correct": (diff > 0) == (pred["p_active_beats_control"] >= 0.5),
        "note": "intervals are for true response probabilities; observed rates add binomial noise",
    }
    draws_name = record.get("draws_file")
    if draws_name:
        draws_path = base_dir(file).parent / draws_name
        if draws_path.is_file() and (
            hashlib.sha256(draws_path.read_bytes()).hexdigest() == record.get("draws_sha256")
        ):
            with np.load(draws_path) as draws:
                detail["log_score"] = _log_score(obs, draws["p_active"], draws["p_control"])
        else:
            detail["log_score_error"] = "draws file missing or hash mismatch"
    return Resolution(sha, label, True, detail)


def resolve(
    ledger: Ledger,
    rows: Sequence[ArmEndpointRow],
    *,
    base_dir: Callable[[str], Path] = Path,
) -> list[Resolution]:
    """Score every pending forecast in the ledger whose results are now in the arm table."""
    results: list[Resolution] = []
    for sha, _label, file, record in ledger.pending_forecasts():
        result = score_record(record, file, rows, base_dir=base_dir)
        if result.resolved:
            ledger.resolve_forecast(sha, result.detail)
        results.append(result)
    return results


def comparison_key(record: dict[str, Any]) -> tuple[Any, ...] | None:
    """What a forecast predicts, independent of how its record was produced."""
    target = _target_of(record)
    if target is None:
        return None
    return (
        target["trial"],
        target["instrument"],
        target["threshold"],
        target["week"],
        float(target["dose_value"]),
    )


def compare_models(scored: Sequence[tuple[str, dict[str, Any], Resolution]]) -> dict[str, Any]:
    """Summed log scores per model on the targets resolved, with a log score, for every model.

    ``scored`` holds (model, record, resolution) for each sealed forecast.
    """
    by_key: dict[tuple[Any, ...], dict[str, float]] = {}
    models: set[str] = set()
    for model, record, result in scored:
        key = comparison_key(record)
        if key is None:
            continue
        models.add(model)
        if result.resolved and "log_score" in result.detail:
            by_key.setdefault(key, {})[model] = float(result.detail["log_score"])
    out: dict[str, Any] = {}
    names = sorted(models)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            common = [k for k, scores in by_key.items() if a in scores and b in scores]
            out[f"{a} vs {b}"] = {
                "targets": len(common),
                a: sum(by_key[k][a] for k in common),
                b: sum(by_key[k][b] for k in common),
            }
    return out


def sealed_records(paths: Sequence[Path]) -> list[tuple[Path, dict[str, Any]]]:
    """Sealed forecast records under the given files or folders; tampered seals raise."""
    files: list[Path] = []
    for p in paths:
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    out: list[tuple[Path, dict[str, Any]]] = []
    for path in files:
        record = json.loads(path.read_text())
        if not isinstance(record, dict) or "sha256" not in record or "prediction" not in record:
            continue  # back-test files and other JSON
        if not verify_seal(record):
            raise ValueError(f"seal does not match content: {path}")
        out.append((path, record))
    return out


def check_forecasts(
    paths: Sequence[Path], fetch: Callable[[str], dict[str, Any] | None]
) -> list[tuple[Path, Resolution]]:
    """Score sealed forecasts straight from the registry, without corpus or ledger.

    ``fetch`` returns one raw ClinicalTrials.gov study (e.g. ``CTGovClient.fetch_study``).
    """
    records = sealed_records(paths)
    trials = sorted({t["trial"] for _p, r in records if (t := _target_of(r))})
    studies = [study for trial in trials if (study := fetch(trial)) is not None]
    atlas_records = [rec for study in studies if (rec := jak_record_from_ctgov(study))]
    rows = arm_rows(atlas_records)
    return [(path, score_record(record, str(path), rows)) for path, record in records]
