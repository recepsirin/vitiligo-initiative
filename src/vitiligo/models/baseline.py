"""Simple baselines the scenario model has to beat.

A Bayesian model-based meta-analysis is only worth its complexity if it
predicts better than the obvious thing. The obvious thing here is: take the
held-out trial's own control arm, add the effect the same route of drug has
had in other trials, and stop. These baselines make that comparison possible.

Three of them, in rising order of what they assume:

``pooled_rate``
    Ignore the trial's control arm. Pool the response rates other trials
    reported for the same route and threshold. This is what you would guess
    knowing only the drug class.
``placebo_anchored``
    Anchor on the held-out trial's own control arm at that week and
    threshold, and add the pooled log-odds difference between active and
    control arms in other trials. No time course: an effect seen at week 12
    counts the same as one seen at week 52.
``placebo_anchored_time``
    The same, with the pooled difference regressed on log(week), so the
    effect is allowed to grow with time.

Everything is on the **log-odds** scale, which keeps rates inside (0, 1) and
needs nothing beyond NumPy (the scenario model works on the probit scale and
needs SciPy and PyMC). Observed proportions use the Jeffreys correction
``(r + 0.5) / (n + 1)``, because control arms at week 24 are often zero and
``logit(0)`` is undefined.

Each prediction is an interval for the *observed* rate in an arm of the given
size, formed exactly as the scenario model forms its own: quantiles of
binomial draws around the predicted probability. A baseline **abstains**
(returns ``None``) rather than guessing when it has too little to pool from,
so a comparison must be read together with how many points each method could
predict at all.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from vitiligo.models.jak_mbma import _EXCLUDING_FLAGS, DESIGN_ANNOTATIONS
from vitiligo.reports.jak_arms import ArmEndpointRow

DRAWS = 20_000

# Pooling needs a spread, so one observation is never enough; the time
# variant also has to estimate a slope.
MIN_POOL = 2
MIN_POOL_TIME = 3


def jeffreys_rate(responders: int, n: int) -> float:
    """``(r + 0.5) / (n + 1)``: a proportion that is never exactly 0 or 1."""
    if n <= 0:
        raise ValueError("n must be positive")
    return (responders + 0.5) / (n + 1)


def logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def expit(x: np.ndarray) -> np.ndarray:
    """Logistic function, computed so that large |x| cannot overflow."""
    values = np.asarray(x, dtype=float)
    out = np.empty_like(values)
    positive = values >= 0
    out[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    below = np.exp(values[~positive])
    out[~positive] = below / (1.0 + below)
    return out


@dataclass(frozen=True)
class Observed:
    """One arm's reported result at a week and threshold."""

    responders: int
    n: int

    @property
    def rate(self) -> float:
        return jeffreys_rate(self.responders, self.n)


@dataclass(frozen=True)
class EffectSample:
    """One trial's log-odds difference between an active arm and its own control."""

    trial: str
    week: int
    delta: float


@dataclass(frozen=True)
class Prediction:
    """Predicted observed rate, in the same shape as the scenario model's interval."""

    method: str
    mean: float
    median: float
    lo80: float
    hi80: float
    lo95: float
    hi95: float
    pooled_from: int
    pool_level: str = "route"  # route | any_route (the fallback that was needed)

    def covers80(self, observed: float) -> bool:
        return self.lo80 <= observed <= self.hi80

    def covers95(self, observed: float) -> bool:
        return self.lo95 <= observed <= self.hi95


def _interval(
    method: str, draws: np.ndarray, pooled_from: int, pool_level: str = "route"
) -> Prediction:
    median, lo80, hi80, lo95, hi95 = np.quantile(draws, [0.5, 0.1, 0.9, 0.025, 0.975])
    return Prediction(
        method=method,
        mean=float(np.mean(draws)),
        median=float(median),
        lo80=float(lo80),
        hi80=float(hi80),
        lo95=float(lo95),
        hi95=float(hi95),
        pooled_from=pooled_from,
        pool_level=pool_level,
    )


