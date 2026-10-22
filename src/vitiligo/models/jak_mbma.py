"""Bayesian model-based meta-analysis (MBMA) of JAK inhibitor response in vitiligo.

Scenario model v0, fitted to the harmonized arm table (``vitiligo report
jak-arms``). It answers questions such as "what share of patients reach
F-VASI75 at week 52 on ritlecitinib 50 mg once daily?" with uncertainty.

Structure — an ordered-probit model, the form NICE uses for PASI50/75/90 in
psoriasis network meta-analyses, applied to VASI thresholds:

    P(improvement >= k | arm a, trial t, week w)
        = Phi(mu_t + pi * (h(w) - 1) + D_a * h(w) - c_k)

- ``c_k``: cut-points shared by all trials, one per VASI threshold k
  (anchored at c_50 = 0), so data at one threshold inform the others;
- ``mu_t``: trial baseline (placebo/vehicle response) at week 24, partially
  pooled across *controlled* trials; trials without a control arm get their own
  unpooled baseline, so they inform time course and within-trial contrasts but
  not the absolute size of drug effects; ``pi`` lets the placebo response move
  along the same saturating time course as the drug effect;
- ``D_a`` (active arms only) = alpha_agent + beta_agent * log(daily dose /
  reference dose) + lambda * loading_dose + phi * phototherapy + eps_a, with
  agents partially pooled towards a route-specific class mean (oral vs
  topical), so an agent with little data borrows strength from agents given
  the same way, and an unseen agent gets that route's class prediction;
- ``h(w) = [w / (w + T50)] * [(24 + T50) / 24]`` (= 1 at week 24): response
  builds with time, with a half-time T50 per route (oral vs topical) — v0.1's
  class-wide T50 over-predicted topical ruxolitinib from week 24 to 52. A
  control arm follows the time course of its trial's route.

Thresholds within the same arm and week are nested (an F-VASI90 responder is
also an F-VASI75 responder), so the likelihood is a chain of conditional
binomials — equivalent to the multinomial over response bands.

This is a research model: every prediction carries its uncertainty, and the
back-tests in this module measure how well it predicts data it has not seen.
It is not a basis for treatment decisions.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import warnings
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from vitiligo.reports.jak_arms import ArmEndpointRow

REFERENCE_WEEK = 24

# Expert-reviewable design annotations the registry fields cannot express.
# Each caps a trial's usable weeks; the reason is reported with every fit.
DESIGN_ANNOTATIONS: dict[str, dict[str, Any]] = {
    "NCT03099304": {
        "max_week": 24,
        "reason": (
            "After week 24 arms were re-assigned (registry arm labels such as 'Vehicle/"
            "Ruxolitinib Cream 0.15% QD to 0.5% QD: 1.5% BID'), so arms observed later are "
            "selected subsets, not the randomized population."
        ),
    },
}
_EXCLUDING_FLAGS = frozenset({"treatment_changes_within_arm", "extension_study"})
_FREQUENCY_MULTIPLIER = {"QD": 1.0, "BID": 2.0, None: 1.0}

# Weakly informative priors on the probit scale (documented in the output).
PRIORS: dict[str, str] = {
    "mu0 (mean trial baseline)": "Normal(-1.5, 1.0)",
    "sigma_mu (between-trial baseline SD)": "HalfNormal(1.0)",
    "pi (placebo drift along h(w), zero at week 24)": "Normal(0, 1.0)",
    "baseline of uncontrolled trials (unpooled)": "Normal(-1.5, 2.5)",
    "cut-point gaps": "HalfNormal(1.5)",
    "alpha_route (class effect at reference dose, per route)": "Normal(1.0, 1.0)",
    "omega_alpha (between-agent SD)": "HalfNormal(0.5)",
    "beta_class (log-dose slope)": "Normal(0.3, 0.3)",
    "omega_beta (between-agent slope SD)": "HalfNormal(0.3)",
    "lambda (loading dose)": "Normal(0, 0.5)",
    "phi (phototherapy)": "Normal(0, 0.5)",
    "tau (between-arm SD)": "HalfNormal(0.3)",
    "T50 per route (weeks to half of week-infinity effect)": "LogNormal(log 20, 0.7)",
}


# ----------------------------------------------------------------------- data


@dataclass(frozen=True)
class ArmInfo:
    source_id: str
    label: str
    active: bool
    agent: str | None
    daily_dose: float | None
    dose_unit: str | None
    loading: bool
    phototherapy: bool
    loading_dose: float | None = None


@dataclass(frozen=True)
class Observation:
    """Cumulative responders at increasing thresholds for one arm at one week."""

    arm: int
    week: int
    n: int
    thresholds: tuple[int, ...]
    responders: tuple[int, ...]


@dataclass
class MBMAData:
    instrument: str
    thresholds: list[int]
    trials: list[str]
    arms: list[ArmInfo]
    agents: list[str]
    reference_dose: dict[str, float]
    observations: list[Observation]
    agent_route: dict[str, str] = field(default_factory=dict)
    excluded: dict[str, int] = field(default_factory=dict)
    trial_phase3: dict[str, bool] = field(default_factory=dict)  # used by v0.3

    def summary(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "thresholds": self.thresholds,
            "trials": self.trials,
            "agents": self.agents,
            "reference_dose": self.reference_dose,
            "agent_route": self.agent_route,
            "controlled_trials": self.controlled_trials(),
            "arms": len(self.arms),
            "active_arms": sum(a.active for a in self.arms),
            "observations": len(self.observations),
            "weeks": sorted({o.week for o in self.observations}),
            "excluded_rows": self.excluded,
            "design_annotations": {t: a for t, a in DESIGN_ANNOTATIONS.items() if t in self.trials},
        }

    def controlled_trials(self) -> list[str]:
        """Trials with a placebo/vehicle arm in the data."""
        return sorted({a.source_id for a in self.arms if not a.active})


def daily_dose(dose_value: float | None, frequency: str | None) -> float | None:
    if dose_value is None:
        return None
    return dose_value * _FREQUENCY_MULTIPLIER.get(frequency, 1.0)


def build_dataset(
    rows: Sequence[ArmEndpointRow],
    instrument: str = "F-VASI",
    *,
    max_week: int | None = None,
    drop: Sequence[tuple[str, bool]] = (),
    agent_routes: dict[str, str] | None = None,
    trial_phase3: dict[str, bool] | None = None,
) -> MBMAData:
    """Select and shape model-ready rows for one instrument (F-VASI or T-VASI).

    ``drop`` removes (source_id, active) groups — used by the back-tests to hold
    out a trial's active arms while keeping its control arm. ``agent_routes``
    (e.g. from the atlas agent summaries) supplies an agent's route when its
    arms here do not state one; otherwise the arms' most common route is used.
    """
    excluded: dict[str, int] = {}

    def skip(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    # Prefer central readings where a trial reports both central and local.
    central_trials = {
        r.source_id for r in rows if r.instrument == instrument and r.assessor == "central"
    }

    selected: list[ArmEndpointRow] = []
    for r in rows:
        if r.instrument != instrument or r.threshold is None:
            continue
        if _EXCLUDING_FLAGS.intersection(r.flags):
            skip("treatment switch or extension study")
            continue
        if r.arm_role not in ("active", "placebo"):
            skip("arm role")
            continue
        if "population:as_observed" in r.flags:
            skip("as-observed population (not comparable with non-responder imputation)")
            continue
        if r.week is None or not r.n_analyzed or r.responders is None:
            skip("week, n or responders missing")
            continue
        if r.source_id in central_trials and r.assessor != "central":
            skip("local read where central exists")
            continue
        if r.arm_role == "active" and (r.arm_agent is None or r.dose_value is None):
            skip("active arm without agent or dose")
            continue
        if max_week is not None and r.week > max_week:
            skip("beyond max_week")
            continue
        annotation = DESIGN_ANNOTATIONS.get(r.source_id)
        # The cap covers registry rows; curated paper rows are for arms the paper
        # reports as continuous from day 1.
        if annotation and r.week > annotation["max_week"] and "from_publication" not in r.flags:
            skip("design annotation: post-randomization selection")
            continue
        if (r.source_id, r.arm_role == "active") in drop:
            skip("held out")
            continue
        selected.append(r)

    arm_index: dict[tuple[Any, ...], int] = {}
    arms: list[ArmInfo] = []
    cells: dict[tuple[int, int], dict[int, tuple[int, int]]] = {}
    for r in selected:
        active = r.arm_role == "active"
        dose = daily_dose(r.dose_value, r.frequency) if active else None
        loading = r.loading_dose_value is not None
        key = (
            r.source_id,
            active,
            r.arm_agent,
            dose,
            r.dose_unit,
            r.loading_dose_value,  # 200->50 mg and 100->50 mg are different arms
            r.phototherapy,
        )
        if key not in arm_index:
            arm_index[key] = len(arms)
            arms.append(
                ArmInfo(
                    source_id=r.source_id,
                    label=r.arm_label,
                    active=active,
                    agent=r.arm_agent if active else None,
                    daily_dose=dose,
                    dose_unit=r.dose_unit if active else None,
                    loading=loading,
                    phototherapy=r.phototherapy,
                    loading_dose=r.loading_dose_value,
                )
            )
        assert r.threshold is not None and r.week is not None and r.n_analyzed is not None
        assert r.responders is not None
        cell = cells.setdefault((arm_index[key], r.week), {})
        # Reported twice: keep the first (duplicates were checked to agree).
        cell.setdefault(r.threshold, (r.responders, r.n_analyzed))

    observations: list[Observation] = []
    for (arm, week), by_threshold in sorted(cells.items()):
        thresholds = tuple(sorted(by_threshold))
        n = by_threshold[thresholds[0]][1]
        responders: list[int] = []
        for k in thresholds:
            r_k = min(by_threshold[k][0], n)
            if responders:
                r_k = min(r_k, responders[-1])  # nested thresholds cannot increase
            responders.append(r_k)
        observations.append(Observation(arm, week, n, thresholds, tuple(responders)))

    agents = sorted({a.agent for a in arms if a.agent})
    route_votes: dict[str, list[str]] = {}
    for r in selected:
        if r.arm_role == "active" and r.arm_agent and r.route:
            route_votes.setdefault(r.arm_agent, []).append(r.route)
    agent_route = {
        agent: (
            max(set(route_votes[agent]), key=route_votes[agent].count)
            if agent in route_votes
            else (agent_routes or {}).get(agent, "unknown")
        )
        for agent in agents
    }
    reference = {
        agent: max(a.daily_dose for a in arms if a.agent == agent and a.daily_dose is not None)
        for agent in agents
    }
    return MBMAData(
        instrument=instrument,
        thresholds=sorted({k for o in observations for k in o.thresholds}),
        trials=sorted({a.source_id for a in arms}),
        arms=arms,
        agents=agents,
        reference_dose=reference,
        observations=observations,
        excluded=excluded,
        agent_route=agent_route,
        trial_phase3={
            t: bool((trial_phase3 or {}).get(t, False)) for t in sorted({a.source_id for a in arms})
        },
    )


# ---------------------------------------------------------------------- model


@dataclass
class FitSettings:
    draws: int = 1500
    tune: int = 2000
    chains: int = 4
    target_accept: float = 0.99  # 0.95 left a few divergences in the hierarchy
    random_seed: int = 20261014
    version: str = (
        "v0.2"  # "v0.3": trial-by-treatment and phase 3 effects; "v0.5": also per-route baselines
    )


@dataclass
class Posterior:
    """Flattened posterior draws plus the data layout needed to predict."""

    data: MBMAData
    draws: dict[str, np.ndarray]
    diagnostics: dict[str, float]

    def cutpoint(self, threshold: int) -> np.ndarray:
        if threshold not in self.data.thresholds:
            raise ValueError(
                f"threshold {threshold} not in fitted thresholds {self.data.thresholds}"
            )
        return self.draws["cut"][:, self.data.thresholds.index(threshold)]


def _h(week: Any, t50: Any) -> Any:
    return (week / (week + t50)) * ((REFERENCE_WEEK + t50) / REFERENCE_WEEK)


def fit(data: MBMAData, settings: FitSettings | None = None) -> Posterior:
    """Fit the ordered-probit MBMA with PyMC (``pip install -e '.[model]'``)."""
    try:
        with _quiet_sampler():  # import-time configuration chatter
            import arviz as az
            import pymc as pm
            import pytensor.tensor as pt
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "The scenario model needs the optional 'model' extra: pip install -e '.[model]'"
        ) from exc

    settings = settings or FitSettings()
    if 50 not in data.thresholds:
        raise ValueError("The cut-points are anchored at threshold 50, which has no data.")
    thresholds = data.thresholds
    anchor = thresholds.index(50)
    agent_idx = {a: i for i, a in enumerate(data.agents)}
    trial_idx = {t: i for i, t in enumerate(data.trials)}
    active_arms = [i for i, a in enumerate(data.arms) if a.active]
    active_pos = {arm: j for j, arm in enumerate(active_arms)}

    # Per-arm covariates (placebo arms get zeros; their effect is masked out).
    arm_trial = np.array([trial_idx[a.source_id] for a in data.arms])
    arm_active = np.array([a.active for a in data.arms], dtype=float)
    arm_agent = np.array([agent_idx[a.agent] if a.agent else 0 for a in data.arms])
    arm_logdose = np.array(
        [
            math.log(a.daily_dose / data.reference_dose[a.agent])
            if a.active and a.agent and a.daily_dose
            else 0.0
            for a in data.arms
        ]
    )
    arm_loading = np.array([float(a.loading) for a in data.arms])
    arm_photo = np.array([float(a.phototherapy) for a in data.arms])
    arm_eps = np.array([active_pos.get(i, 0) for i in range(len(data.arms))])
    routes = sorted(set(data.agent_route.values())) or ["unknown"]
    agent_route_idx = np.array([routes.index(data.agent_route[a]) for a in data.agents] or [0])
    controlled = set(data.controlled_trials())
    trial_controlled = np.array([t in controlled for t in data.trials])
    trial_route = np.array([routes.index(_trial_route(data, t, routes)) for t in data.trials])
    trial_phase3 = np.array([float(data.trial_phase3.get(t, False)) for t in data.trials])
    v03 = settings.version in ("v0.3", "v0.5")
    route_baseline = settings.version == "v0.5"
    if settings.version not in ("v0.2", "v0.3", "v0.5"):
        raise ValueError(f"unknown model version {settings.version!r}")

    # Flatten the conditional-binomial chain: one step per (observation, threshold).
    step_obs, step_thr, step_prev, step_n, step_r = [], [], [], [], []
    for o_i, obs in enumerate(data.observations):
        prev_r = obs.n
        for j, (k, r_k) in enumerate(zip(obs.thresholds, obs.responders, strict=True)):
            step_obs.append(o_i)
            step_thr.append(thresholds.index(k))
            step_prev.append(thresholds.index(obs.thresholds[j - 1]) if j else -1)
            step_n.append(prev_r)
            step_r.append(r_k)
            prev_r = r_k
    obs_arm = np.array([o.arm for o in data.observations])
    obs_week = np.array([float(o.week) for o in data.observations])
    s_obs, s_thr = np.array(step_obs), np.array(step_thr)
    s_prev = np.array(step_prev)
    has_prev = s_prev >= 0

    with pm.Model():
        sigma_mu = pm.HalfNormal("sigma_mu", 1.0)
        mu_z = pm.Normal("mu_z", 0.0, 1.0, shape=len(data.trials))
        if route_baseline:
            # v0.5: oral placebo and topical vehicle trials get separate baseline means.
            mu0_route = pm.Normal("mu0_route", -1.5, 1.0, shape=len(routes))
            pm.Deterministic("mu0", pt.mean(mu0_route))
            mean_baseline = mu0_route[trial_route]
        else:
            mean_baseline = pm.Normal("mu0", -1.5, 1.0)
        # Uncontrolled trials: wide, unpooled baseline (no borrowing either way).
        mu = pm.Deterministic(
            "mu", pt.where(trial_controlled, mean_baseline + sigma_mu * mu_z, -1.5 + 2.5 * mu_z)
        )
        drift = pm.Normal("pi", 0.0, 1.0)

        gaps = pm.HalfNormal("gaps", 1.5, shape=len(thresholds) - 1)
        cuts = []
        for j in range(len(thresholds)):
            if j == anchor:
                cuts.append(pt.as_tensor_variable(0.0))
            elif j > anchor:
                cuts.append(pt.sum(gaps[anchor:j]))
            else:
                cuts.append(-pt.sum(gaps[j:anchor]))
        cut = pm.Deterministic("cut", pt.stack(cuts))

        alpha_route = pm.Normal("alpha_route", 1.0, 1.0, shape=len(routes))
        omega_alpha = pm.HalfNormal("omega_alpha", 0.5)
        alpha_z = pm.Normal("alpha_z", 0.0, 1.0, shape=max(len(data.agents), 1))
        alpha = pm.Deterministic("alpha", alpha_route[agent_route_idx] + omega_alpha * alpha_z)
        beta_class = pm.Normal("beta_class", 0.3, 0.3)
        omega_beta = pm.HalfNormal("omega_beta", 0.3)
        beta_z = pm.Normal("beta_z", 0.0, 1.0, shape=max(len(data.agents), 1))
        beta = pm.Deterministic("beta", beta_class + omega_beta * beta_z)
        loading = pm.Normal("lambda", 0.0, 0.5)
        photo = pm.Normal("phi", 0.0, 0.5)
        tau = pm.HalfNormal("tau", 0.3)
        eps_z = pm.Normal("eps_z", 0.0, 1.0, shape=max(len(active_arms), 1))
        t50 = pm.LogNormal("T50", math.log(20.0), 0.7, shape=len(routes))

        arm_term = (
            alpha[arm_agent]
            + beta[arm_agent] * arm_logdose
            + loading * arm_loading
            + photo * arm_photo
            + tau * eps_z[arm_eps]
        )
        if v03:
            # Trials differ in how much the drug helps (beyond placebo response),
            # and phase 3 programmes may differ from phase 2 by route.
            sigma_gamma = pm.HalfNormal("sigma_gamma", 0.5)
            gamma_z = pm.Normal("gamma_z", 0.0, 1.0, shape=len(data.trials))
            gamma = pm.Deterministic("gamma", sigma_gamma * gamma_z)
            kappa = pm.Normal("kappa", 0.0, 0.5, shape=len(routes))
            arm_term = (
                arm_term
                + gamma[arm_trial]
                + kappa[trial_route[arm_trial]] * trial_phase3[arm_trial]
            )
        effect = arm_term * arm_active
        h = _h(obs_week, t50[trial_route[arm_trial[obs_arm]]])
        eta = mu[arm_trial[obs_arm]] + drift * (h - 1.0) + effect[obs_arm] * h
        std = pm.Normal.dist(0.0, 1.0)
        log_p = pm.logcdf(std, eta[s_obs] - cut[s_thr])
        log_prev = pm.logcdf(std, eta[s_obs] - cut[np.where(has_prev, s_prev, 0)])
        log_cond = pt.where(has_prev, log_p - log_prev, log_p)
        p_step = pt.clip(pt.exp(log_cond), 1e-12, 1.0 - 1e-12)
        pm.Binomial("responders", n=np.array(step_n), p=p_step, observed=np.array(step_r))

        with _quiet_sampler():
            idata = pm.sample(
                draws=settings.draws,
                tune=settings.tune,
                chains=settings.chains,
                target_accept=settings.target_accept,
                random_seed=settings.random_seed,
                progressbar=False,
            )

    names = [
        "mu0", "sigma_mu", "mu", "pi", "cut", "alpha_route", "omega_alpha", "alpha",
        "beta_class", "omega_beta", "beta", "lambda", "phi", "tau", "T50", "eps_z",
    ]  # fmt: skip
    if v03:
        names += ["sigma_gamma", "gamma", "kappa"]
    if route_baseline:
        names += ["mu0_route"]
    draws: dict[str, np.ndarray] = {}
    for name in names:
        values = np.asarray(idata.posterior[name])
        draws[name] = values.reshape(values.shape[0] * values.shape[1], *values.shape[2:])

    draws["arm_eps_position"] = np.array([active_pos.get(i, -1) for i in range(len(data.arms))])
    draws["routes"] = np.array(routes)
    draws["trial_route"] = trial_route
    draws["trial_phase3"] = trial_phase3
    with _quiet_sampler():  # the fixed c_50 = 0 cut-point has no variance (NaN R-hat)
        rhat = az.rhat(idata, var_names=names)
        ess = az.ess(idata, var_names=names, method="bulk")
    diagnostics = {
        "max_rhat": float(max(np.nanmax(np.asarray(rhat[v])) for v in rhat.data_vars)),
        "min_ess_bulk": float(min(np.nanmin(np.asarray(ess[v])) for v in ess.data_vars)),
        "divergences": float(np.asarray(idata.sample_stats["diverging"]).sum()),
        "draws": float(settings.draws * settings.chains),
    }
    return Posterior(data=data, draws=draws, diagnostics=diagnostics)


@contextlib.contextmanager
def _quiet_sampler() -> Iterator[None]:
    """Silence PyMC / PyTensor / ArviZ console chatter; diagnostics are reported instead."""
    loggers = [logging.getLogger(n) for n in ("pymc", "pytensor", "arviz", "arviz_stats")]
    levels = [lg.level for lg in loggers]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for lg in loggers:
            lg.setLevel(logging.ERROR)
        try:
            yield
        finally:
            for lg, level in zip(loggers, levels, strict=True):
                lg.setLevel(level)


def converged(posterior: Posterior) -> bool:
    d = posterior.diagnostics
    return d["max_rhat"] <= 1.01 and d["min_ess_bulk"] >= 400 and d["divergences"] == 0


# ------------------------------------------------------------------ prediction


@dataclass(frozen=True)
class Scenario:
    agent: str
    dose: float
    dose_unit: str
    frequency: str | None = "QD"
    week: int = REFERENCE_WEEK
    threshold: int = 75
    loading_dose: bool = False
    phototherapy: bool = False
    route: str | None = None  # needed only for agents the model has not seen
    phase3: bool = False  # v0.3: the trial is phase 3


@dataclass
class Interval:
    mean: float
    median: float
    lo80: float
    hi80: float
    lo95: float
    hi95: float

    @classmethod
    def of(cls, values: np.ndarray) -> Interval:
        q = np.quantile(values, [0.5, 0.1, 0.9, 0.025, 0.975])
        return cls(float(np.mean(values)), *(float(x) for x in q))


def _agent_params(
    posterior: Posterior, scenario: Scenario, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, float]:
    """(alpha, beta, reference daily dose) draws for the scenario's agent."""
    d, data = posterior.draws, posterior.data
    size = d["mu0"].shape[0]
    if scenario.agent in data.agents:
        i = data.agents.index(scenario.agent)
        return d["alpha"][:, i], d["beta"][:, i], data.reference_dose[scenario.agent]
    # Unseen agent: draw from its route's class distribution (or, if the route
    # is unknown, from an equal mixture of the fitted routes).
    routes = list(d["routes"])
    if scenario.route in routes:
        route_mean = d["alpha_route"][:, routes.index(scenario.route)]
    else:
        pick = rng.integers(0, len(routes), size)
        route_mean = d["alpha_route"][np.arange(size), pick]
    alpha = route_mean + d["omega_alpha"] * rng.standard_normal(size)
    beta = d["beta_class"] + d["omega_beta"] * rng.standard_normal(size)
    return alpha, beta, daily_dose(scenario.dose, scenario.frequency) or 1.0


