"""The discovery loop: generate -> test on held-out evidence -> ledger -> policy.

Evidence units are two arms of one trial at one week: an active arm vs the
control arm (family ``superiority_margin``), or a more vs a less intensive
regimen of the same agent (families ``regimen_contrast`` and
``dose_retention``). Each unit is spent once, ever.

One *round* per held-out trial T:

1. Freeze the policy (from the ledger, without T's own earlier rewards) and
   the discovery count used for power predictions (without T's own earlier
   discoveries), so nothing chosen for T can depend on T's data.
2. For each instrument, refit the scenario model with T removed entirely.
3. For each unspent unit of T, score every template (family x threshold x
   margin or retained fraction) by the held-out model's belief that the claim
   is true; abstain if none reaches the belief threshold, or if the model
   predicts too small a chance that testing would produce a discovery
   (abstaining spends nothing). Units with the best predicted chance go first,
   because earlier tests get larger e-LOND levels.
4. Otherwise let the policy pick a template, compute the mixture e-value on
   T's observed counts (alternatives: the held-out model's predictive draws in
   which the claim holds), apply e-LOND, and record the test (the unit is now
   spent, for good).
5. After the round, write the policy rewards (e >= 2) to the ledger.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from vitiligo.discovery.evidence import (
    discovery_power,
    elond_level,
    is_discovery,
    mixture_log_e,
)
from vitiligo.discovery.ledger import Ledger
from vitiligo.discovery.policy import (
    EVIDENCE_REWARD_LOG_E,
    ThompsonPolicy,
    arm_name,
    contrast_arm_name,
    retention_arm_name,
)
from vitiligo.models.jak_mbma import (
    ArmInfo,
    FitSettings,
    MBMAData,
    Observation,
    Posterior,
    Scenario,
    build_dataset,
    converged,
    fit,
    predict_draws,
    predict_pair_draws,
)
from vitiligo.reports.jak_arms import ArmEndpointRow

SUPERIORITY = "superiority_margin"  # active arm beats control by more than a margin
CONTRAST = "regimen_contrast"  # more intensive regimen beats a less intensive one
RETENTION = "dose_retention"  # less intensive regimen keeps more than a fraction of the response
FAMILIES = (SUPERIORITY, CONTRAST, RETENTION)
FAMILY = SUPERIORITY  # the v0 name


@dataclass
class LoopConfig:
    alpha: float = 0.10
    belief_threshold: float = 0.80
    min_power: float = 0.50  # model-predicted chance that the test yields a discovery
    power_simulations: int = 200
    mixture_draws: int = 400  # alternative draws averaged in the e-value
    thresholds: tuple[int, ...] = (50, 75, 90)
    margins: tuple[float, ...] = (0.0, 0.05, 0.10, 0.15)
    contrast_margins: tuple[float, ...] = (0.0, 0.05, 0.10, 0.15)
    retention_ratios: tuple[float, ...] = (0.50, 0.75)
    families: tuple[str, ...] = FAMILIES
    instruments: tuple[str, ...] = ("F-VASI", "T-VASI")
    seed: int = 20261014
    fit_settings: FitSettings = field(default_factory=lambda: FitSettings(draws=1000, tune=1500))


@dataclass(frozen=True)
class Unit:
    """One spendable piece of held-out evidence: two arms of one trial at one week.

    ``kind == "control"``: ``arm`` is an active arm, ``comparator`` the trial's
    control arm. ``kind == "pair"``: ``arm`` is the more intensive and
    ``comparator`` the less intensive regimen of the same agent.
    """

    key: str
    kind: str
    instrument: str
    trial: str
    week: int
    arm: ArmInfo
    comparator: ArmInfo
    arm_obs: Observation
    comparator_obs: Observation


def control_units(data: MBMAData) -> list[Unit]:
    """Active-vs-control pairs at the same week within each controlled trial."""
    units: list[Unit] = []
    for trial in data.controlled_trials():
        controls = {
            o.week: o
            for o in sorted(data.observations, key=lambda o: o.arm)
            if data.arms[o.arm].source_id == trial and not data.arms[o.arm].active
        }
        for obs in data.observations:
            arm = data.arms[obs.arm]
            if arm.source_id != trial or not arm.active or obs.week not in controls:
                continue
            control_obs = controls[obs.week]
            key = (
                f"{data.instrument}|{trial}|{arm.label}|dose={arm.daily_dose}"
                f"|load={arm.loading_dose}|photo={int(arm.phototherapy)}|wk{obs.week}"
            )
            units.append(
                Unit(
                    key=key,
                    kind="control",
                    instrument=data.instrument,
                    trial=trial,
                    week=obs.week,
                    arm=arm,
                    comparator=data.arms[control_obs.arm],
                    arm_obs=obs,
                    comparator_obs=control_obs,
                )
            )
    return units


def more_intensive(a: ArmInfo, b: ArmInfo) -> bool:
    """``a`` is at least as intensive as ``b`` in daily dose, loading dose and
    phototherapy, and more intensive in at least one (same agent and dose unit)."""
    if not (a.active and b.active and a.agent and a.agent == b.agent):
        return False
    if a.dose_unit != b.dose_unit or a.daily_dose is None or b.daily_dose is None:
        return False
    first = (a.daily_dose, a.loading_dose or 0.0, float(a.phototherapy))
    second = (b.daily_dose, b.loading_dose or 0.0, float(b.phototherapy))
    return first != second and all(x >= y for x, y in zip(first, second, strict=True))


def _signature(arm: ArmInfo) -> str:
    return (
        f"{arm.label}|dose={arm.daily_dose}|load={arm.loading_dose}|photo={int(arm.phototherapy)}"
    )


def pair_units(data: MBMAData) -> list[Unit]:
    """Ordered regimen pairs of one agent within a trial, at weeks both arms report."""
    by_arm_week = {(o.arm, o.week): o for o in data.observations}
    units: list[Unit] = []
    for i, upper in enumerate(data.arms):
        for j, lower in enumerate(data.arms):
            if upper.source_id != lower.source_id or not more_intensive(upper, lower):
                continue
            weeks = sorted(
                {w for a, w in by_arm_week if a == i} & {w for a, w in by_arm_week if a == j}
            )
            for week in weeks:
                units.append(
                    Unit(
                        key=(
                            f"pair|{data.instrument}|{upper.source_id}|{_signature(upper)}"
                            f"|vs|{_signature(lower)}|wk{week}"
                        ),
                        kind="pair",
                        instrument=data.instrument,
                        trial=upper.source_id,
                        week=week,
                        arm=upper,
                        comparator=lower,
                        arm_obs=by_arm_week[(i, week)],
                        comparator_obs=by_arm_week[(j, week)],
                    )
                )
    return units


def evidence_units(data: MBMAData, families: Sequence[str] = FAMILIES) -> list[Unit]:
    units = control_units(data) if SUPERIORITY in families else []
    if CONTRAST in families or RETENTION in families:
        units += pair_units(data)
    return units


def _responders(obs: Observation, threshold: int) -> int | None:
    if threshold not in obs.thresholds:
        return None
    return obs.responders[obs.thresholds.index(threshold)]


def _regimen(arm: ArmInfo) -> str:
    if arm.agent and arm.agent.lower() not in arm.label.lower():
        return f"{arm.label} ({arm.agent})"
    return arm.label


@dataclass
class Candidate:
    """A claim ``p_x - ratio * p_y > margin`` about one unit, with the held-out
    model's predictive draws. ``swap`` puts the comparator on the x side."""

    family: str
    arm: str  # policy arm (template)
    threshold: int
    margin: float
    ratio: float
    swap: bool
    belief: float
    draws_x: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))
    draws_y: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))
    power: float | None = None
    power_alpha: float | None = None

    def holds(self) -> np.ndarray:
        return np.asarray(self.draws_x - self.ratio * self.draws_y > self.margin)

    def alternative(self, limit: int) -> tuple[np.ndarray, np.ndarray]:
        """Predictive draws in which the claim holds (the mixture alternative)."""
        keep = self.holds()
        x, y = self.draws_x[keep], self.draws_y[keep]
        step = max(1, len(x) // limit)
        return x[::step][:limit], y[::step][:limit]

    def sides(self, unit: Unit) -> tuple[Observation, Observation]:
        """(x, y) observations of the unit, in claim order."""
        if self.swap:
            return unit.comparator_obs, unit.arm_obs
        return unit.arm_obs, unit.comparator_obs

    def predicted(self) -> tuple[float, float]:
        """Mean predicted rates of (unit arm, unit comparator)."""
        x, y = float(np.mean(self.draws_x)), float(np.mean(self.draws_y))
        return (y, x) if self.swap else (x, y)


def _statement(unit: Unit, c: Candidate) -> str:
    where = f"{unit.instrument}{c.threshold} at week {unit.week} (held-out trial {unit.trial})"
    if c.family == SUPERIORITY:
        return f"{_regimen(unit.arm)} beats control by more than {100 * c.margin:.0f} points on {where}"
    if c.family == CONTRAST:
        return (
            f"{_regimen(unit.arm)} beats {_regimen(unit.comparator)} by more than "
            f"{100 * c.margin:.0f} points on {where}"
        )
    return (
        f"{_regimen(unit.comparator)} keeps more than {100 * c.ratio:.0f}% of the response "
        f"rate of {_regimen(unit.arm)} on {where}"
    )


def _arm_spec(arm: ArmInfo) -> dict[str, Any]:
    return {
        "label": arm.label,
        "agent": arm.agent,
        "daily_dose": arm.daily_dose,
        "dose_unit": arm.dose_unit,
        "loading_dose": arm.loading_dose,
        "phototherapy": arm.phototherapy,
    }


def _spec(unit: Unit, c: Candidate | None, family: str) -> dict[str, Any]:
    if unit.kind == "control":  # the v0 spec, unchanged so ledger entries stay comparable
        return {
            "family": SUPERIORITY,
            "unit_key": unit.key,
            "instrument": unit.instrument,
            "trial": unit.trial,
            "arm_label": unit.arm.label,
            "agent": unit.arm.agent,
            "daily_dose": unit.arm.daily_dose,
            "dose_unit": unit.arm.dose_unit,
            "loading_dose": unit.arm.loading_dose,
            "phototherapy": unit.arm.phototherapy,
            "week": unit.week,
            "threshold": c.threshold if c else None,
            "margin": c.margin if c else None,
        }
    return {
        "family": family,
        "unit_key": unit.key,
        "instrument": unit.instrument,
        "trial": unit.trial,
        "more_intensive": _arm_spec(unit.arm),
        "less_intensive": _arm_spec(unit.comparator),
        "week": unit.week,
        "threshold": c.threshold if c else None,
        "margin": c.margin if c else None,
        "ratio": c.ratio if c else None,
    }


def _scenario(arm: ArmInfo, week: int, threshold: int, routes: dict[str, str]) -> Scenario:
    assert arm.agent is not None and arm.daily_dose is not None
    return Scenario(
        agent=arm.agent,
        dose=arm.daily_dose,
        dose_unit=arm.dose_unit or "",
        frequency=None,  # daily dose already
        week=week,
        threshold=threshold,
        loading_dose=arm.loading,
        phototherapy=arm.phototherapy,
        route=routes.get(arm.agent),
    )


def _candidates(
    posterior: Posterior,
    unit: Unit,
    config: LoopConfig,
    agent_routes: dict[str, str],
) -> list[Candidate]:
    """Every template the held-out model can score for this unit, with its belief."""
    out: list[Candidate] = []

    def add(family: str, arm: str, k: int, margin: float, ratio: float, swap: bool,
            x: np.ndarray, y: np.ndarray) -> None:  # fmt: skip
        c = Candidate(family, arm, k, margin, ratio, swap, 0.0, x, y)
        c.belief = float(np.mean(c.holds()))
        out.append(c)

    for k in config.thresholds:
        if (
            k not in posterior.data.thresholds
            or _responders(unit.arm_obs, k) is None
            or _responders(unit.comparator_obs, k) is None
        ):
            continue
        if unit.kind == "control":
            if SUPERIORITY not in config.families:
                continue
            p_active, p_control = predict_draws(
                posterior, _scenario(unit.arm, unit.week, k, agent_routes)
            )
            for margin in config.margins:
                add(SUPERIORITY, arm_name(k, margin), k, margin, 1.0, False, p_active, p_control)
            continue
        p_upper, p_lower = predict_pair_draws(
            posterior,
            _scenario(unit.arm, unit.week, k, agent_routes),
            _scenario(unit.comparator, unit.week, k, agent_routes),
        )
        if CONTRAST in config.families:
            for margin in config.contrast_margins:
                add(CONTRAST, contrast_arm_name(k, margin), k, margin, 1.0, False, p_upper, p_lower)
        if RETENTION in config.families:
            for ratio in config.retention_ratios:
                add(RETENTION, retention_arm_name(k, ratio), k, 0.0, ratio, True, p_lower, p_upper)
    return out


def _power(unit: Unit, c: Candidate, alpha_t: float, config: LoopConfig) -> float:
    """Predicted chance of a discovery at level ``alpha_t`` (cached per level)."""
    if c.power is None or c.power_alpha != alpha_t:
        x_obs, y_obs = c.sides(unit)
        c.power = discovery_power(
            n_active=x_obs.n,
            n_control=y_obs.n,
            draws_active=c.draws_x,
            draws_control=c.draws_y,
            margin=c.margin,
            ratio=c.ratio,
            alpha_t=alpha_t,
            simulations=config.power_simulations,
            seed=config.seed,
        )
        c.power_alpha = alpha_t
    return c.power


@dataclass
class RoundLog:
    trial: str
    round_id: str
    notes: list[str] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    abstained: int = 0
    abstain_reasons: dict[str, int] = field(default_factory=dict)


def run_discovery(
    rows: Sequence[ArmEndpointRow],
    ledger: Ledger,
    config: LoopConfig | None = None,
    *,
    agent_routes: dict[str, str] | None = None,
    max_trials: int | None = None,
    fit_fn: Callable[[MBMAData, FitSettings], Posterior] = fit,
    converged_fn: Callable[[Posterior], bool] = converged,
) -> list[RoundLog]:
    """Run rounds over held-out trials that still have unspent evidence units."""
    config = config or LoopConfig()
    routes = dict(agent_routes or {})
    rng = np.random.default_rng(config.seed + ledger.next_test_index())
    consumed = ledger.consumed_units()

    pending: dict[str, dict[str, list[Unit]]] = {}
    for instrument in config.instruments:
        full = build_dataset(rows, instrument, agent_routes=routes)
        for unit in evidence_units(full, config.families):
            if unit.key not in consumed:
                pending.setdefault(unit.trial, {}).setdefault(instrument, []).append(unit)

    trials = sorted(pending)
    order = [trials[i] for i in rng.permutation(len(trials))]
    logs: list[RoundLog] = []
    for trial in order[:max_trials]:
        round_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{trial}"
        log = RoundLog(trial=trial, round_id=round_id)
        # Frozen for the round and blind to this trial's own earlier results, so
        # nothing chosen for it can depend on its data (even when new claim
        # families reach a trial that earlier rounds already tested).
        policy = ThompsonPolicy(ledger.arm_stats(exclude_trial=trial), rng)
        discoveries_at_start = ledger.discoveries(exclude_trial=trial)
        rewards: list[tuple[str, float]] = []

        work: list[tuple[Unit, list[Candidate]]] = []
        for instrument, units in sorted(pending[trial].items()):
            train = build_dataset(
                rows, instrument, drop=[(trial, True), (trial, False)], agent_routes=routes
            )
            posterior = fit_fn(train, config.fit_settings)
            if not converged_fn(posterior):
                log.notes.append(f"{instrument}: held-out fit did not converge; units left unspent")
                continue
            work.extend((unit, _candidates(posterior, unit, config, routes)) for unit in units)

        # Most promising units first (earlier tests get larger e-LOND levels);
        # the ranking uses only the held-out model.
        opening = elond_level(config.alpha, ledger.next_test_index(), discoveries_at_start)
        rank = {
            unit.key: max(
                (
                    _power(unit, c, opening, config)
                    for c in candidates
                    if c.belief >= config.belief_threshold
                ),
                default=0.0,
            )
            for unit, candidates in work
        }
        work.sort(key=lambda item: (-rank[item[0].key], item[0].key))

        for unit, candidates in work:
            planned_alpha = elond_level(
                config.alpha, ledger.next_test_index(), discoveries_at_start
            )
            believed = [c for c in candidates if c.belief >= config.belief_threshold]
            for c in believed:
                _power(unit, c, planned_alpha, config)
            eligible = [c for c in believed if (c.power or 0.0) >= config.min_power]
            if not eligible:
                reason = "low belief" if not believed else "low predicted power"
                best = max(believed or candidates, key=lambda c: c.belief, default=None)
                family = (
                    best.family if best else (SUPERIORITY if unit.kind == "control" else CONTRAST)
                )
                ledger.record_hypothesis(
                    family=family,
                    statement=_statement(unit, best)
                    if best
                    else f"{unit.key}: no scorable template",
                    spec={**_spec(unit, None, family), "abstained": reason},
                    tier=1,
                    status="abstained",
                    belief=best.belief if best else None,
                )
                log.abstained += 1
                log.abstain_reasons[reason] = log.abstain_reasons.get(reason, 0) + 1
                continue
            by_arm = {c.arm: c for c in eligible}
            arm, _samples = policy.choose(sorted(by_arm))
            chosen = by_arm[arm]
            x_obs, y_obs = chosen.sides(unit)
            r_x = _responders(x_obs, chosen.threshold)
            r_y = _responders(y_obs, chosen.threshold)
            assert r_x is not None and r_y is not None
            alt_x, alt_y = chosen.alternative(config.mixture_draws)
            log_e = float(
                mixture_log_e(
                    r_x,
                    x_obs.n,
                    r_y,
                    y_obs.n,
                    alt_active=alt_x,
                    alt_control=alt_y,
                    margin=chosen.margin,
                    ratio=chosen.ratio,
                )[0]
            )
            t = ledger.next_test_index()
            alpha_t = elond_level(config.alpha, t, ledger.discoveries())
            discovery = is_discovery(log_e, alpha_t)
            supported = log_e >= EVIDENCE_REWARD_LOG_E
            # A low e-value means no evidence, not that the claim is false.
            status = "discovery" if discovery else ("evidence" if supported else "inconclusive")
            statement = _statement(unit, chosen)
            hypothesis_id = ledger.record_hypothesis(
                family=chosen.family,
                statement=statement,
                spec=_spec(unit, chosen, chosen.family),
                tier=1,
                status="proposed",
                belief=chosen.belief,
            )
            r_arm = _responders(unit.arm_obs, chosen.threshold)
            r_comparator = _responders(unit.comparator_obs, chosen.threshold)
            predicted_arm, predicted_comparator = chosen.predicted()
            if unit.kind == "control":
                observed = {
                    "responders_active": r_arm,
                    "n_active": unit.arm_obs.n,
                    "responders_control": r_comparator,
                    "n_control": unit.comparator_obs.n,
                }
                predicted: dict[str, Any] = {
                    "active": predicted_arm,
                    "control": predicted_comparator,
                }
            else:
                observed = {
                    "responders_more_intensive": r_arm,
                    "n_more_intensive": unit.arm_obs.n,
                    "responders_less_intensive": r_comparator,
                    "n_less_intensive": unit.comparator_obs.n,
                }
                predicted = {
                    "more_intensive": predicted_arm,
                    "less_intensive": predicted_comparator,
                }
            predicted |= {
                "belief": chosen.belief,
                "power": chosen.power,
                "planned_alpha": planned_alpha,
                "mixture_draws": len(alt_x),
            }
            ledger.record_test(
                hypothesis_id=hypothesis_id,
                t=t,
                unit_key=unit.key,
                round_id=round_id,
                trial=unit.trial,
                arm=arm,
                log_e=log_e,
                alpha_t=alpha_t,
                discovery=discovery,
                status=status,
                observed=observed,
                predicted=predicted,
            )
            rewards.append((arm, 1.0 if supported else 0.0))
            log.tests.append(
                {
                    "t": t,
                    "family": chosen.family,
                    "statement": statement,
                    "belief": round(chosen.belief, 3),
                    "power": round(chosen.power or 0.0, 3),
                    "log10_e": round(log_e / math.log(10), 2),
                    "threshold_log10_e": round(-math.log10(alpha_t), 2),
                    "status": status,
                }
            )
        ledger.record_policy_events(round_id, trial, rewards)
        logs.append(log)
    return logs