def usable(row: ArmEndpointRow, instrument: str) -> bool:
    """Rows the scenario model fits, by the same rules, so the comparison is fair.

    Mirrors ``build_dataset`` and ``_held_out_points``: no switched-treatment or
    extension arms, no as-observed rows, nothing past a trial's annotated
    maximum week, and counts present.
    """
    if row.instrument != instrument or row.week is None or row.threshold is None:
        return False
    if _EXCLUDING_FLAGS.intersection(row.flags) or "population:as_observed" in row.flags:
        return False
    if row.responders is None or not row.n_analyzed:
        return False
    annotation = DESIGN_ANNOTATIONS.get(row.source_id)
    return not (
        annotation and row.week > annotation["max_week"] and "from_publication" not in row.flags
    )


def control_rates(
    rows: Sequence[ArmEndpointRow], instrument: str
) -> dict[tuple[str, int, int], Observed]:
    """Each trial's control arm by (trial, threshold, week).

    A trial with several control rows for one cell (different assessors) keeps
    the largest, which is the fullest analysis population.
    """
    out: dict[tuple[str, int, int], Observed] = {}
    for row in rows:
        if row.arm_role != "placebo" or not usable(row, instrument):
            continue
        assert row.threshold is not None and row.week is not None and row.responders is not None
        assert row.n_analyzed is not None
        key = (row.source_id, row.threshold, row.week)
        current = out.get(key)
        if current is None or row.n_analyzed > current.n:
            out[key] = Observed(row.responders, row.n_analyzed)
    return out


def _route_of(row: ArmEndpointRow, agent_routes: dict[str, str]) -> str | None:
    return agent_routes.get(row.arm_agent or "", row.route)


def effect_samples(
    rows: Sequence[ArmEndpointRow],
    controls: dict[tuple[str, int, int], Observed],
    *,
    instrument: str,
    route: str | None,
    threshold: int,
    exclude_trial: str,
    agent_routes: dict[str, str],
) -> list[EffectSample]:
    """Active-vs-own-control log-odds differences from every *other* trial.

    One sample per active arm that has a control arm in its own trial at the
    same week and threshold.
    """
    samples: list[EffectSample] = []
    for row in rows:
        if row.arm_role != "active" or row.source_id == exclude_trial:
            continue
        if not usable(row, instrument) or row.threshold != threshold:
            continue
        if route is not None and _route_of(row, agent_routes) != route:
            continue
        assert row.week is not None and row.responders is not None and row.n_analyzed is not None
        control = controls.get((row.source_id, threshold, row.week))
        if control is None:
            continue
        active = jeffreys_rate(row.responders, row.n_analyzed)
        samples.append(
            EffectSample(
                trial=row.source_id,
                week=row.week,
                delta=logit(active) - logit(control.rate),
            )
        )
    return samples


def active_rates(
    rows: Sequence[ArmEndpointRow],
    *,
    instrument: str,
    route: str | None,
    threshold: int,
    week: int,
    exclude_trial: str,
    agent_routes: dict[str, str],
) -> list[float]:
    """Log-odds of the rates other trials reported for this route, threshold and week."""
    out = []
    for row in rows:
        if row.arm_role != "active" or row.source_id == exclude_trial:
            continue
        if not usable(row, instrument) or row.threshold != threshold or row.week != week:
            continue
        if route is not None and _route_of(row, agent_routes) != route:
            continue
        assert row.responders is not None and row.n_analyzed is not None
        out.append(logit(jeffreys_rate(row.responders, row.n_analyzed)))
    return out


def _t_draws(mean: float, scale: float, df: int, rng: np.random.Generator) -> np.ndarray:
    """Predictive draws for a new observation: mean + scale * t_df."""
    return mean + scale * rng.standard_t(df, size=DRAWS)