def _regimen_effect(
    posterior: Posterior,
    scenario: Scenario,
    params: tuple[np.ndarray, np.ndarray, float],
    rng: np.random.Generator,
    arm: int | None = None,
) -> np.ndarray:
    d = posterior.draws
    alpha, beta, reference = params
    dose = daily_dose(scenario.dose, scenario.frequency) or reference
    position = int(d["arm_eps_position"][arm]) if arm is not None else -1
    if position >= 0:
        eps = d["tau"] * d["eps_z"][:, position]  # this arm's fitted deviation
    else:
        eps = d["tau"] * rng.standard_normal(d["mu0"].shape[0])  # a new arm
    return np.asarray(
        alpha
        + beta * math.log(dose / reference)
        + d["lambda"] * float(scenario.loading_dose)
        + d["phi"] * float(scenario.phototherapy)
        + eps
    )


def _effect(
    posterior: Posterior,
    scenario: Scenario,
    rng: np.random.Generator,
    arm: int | None = None,
) -> np.ndarray:
    params = _agent_params(posterior, scenario, rng)
    return _regimen_effect(posterior, scenario, params, rng, arm)


def _draws(
    posterior: Posterior,
    scenario: Scenario,
    trial: str | None,
    arm: int | None,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    d = posterior.draws
    if trial is not None:
        baseline = d["mu"][:, posterior.data.trials.index(trial)]
    else:
        baseline = _new_baseline(posterior, scenario, rng)
    week = float(scenario.week)
    h = _h(week, _scenario_t50(posterior, scenario, trial, rng))
    base = baseline + d["pi"] * (h - 1.0) - posterior.cutpoint(scenario.threshold)
    effect = (
        _effect(posterior, scenario, rng, arm) + _trial_effect(posterior, scenario, trial, rng)
    ) * h
    return _phi(base + effect), _phi(base)


def _new_baseline(posterior: Posterior, scenario: Scenario, rng: np.random.Generator) -> np.ndarray:
    """A new trial's baseline: from the route's mean in v0.5, the shared mean before."""
    d = posterior.draws
    size = d["mu0"].shape[0]
    z = rng.standard_normal(size)  # first, so earlier versions keep their random stream
    if "mu0_route" not in d:
        return np.asarray(d["mu0"] + d["sigma_mu"] * z)
    routes = list(d["routes"])
    route = posterior.data.agent_route.get(scenario.agent, scenario.route)
    if route in routes:
        idx = np.full(size, routes.index(route))
    else:
        idx = np.asarray(rng.integers(0, len(routes), size))
    return np.asarray(d["mu0_route"][np.arange(size), idx] + d["sigma_mu"] * z)


def _trial_effect(
    posterior: Posterior, scenario: Scenario, trial: str | None, rng: np.random.Generator
) -> np.ndarray | float:
    """v0.3 trial-by-treatment effect plus the phase 3 shift (0 for v0.2 posteriors)."""
    d = posterior.draws
    if "sigma_gamma" not in d:
        return 0.0
    size = d["mu0"].shape[0]
    routes = list(d["routes"])
    if trial is not None:
        i = posterior.data.trials.index(trial)
        gamma = d["gamma"][:, i]
        route_draws = np.full(size, int(d["trial_route"][i]))
        phase3 = float(d["trial_phase3"][i])
    else:
        gamma = d["sigma_gamma"] * rng.standard_normal(size)
        route = posterior.data.agent_route.get(scenario.agent, scenario.route)
        if route in routes:
            route_draws = np.full(size, routes.index(route))
        else:
            route_draws = np.asarray(rng.integers(0, len(routes), size))
        phase3 = float(scenario.phase3)
    return np.asarray(gamma + d["kappa"][np.arange(size), route_draws] * phase3)


def predict_draws(
    posterior: Posterior,
    scenario: Scenario,
    *,
    trial: str | None = None,
    arm: int | None = None,
    seed: int = 7,
) -> tuple[np.ndarray, np.ndarray]:
    """Posterior predictive draws of (active, control) response probabilities."""
    return _draws(posterior, scenario, trial, arm, np.random.default_rng(seed))


def predict_pair_draws(
    posterior: Posterior,
    first: Scenario,
    second: Scenario,
    *,
    seed: int = 7,
) -> tuple[np.ndarray, np.ndarray]:
    """Joint draws of two regimens of one agent in the same *new* trial.

    The arms share the trial baseline, the agent's effect and the time course
    (so their difference reflects dose, loading and phototherapy only) but get
    independent new-arm deviations. Calling ``predict_draws`` twice would
    instead give both arms the same deviation and, for an agent the model has
    not seen, two different agent effects.
    """
    if (first.agent, first.week, first.threshold, first.dose_unit) != (
        second.agent,
        second.week,
        second.threshold,
        second.dose_unit,
    ):
        raise ValueError("both regimens need the same agent, dose unit, week and threshold")
    rng = np.random.default_rng(seed)
    d = posterior.draws
    baseline = _new_baseline(posterior, first, rng)
    h = _h(float(first.week), _scenario_t50(posterior, first, None, rng))
    base = baseline + d["pi"] * (h - 1.0) - posterior.cutpoint(first.threshold)
    params = _agent_params(posterior, first, rng)
    shared = _trial_effect(posterior, first, None, rng)  # one trial: one trial effect
    effect_first = (_regimen_effect(posterior, first, params, rng) + shared) * h
    effect_second = (_regimen_effect(posterior, second, params, rng) + shared) * h
    return _phi(base + effect_first), _phi(base + effect_second)


def predict_trial_draws(
    posterior: Posterior,
    regimens: Sequence[Scenario],
    *,
    seed: int = 7,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Joint draws of a *new* trial: its control arm and any number of regimens of one agent.

    As in ``predict_pair_draws`` (and in the same random order, so two regimens
    give exactly its draws): the arms share the trial baseline, the time course,
    the agent's effect and the trial effect, including any phase 3 shift; each
    regimen gets its own new-arm deviation. Returns (control, [regimen, ...]).
    """
    if not regimens:
        raise ValueError("at least one regimen is needed")
    first = regimens[0]
    for other in regimens[1:]:
        if (other.agent, other.week, other.threshold, other.dose_unit, other.phase3) != (
            first.agent,
            first.week,
            first.threshold,
            first.dose_unit,
            first.phase3,
        ):
            raise ValueError("all regimens need the same agent, dose unit, week, threshold, phase")
    rng = np.random.default_rng(seed)
    d = posterior.draws
    baseline = _new_baseline(posterior, first, rng)
    h = _h(float(first.week), _scenario_t50(posterior, first, None, rng))
    base = baseline + d["pi"] * (h - 1.0) - posterior.cutpoint(first.threshold)
    params = _agent_params(posterior, first, rng)
    shared = _trial_effect(posterior, first, None, rng)  # one trial: one trial effect
    arms = [
        _phi(base + (_regimen_effect(posterior, regimen, params, rng) + shared) * h)
        for regimen in regimens
    ]
    return _phi(base), arms


def predict(
    posterior: Posterior,
    scenario: Scenario,
    *,
    trial: str | None = None,
    arm: int | None = None,
    n_active: int | None = None,
    n_control: int | None = None,
    seed: int = 7,
) -> dict[str, Any]:
    """Predicted response rates for a scenario vs placebo in the same trial.

    ``trial`` conditions on a fitted trial's baseline and ``arm`` on a fitted
    arm's own deviation (back-tests); otherwise a *new* trial's baseline and a
    new arm are drawn from their between-trial / between-arm distributions.
    With ``n_active``/``n_control``, also returns intervals for the observed
    rates of a trial of that size (adds binomial sampling noise).
    """
    rng = np.random.default_rng(seed)
    p_active, p_control = _draws(posterior, scenario, trial, arm, rng)
    result: dict[str, Any] = {
        "scenario": asdict(scenario),
        "conditioned_on_trial": trial,
        "p_active": asdict(Interval.of(p_active)),
        "p_control": asdict(Interval.of(p_control)),
        "difference": asdict(Interval.of(p_active - p_control)),
        "p_active_beats_control": float(np.mean(p_active > p_control)),
        "extrapolation": _extrapolation_notes(posterior, scenario),
    }
    if n_active:
        result["observed_active_rate"] = asdict(
            Interval.of(rng.binomial(n_active, p_active) / n_active)
        )
    if n_control:
        result["observed_control_rate"] = asdict(
            Interval.of(rng.binomial(n_control, p_control) / n_control)
        )
    return result


def _trial_route(data: MBMAData, trial: str, routes: list[str]) -> str:
    """Route of a trial's active arms (most common); first route if it has none."""
    votes = [
        data.agent_route.get(a.agent, "unknown")
        for a in data.arms
        if a.source_id == trial and a.active and a.agent
    ]
    route = max(set(votes), key=votes.count) if votes else routes[0]
    return route if route in routes else routes[0]


def _scenario_t50(
    posterior: Posterior, scenario: Scenario, trial: str | None, rng: np.random.Generator
) -> np.ndarray:
    """T50 draws for the scenario's route; an equal route mixture if the route is unknown."""
    t50 = posterior.draws["T50"]
    routes = list(posterior.draws["routes"])
    if trial is not None:
        return np.asarray(
            t50[:, int(posterior.draws["trial_route"][posterior.data.trials.index(trial)])]
        )
    route = posterior.data.agent_route.get(scenario.agent, scenario.route)
    if route in routes:
        return np.asarray(t50[:, routes.index(route)])
    pick = rng.integers(0, len(routes), t50.shape[0])
    return np.asarray(t50[np.arange(t50.shape[0]), pick])


def _phi(x: np.ndarray) -> np.ndarray:
    from scipy.special import ndtr  # installed with the [model] extra (via PyMC)

    return np.asarray(ndtr(x))


def _extrapolation_notes(posterior: Posterior, scenario: Scenario) -> list[str]:
    data = posterior.data
    notes: list[str] = []
    if scenario.agent not in data.agents:
        route = scenario.route if scenario.route in data.agent_route.values() else "unknown"
        notes.append(
            f"agent has no data: prediction is the {route}-route class prior, very uncertain"
        )
    else:
        doses = sorted(
            {a.daily_dose for a in data.arms if a.agent == scenario.agent and a.daily_dose}
        )
        dose = daily_dose(scenario.dose, scenario.frequency)
        if dose is not None and doses and not (doses[0] <= dose <= doses[-1]):
            notes.append(f"dose outside studied range {doses[0]:g}-{doses[-1]:g}")
        weeks = sorted(
            {o.week for o in data.observations if data.arms[o.arm].agent == scenario.agent}
        )
        if weeks and scenario.week > weeks[-1]:
            notes.append(
                f"week {scenario.week} beyond this agent's data (max week {weeks[-1]}): "
                "relies on its route's time course"
            )
    control_weeks = sorted({o.week for o in data.observations if not data.arms[o.arm].active})
    if control_weeks and scenario.week > control_weeks[-1]:
        notes.append(
            f"placebo/vehicle data end at week {control_weeks[-1]}: control response at "
            f"week {scenario.week} is extrapolated"
        )
    return notes


# ------------------------------------------------------------------ back-tests


@dataclass
class BacktestPoint:
    source_id: str
    arm_label: str
    week: int
    threshold: int
    n: int
    observed: float
    predicted: Interval
    in80: bool
    in95: bool


def _held_out_points(
    rows: Sequence[ArmEndpointRow], instrument: str, keep: Any
) -> list[tuple[ArmEndpointRow, Scenario]]:
    """Active-arm rows selected by ``keep``, with the same filters as ``build_dataset``."""
    central = {r.source_id for r in rows if r.instrument == instrument and r.assessor == "central"}
    points: list[tuple[ArmEndpointRow, Scenario]] = []
    seen: set[tuple[Any, ...]] = set()
    for r in rows:
        if not keep(r) or r.instrument != instrument or r.arm_role != "active":
            continue
        if _EXCLUDING_FLAGS.intersection(r.flags) or r.week is None or r.threshold is None:
            continue
        if "population:as_observed" in r.flags:
            continue  # not fitted (see build_dataset), so not scored either
        if not r.n_analyzed or r.percent is None or r.arm_agent is None or r.dose_value is None:
            continue
        if r.source_id in central and r.assessor != "central":
            continue
        annotation = DESIGN_ANNOTATIONS.get(r.source_id)
        if annotation and r.week > annotation["max_week"] and "from_publication" not in r.flags:
            continue  # excluded from fitting for selection bias, so not scored either
        key = (r.source_id, r.arm_label, r.week, r.threshold)
        if key in seen:
            continue
        seen.add(key)
        scenario = Scenario(
            agent=r.arm_agent,
            dose=r.dose_value,
            dose_unit=r.dose_unit or "",
            frequency=r.frequency,
            week=r.week,
            threshold=r.threshold,
            loading_dose=r.loading_dose_value is not None,
            phototherapy=r.phototherapy,
        )
        points.append((r, scenario))
    return points


def _find_arm(data: MBMAData, row: ArmEndpointRow) -> int | None:
    """Index of the fitted arm with the same regimen as ``row`` (None if absent)."""
    dose = daily_dose(row.dose_value, row.frequency)
    for i, arm in enumerate(data.arms):
        if (
            arm.active
            and arm.source_id == row.source_id
            and arm.agent == row.arm_agent
            and arm.daily_dose == dose
            and arm.loading_dose == row.loading_dose_value
            and arm.phototherapy == row.phototherapy
        ):
            return i
    return None


def _score(
    posterior: Posterior, points: list[tuple[ArmEndpointRow, Scenario]], conditioned: bool
) -> list[BacktestPoint]:
    scored: list[BacktestPoint] = []
    for row, scenario in points:
        if scenario.threshold not in posterior.data.thresholds:
            continue
        trial = row.source_id if conditioned and row.source_id in posterior.data.trials else None
        arm = _find_arm(posterior.data, row) if conditioned else None
        assert row.n_analyzed is not None and row.percent is not None
        pred = predict(posterior, scenario, trial=trial, arm=arm, n_active=row.n_analyzed)
        interval = Interval(**pred["observed_active_rate"])
        observed = row.percent / 100.0
        scored.append(
            BacktestPoint(
                source_id=row.source_id,
                arm_label=row.arm_label,
                week=scenario.week,
                threshold=scenario.threshold,
                n=row.n_analyzed,
                observed=observed,
                predicted=interval,
                in80=interval.lo80 <= observed <= interval.hi80,
                in95=interval.lo95 <= observed <= interval.hi95,
            )
        )
    return scored


def _metrics(points: list[BacktestPoint]) -> dict[str, Any]:
    if not points:
        return {"points": 0}
    return {
        "points": len(points),
        "coverage80": round(sum(p.in80 for p in points) / len(points), 3),
        "coverage95": round(sum(p.in95 for p in points) / len(points), 3),
        "mean_abs_error_pp": round(
            100 * float(np.mean([abs(p.predicted.median - p.observed) for p in points])), 2
        ),
    }


def backtest_leave_one_trial_out(
    rows: Sequence[ArmEndpointRow],
    instrument: str = "F-VASI",
    settings: FitSettings | None = None,
    agent_routes: dict[str, str] | None = None,
    trial_phase3: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Hold out each controlled trial's active arms, keep its control arm, predict them."""
    full = build_dataset(rows, instrument, agent_routes=agent_routes, trial_phase3=trial_phase3)
    controlled = sorted(
        {
            t
            for t in full.trials
            if any(a.source_id == t and not a.active for a in full.arms)
            and any(a.source_id == t and a.active for a in full.arms)
        }
    )
    folds: dict[str, Any] = {}
    all_points: list[BacktestPoint] = []
    for trial in controlled:
        data = build_dataset(
            rows,
            instrument,
            drop=[(trial, True)],
            agent_routes=agent_routes,
            trial_phase3=trial_phase3,
        )
        posterior = fit(data, settings)
        points = _score(
            posterior,
            _held_out_points(rows, instrument, lambda r, t=trial: r.source_id == t),
            conditioned=True,
        )
        all_points.extend(points)
        folds[trial] = {
            "metrics": _metrics(points),
            "converged": converged(posterior),
            "diagnostics": posterior.diagnostics,
            "points": [asdict(p) for p in points],
        }
    return {
        "design": "leave-one-trial-out, control arm kept",
        "overall": _metrics(all_points),
        "all_folds_converged": all(f["converged"] for f in folds.values()),
        "folds": folds,
    }


def backtest_time_extrapolation(
    rows: Sequence[ArmEndpointRow],
    instrument: str = "F-VASI",
    settings: FitSettings | None = None,
    agent_routes: dict[str, str] | None = None,
    trial_phase3: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Fit on data up to week 24 only; predict the later weeks of the same arms."""
    data = build_dataset(
        rows,
        instrument,
        max_week=REFERENCE_WEEK,
        agent_routes=agent_routes,
        trial_phase3=trial_phase3,
    )
    posterior = fit(data, settings)
    points = _score(
        posterior,
        _held_out_points(
            rows, instrument, lambda r: r.week is not None and r.week > REFERENCE_WEEK
        ),
        conditioned=True,
    )
    return {
        "design": f"fit weeks <= {REFERENCE_WEEK}, predict later weeks",
        "overall": _metrics(points),
        "converged": converged(posterior),
        "diagnostics": posterior.diagnostics,
        "points": [asdict(p) for p in points],
    }


# --------------------------------------------------------------------- freeze


def freeze(record: dict[str, Any]) -> dict[str, Any]:
    """Timestamp a forecast and add a SHA-256 of its canonical JSON content."""
    stamped = {"frozen_at": datetime.now(UTC).isoformat(), **record}
    canonical = json.dumps(stamped, sort_keys=True, separators=(",", ":"), default=str)
    return {**stamped, "sha256": hashlib.sha256(canonical.encode()).hexdigest()}