def _observed_rate_draws(p: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """Binomial sampling noise around predicted probabilities, as the model does."""
    return np.asarray(rng.binomial(n, np.clip(p, 0.0, 1.0)), dtype=float) / n


def predict_pooled_rate(
    rates_logit: Sequence[float], n: int, rng: np.random.Generator, pool_level: str = "route"
) -> Prediction | None:
    """Pool other trials' rates for this route, threshold and week. No trial anchor."""
    m = len(rates_logit)
    if m < MIN_POOL:
        return None
    values = np.asarray(rates_logit, dtype=float)
    spread = float(np.std(values, ddof=1)) * math.sqrt(1 + 1 / m)
    draws = _observed_rate_draws(
        expit(_t_draws(float(np.mean(values)), spread, m - 1, rng)), n, rng
    )
    return _interval("pooled_rate", draws, m, pool_level)


def predict_placebo_anchored(
    control: Observed,
    effects: Sequence[EffectSample],
    n: int,
    rng: np.random.Generator,
    pool_level: str = "route",
) -> Prediction | None:
    """The trial's own control arm plus the pooled effect of this route."""
    m = len(effects)
    if m < MIN_POOL:
        return None
    deltas = np.asarray([e.delta for e in effects], dtype=float)
    spread = float(np.std(deltas, ddof=1)) * math.sqrt(1 + 1 / m)
    effect = _t_draws(float(np.mean(deltas)), spread, m - 1, rng)
    draws = _observed_rate_draws(expit(logit(control.rate) + effect), n, rng)
    return _interval("placebo_anchored", draws, m, pool_level)


def fits_a_time_trend(effects: Sequence[EffectSample]) -> bool:
    """Whether a slope in log(week) can be estimated: enough arms, over enough weeks."""
    return len(effects) >= MIN_POOL_TIME and len({e.week for e in effects}) >= 2


def predict_placebo_anchored_time(
    control: Observed,
    effects: Sequence[EffectSample],
    week: int,
    n: int,
    rng: np.random.Generator,
    pool_level: str = "route",
) -> Prediction | None:
    """As ``placebo_anchored``, with the pooled effect regressed on log(week)."""
    if not fits_a_time_trend(effects):
        return None
    m = len(effects)
    x = np.log(np.asarray([e.week for e in effects], dtype=float))
    y = np.asarray([e.delta for e in effects], dtype=float)
    x_bar = float(np.mean(x))
    sxx = float(np.sum((x - x_bar) ** 2))
    slope = float(np.sum((x - x_bar) * (y - np.mean(y))) / sxx)
    intercept = float(np.mean(y) - slope * x_bar)
    residual_var = float(np.sum((y - (intercept + slope * x)) ** 2) / (m - 2))
    x0 = math.log(week)
    scale = math.sqrt(max(residual_var, 0.0) * (1 + 1 / m + (x0 - x_bar) ** 2 / sxx))
    effect = _t_draws(intercept + slope * x0, scale, m - 2, rng)
    draws = _observed_rate_draws(expit(logit(control.rate) + effect), n, rng)
    return _interval("placebo_anchored_time", draws, m, pool_level)


def metrics(scored: Sequence[tuple[Prediction, float]]) -> dict[str, Any]:
    """Coverage and mean absolute error, as the scenario model's back-tests report them."""
    if not scored:
        return {"points": 0}
    return {
        "points": len(scored),
        "coverage80": round(sum(p.covers80(o) for p, o in scored) / len(scored), 3),
        "coverage95": round(sum(p.covers95(o) for p, o in scored) / len(scored), 3),
        "mean_abs_error_pp": round(100 * float(np.mean([abs(p.median - o) for p, o in scored])), 2),
    }


def paired_error_difference(
    errors: Sequence[tuple[str, float, float]],
    rng: np.random.Generator,
    *,
    resamples: int = 4000,
) -> dict[str, Any]:
    """Mean of (baseline error - model error) in points, with a bootstrap interval.

    ``errors`` holds ``(trial, baseline_abs_error, model_abs_error)`` per point.
    Points from one trial share its patients and design, so the bootstrap
    resamples **trials**, not points: treating points as independent would make
    the interval far too narrow. A positive mean means the model is closer.
    """
    if not errors:
        return {"points": 0}
    by_trial: dict[str, list[float]] = {}
    for trial, baseline_err, model_err in errors:
        by_trial.setdefault(trial, []).append(100 * (baseline_err - model_err))
    trials = list(by_trial)
    observed = float(np.mean([d for diffs in by_trial.values() for d in diffs]))
    draws = []
    for _ in range(resamples):
        picked = rng.choice(len(trials), size=len(trials), replace=True)
        pooled = [d for i in picked for d in by_trial[trials[i]]]
        draws.append(float(np.mean(pooled)))
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {
        "points": len(errors),
        "trials": len(trials),
        "mean_difference_pp": round(observed, 2),
        "ci95_pp": [round(float(lo), 2), round(float(hi), 2)],
        "favours": "model" if observed > 0 else "baseline",
        "separates_from_zero": bool(lo > 0 or hi < 0),
    }
