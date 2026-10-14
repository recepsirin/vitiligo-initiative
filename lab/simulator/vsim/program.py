"""Mechanistic repigmentation programs: spec -> parameters -> responder probabilities.

Patient i in trial t, region g (face for F-VASI, body for T-VASI):

    R_i(w) = 1 - exp(-Lambda_i(w) ** gamma)
    Lambda_i(w) = exp(theta_g + u_t + eta_i) * A(w),   A(w) = integral_tau^w e(s) ds
    eta_i ~ N(0, sigma_g^2),  u_t ~ N(0, sigma_u^2)  (integrated out)

e(s) = 1 on vehicle/placebo and exp(E) on drug, so A(w) is the cumulative
exposure (loading doses act for the first weeks). Responders at threshold k:

    P(R >= k/100) = (1 - q_g) * Phi((theta_g + u_t + log A(w) - c_k / gamma) / sigma_g)

with c_k = log(-log(1 - k/100)) (mechanistic cut-points; F-VASI100 maps to a
fitted ceiling kappa > 0.90), or free ordered cut-points (empirical control).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field, fields, replace

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, gammaln, logsumexp, ndtr

from vsim.data import LOADING_WEEKS, REGION, ArmWeek

THRESHOLDS = (25, 50, 75, 90, 100)
AGENT_SD = 0.75  # between-agent SD of the log-rate effect (fixed, pre-registered)
ROUTES = ("topical", "oral")
LAG_MAX = 3.5
GRID = np.linspace(-6.0, 6.0, 161)  # standard-normal grid for trial effects (step 0.075 SD)
_GRID_LOGW = -0.5 * GRID**2 - 0.5 * math.log(2 * math.pi) + math.log(GRID[1] - GRID[0])
_GRID_LOGW -= logsumexp(_GRID_LOGW)
_EPS = 1e-12

OPTIONS: dict[str, tuple[str, ...]] = {
    "gamma": ("fixed", "free"),
    "lag": ("none", "free"),
    "cuts": ("mechanistic", "free"),
    "sigma": ("shared", "region"),
    "nonresp": ("none", "shared", "region"),
    "dose": ("loglinear", "emax"),
    "trial": ("shared", "region"),
    "placebo": ("single", "split"),
    "kinetics": ("shared", "route"),  # added in-session (see PREREGISTRATION amendments)
}
_DEFAULT_OMITTED = {"kinetics": "shared"}  # keeps names of programs logged before it existed


@dataclass(frozen=True)
class Spec:
    gamma: str = "fixed"
    lag: str = "none"
    cuts: str = "mechanistic"
    sigma: str = "shared"
    nonresp: str = "none"
    dose: str = "loglinear"
    trial: str = "shared"
    placebo: str = "single"
    kinetics: str = "shared"  # onset (gamma, lag) shared, or one per route of the trial

    def canonical(self) -> Spec:
        spec = self
        # gamma only rescales mechanistic cut-points; free cut-points absorb it.
        if spec.cuts == "free":
            spec = replace(spec, gamma="fixed")
        # Per-route kinetics need at least one free kinetic parameter.
        if spec.gamma == "fixed" and spec.lag == "none":
            spec = replace(spec, kinetics="shared")
        return spec

    @property
    def name(self) -> str:
        return ",".join(
            f"{f.name}={getattr(self, f.name)}"
            for f in fields(self)
            if _DEFAULT_OMITTED.get(f.name) != getattr(self, f.name)
        )

    def mutations(self) -> Iterator[Spec]:
        """Every program that differs from this one in exactly one component."""
        seen = {self.canonical()}
        for f in fields(self):
            for option in OPTIONS[f.name]:
                if option != getattr(self, f.name):
                    child = replace(self, **{f.name: option}).canonical()
                    if child not in seen:
                        seen.add(child)
                        yield child


# ----------------------------------------------------------------- design


@dataclass
class Design:
    """Arrays describing a list of arm-weeks for one model."""

    rows: list[ArmWeek]
    region: np.ndarray
    group: list[tuple[object, ...]]
    agent: np.ndarray  # index into the model's agents; -1 control; -2-j unseen agent j
    route: np.ndarray  # index into ROUTES; -1 control
    log_x: np.ndarray  # log(daily dose / reference)
    log_x_load: np.ndarray  # log(loading dose / reference); nan without loading
    photo: np.ndarray
    oral_trial: np.ndarray
    week: np.ndarray
    patterns: dict[tuple[int, ...], np.ndarray] = field(default_factory=dict)
    groups: dict[tuple[object, ...], np.ndarray] = field(default_factory=dict)
    counts: dict[tuple[int, ...], tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        index: dict[tuple[object, ...], list[int]] = {}
        for i, g in enumerate(self.group):
            index.setdefault(g, []).append(i)
        self.groups = {g: np.array(v) for g, v in index.items()}
        for pattern, idx in self.patterns.items():
            counts = np.stack([_bin_counts(self.rows[i]) for i in idx])
            const = gammaln(counts.sum(1) + 1) - gammaln(counts + 1).sum(1)
            self.counts[pattern] = (counts, const)


@dataclass
class Context:
    """Design facts shared by every fit: routes, reference doses, oral trials."""

    agent_route: dict[str, str]
    reference: dict[str, float]
    oral_trials: frozenset[str]


def build_design(
    rows: list[ArmWeek], spec: Spec, ctx: Context, agents: list[str], unseen: list[str]
) -> Design:
    def group_key(a: ArmWeek) -> tuple[object, ...]:
        return (a.trial,) if spec.trial == "shared" else (a.trial, REGION[a.instrument])

    agent = np.full(len(rows), -1)
    route = np.full(len(rows), -1)
    log_x = np.zeros(len(rows))
    log_x_load = np.full(len(rows), np.nan)
    for i, a in enumerate(rows):
        if not a.active:
            continue
        assert a.agent is not None and a.daily_dose is not None
        agent[i] = agents.index(a.agent) if a.agent in agents else -2 - unseen.index(a.agent)
        route[i] = ROUTES.index(ctx.agent_route[a.agent])
        ref = ctx.reference[a.agent]
        log_x[i] = math.log(a.daily_dose / ref)
        if a.loading_dose is not None:
            log_x_load[i] = math.log(a.loading_dose / ref)
    patterns: dict[tuple[int, ...], list[int]] = {}
    for i, a in enumerate(rows):
        patterns.setdefault(a.thresholds, []).append(i)
    return Design(
        rows=rows,
        region=np.array([REGION[a.instrument] for a in rows]),
        group=[group_key(a) for a in rows],
        agent=agent,
        route=route,
        log_x=log_x,
        log_x_load=log_x_load,
        photo=np.array([float(a.phototherapy) for a in rows]),
        oral_trial=np.array([float(a.trial in ctx.oral_trials) for a in rows]),
        week=np.array([float(a.week) for a in rows]),
        patterns={k: np.array(v) for k, v in patterns.items()},
    )


# ------------------------------------------------------------------ model


@dataclass(frozen=True)
class Param:
    name: str
    mean: float
    sd: float


class Model:
    def __init__(self, spec: Spec, agents: list[str]) -> None:
        self.spec = spec.canonical()
        self.agents = agents
        s = self.spec
        p = [Param("theta_face", -5.0, 3.0), Param("theta_body", -5.0, 3.0)]
        p += [Param(f"alpha_{r}", 1.5, 1.5) for r in ROUTES]
        p += [Param(f"delta_{a}", 0.0, AGENT_SD) for a in agents]
        if s.dose == "loglinear":
            p += [Param(f"beta_{r}", 0.5, 0.5) for r in ROUTES]
        else:
            p += [Param(f"logK_{r}", 0.0, 1.5) for r in ROUTES]
        p.append(Param("phi", 0.0, 1.0))
        if s.sigma == "shared":
            p.append(Param("log_sigma", math.log(1.5), 0.75))
        else:
            p += [Param(f"log_sigma_{g}", math.log(1.5), 0.75) for g in ("face", "body")]
        p.append(Param("log_sigma_u", math.log(0.5), 0.75))
        by_route = s.kinetics == "route"
        if s.cuts == "mechanistic":
            p.append(Param("kappa_raw", 0.0, 1.5))
            if s.gamma == "free":
                p += [Param(n, 0.0, 0.5) for n in _kinetic_names("log_gamma", by_route)]
        else:
            p += [Param(f"cut_{i}", 0.0, 1.5) for i in range(1, 5)]
        if s.lag == "free":
            p += [Param(n, -1.0, 1.5) for n in _kinetic_names("lag_raw", by_route)]
        if s.nonresp == "shared":
            p.append(Param("q_raw", -2.0, 1.5))
        elif s.nonresp == "region":
            p += [Param(f"q_raw_{g}", -2.0, 1.5) for g in ("face", "body")]
        if s.placebo == "split":
            p.append(Param("psi_oral", 0.0, 1.0))
        self.params = p
        self.index = {q.name: i for i, q in enumerate(p)}
        self.mean = np.array([q.mean for q in p])
        self.sd = np.array([q.sd for q in p])

    @property
    def size(self) -> int:
        return len(self.params)

    def col(self, x: np.ndarray, name: str) -> np.ndarray:
        return x[:, self.index[name]]

    # -------------------------------------------------- linear predictor

    def _region_pair(self, x: np.ndarray, stem: str, shared: bool) -> np.ndarray:
        """(B, 2) per-region values of a parameter that may be shared."""
        if shared:
            v = self.col(x, stem)
            return np.stack([v, v], axis=1)
        return np.stack([self.col(x, f"{stem}_face"), self.col(x, f"{stem}_body")], axis=1)

    def location(self, x: np.ndarray, d: Design, unseen_delta: np.ndarray) -> np.ndarray:
        """(B, R): theta_g + psi * oral_trial + log A(w), without the trial effect."""
        b = x.shape[0]
        theta = np.stack([self.col(x, "theta_face"), self.col(x, "theta_body")], axis=1)
        loc = theta[:, d.region]
        if self.spec.placebo == "split":
            loc = loc + self.col(x, "psi_oral")[:, None] * d.oral_trial[None, :]
        tau = (
            LAG_MAX * expit(self._kinetic(x, "lag_raw", d))
            if self.spec.lag == "free"
            else np.zeros((b, 1))
        )
        week = d.week[None, :]
        active = d.agent != -1
        # Drug effect E (log-rate multiplier) for active rows; 0 for controls.
        alpha = np.stack([self.col(x, f"alpha_{r}") for r in ROUTES], axis=1)
        seen = [self.col(x, f"delta_{a}") for a in self.agents]
        delta_all = np.concatenate(
            [np.stack(seen, axis=1) if seen else np.zeros((b, 0)), unseen_delta, np.zeros((b, 1))],
            axis=1,
        )  # the trailing zero column is what control rows index
        agent_col = np.where(d.agent >= 0, d.agent, len(self.agents) - 2 - d.agent)
        route = np.where(active, d.route, 0)
        base = (
            alpha[:, route]
            + delta_all[:, np.where(active, agent_col, delta_all.shape[1] - 1)]
            + self.col(x, "phi")[:, None] * d.photo[None, :]
        )
        loading = active & ~np.isnan(d.log_x_load)
        e_main = np.where(active, base + self._dose(x, route, d.log_x), 0.0)
        e_load = np.where(
            loading, base + self._dose(x, route, np.where(loading, d.log_x_load, 0.0)), 0.0
        )
        with np.errstate(divide="ignore"):
            seg_all = np.log(np.maximum(week - tau, 0.0))
            seg1 = np.log(np.maximum(np.minimum(week, LOADING_WEEKS) - tau, 0.0))
            seg2 = np.log(np.maximum(week - np.maximum(tau, LOADING_WEEKS), 0.0))
        log_a = np.where(active[None, :], e_main + seg_all, seg_all)
        log_a_loading = np.logaddexp(e_load + seg1, e_main + seg2)
        log_a = np.where(loading[None, :], log_a_loading, log_a)
        return np.asarray(loc + log_a)

    def _kinetic(self, x: np.ndarray, stem: str, d: Design) -> np.ndarray:
        """(B, 1) shared, or (B, R) by the route of each row's trial."""
        if self.spec.kinetics == "shared":
            return np.asarray(self.col(x, stem)[:, None])
        pair = np.stack([self.col(x, f"{stem}_{r}") for r in ROUTES], axis=1)
        return np.asarray(pair[:, d.oral_trial.astype(int)])

    def _dose(self, x: np.ndarray, route: np.ndarray, log_x: np.ndarray) -> np.ndarray:
        """(B, R) dose term on the log-rate scale (0 at the reference dose)."""
        if self.spec.dose == "loglinear":
            beta = np.stack([self.col(x, f"beta_{r}") for r in ROUTES], axis=1)[:, route]
            return np.asarray(beta * log_x[None, :])
        k = np.exp(np.stack([self.col(x, f"logK_{r}") for r in ROUTES], axis=1))[:, route]
        return np.asarray(np.log1p(k) + log_x[None, :] - np.log(k + np.exp(log_x)[None, :]))

    def cumulative(self, x: np.ndarray, d: Design, loc_u: np.ndarray) -> np.ndarray:
        """P(R >= k) for all THRESHOLDS: loc_u (B, R, N) -> (B, R, N, 5)."""
        sigma = self._region_pair(x, "log_sigma", self.spec.sigma == "shared")
        sigma = np.exp(sigma)[:, d.region][:, :, None, None]
        if self.spec.cuts == "mechanistic":
            kappa = 0.9 + 0.0999 * expit(self.col(x, "kappa_raw"))
            ks = np.array([k / 100 for k in THRESHOLDS[:-1]])
            c = np.concatenate(
                [
                    np.broadcast_to(np.log(-np.log1p(-ks)), (x.shape[0], 4)),
                    np.log(-np.log1p(-kappa))[:, None],
                ],
                axis=1,
            )
            gamma = (
                np.exp(self._kinetic(x, "log_gamma", d))
                if self.spec.gamma == "free"
                else np.ones((x.shape[0], 1))
            )  # (B, 1) or (B, R)
            z = (loc_u[..., None] - c[:, None, None, :] / gamma[:, :, None, None]) / sigma
        else:
            a = np.exp(np.stack([self.col(x, f"cut_{i}") for i in range(1, 5)], axis=1))
            c = np.stack(
                [-a[:, 0], np.zeros(x.shape[0]), a[:, 1], a[:, 1] + a[:, 2],
                 a[:, 1] + a[:, 2] + a[:, 3]],
                axis=1,
            )  # fmt: skip
            z = loc_u[..., None] / sigma - c[:, None, None, :]
        p = ndtr(z)
        if self.spec.nonresp != "none":
            q = expit(self._region_pair(x, "q_raw", self.spec.nonresp == "shared"))
            p = p * (1.0 - q[:, d.region])[:, :, None, None]
        return np.asarray(p)

    # --------------------------------------------------------- likelihood

    def row_loglik(self, x: np.ndarray, d: Design, loc_u: np.ndarray) -> np.ndarray:
        """(B, R, N) multinomial log-likelihood of each row at each trial-effect value."""
        p_all = self.cumulative(x, d, loc_u)
        out = np.zeros(loc_u.shape)
        for pattern, idx in d.patterns.items():
            cols = [THRESHOLDS.index(k) for k in pattern]
            p = np.minimum.accumulate(p_all[:, idx][..., cols], axis=-1)
            ones = np.ones((*p.shape[:-1], 1))
            zeros = np.zeros((*p.shape[:-1], 1))
            bins = np.clip(
                np.concatenate([ones, p], -1) - np.concatenate([p, zeros], -1), _EPS, 1.0
            )
            counts, const = d.counts[pattern]
            out[:, idx] = (counts[None, :, None, :] * np.log(bins)).sum(-1) + const[None, :, None]
        return out

    def log_prior(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(-0.5 * (((x - self.mean) / self.sd) ** 2).sum(axis=1))

    def neg_log_posterior(self, theta: np.ndarray, d: Design) -> float:
        x = theta[None, :]
        sigma_u = math.exp(theta[self.index["log_sigma_u"]])
        loc = self.location(x, d, np.zeros((1, 0)))
        loc_u = loc[:, :, None] + sigma_u * GRID[None, None, :]
        ll = self.row_loglik(x, d, loc_u)[0]  # (R, N)
        total = 0.0
        for idx in d.groups.values():
            total += float(logsumexp(_GRID_LOGW + ll[idx].sum(axis=0)))
        return -(total + float(self.log_prior(x)[0]))


def _kinetic_names(stem: str, by_route: bool) -> list[str]:
    return [f"{stem}_{r}" for r in ROUTES] if by_route else [stem]


def _bin_counts(a: ArmWeek) -> np.ndarray:
    r = np.asarray(a.responders, dtype=float)
    return np.concatenate([[a.n], r]) - np.concatenate([r, [0.0]])


# ------------------------------------------------------------- fit/predict


@dataclass
class Fit:
    model: Model
    ctx: Context
    train: Design
    theta: np.ndarray
    cov: np.ndarray
    nlp: float
    success: bool
    message: str


def training_agents(rows: list[ArmWeek]) -> list[str]:
    return sorted({a.agent for a in rows if a.active and a.agent})


def fit_program(spec: Spec, rows: list[ArmWeek], ctx: Context) -> Fit:
    """MAP of the marginal posterior, then a Laplace approximation."""
    model = Model(spec, training_agents(rows))
    design = build_design(rows, model.spec, ctx, model.agents, [])

    def f(theta: np.ndarray) -> float:
        return model.neg_log_posterior(theta, design)

    best = None
    for start in (model.mean, model.mean + 0.3 * model.sd * np.sin(np.arange(model.size) + 1.0)):
        res = minimize(f, start, method="L-BFGS-B", options={"maxiter": 3000, "maxfun": 200000})
        if best is None or res.fun < best.fun:
            best = res
    assert best is not None
    hess = _hessian(f, best.x)
    vals, vecs = np.linalg.eigh(0.5 * (hess + hess.T))
    vals = np.maximum(vals, 1e-6)
    cov = (vecs / vals) @ vecs.T
    return Fit(
        model, ctx, design, best.x, cov, float(best.fun), bool(best.success), str(best.message)
    )


def _hessian(f: object, x: np.ndarray, h: float = 1e-4) -> np.ndarray:
    fn = f  # callable
    n = len(x)
    hess = np.zeros((n, n))
    f0 = fn(x)  # type: ignore[operator]
    for i in range(n):
        ei = np.zeros(n)
        ei[i] = h
        hess[i, i] = (fn(x + ei) - 2 * f0 + fn(x - ei)) / h**2  # type: ignore[operator]
        for j in range(i + 1, n):
            ej = np.zeros(n)
            ej[j] = h
            v = (
                fn(x + ei + ej) - fn(x + ei - ej) - fn(x - ei + ej) + fn(x - ei - ej)  # type: ignore[operator]
            ) / (4 * h * h)
            hess[i, j] = hess[j, i] = v
    return hess


def predict(
    fit: Fit, targets: list[ArmWeek], *, draws: int = 1000, seed: int = 0
) -> list[np.ndarray]:
    """(draws, thresholds) response probabilities for each target arm-week.

    Each draw combines a Laplace parameter draw, a new agent effect for agents
    the fit has not seen, and the target trial's effect sampled from its
    posterior given that trial's *training* rows (the prior if it has none).
    """
    rng = np.random.default_rng(seed)
    model = fit.model
    x = rng.multivariate_normal(fit.theta, fit.cov, size=draws, method="eigh")
    unseen = sorted(
        {a.agent for a in targets if a.active and a.agent and a.agent not in model.agents}
    )
    unseen_delta = rng.normal(0.0, AGENT_SD, size=(draws, len(unseen)))
    target = build_design(targets, model.spec, fit.ctx, model.agents, unseen)
    sigma_u = np.exp(model.col(x, "log_sigma_u"))

    train_groups = fit.train.groups
    train_loc = model.location(x, fit.train, np.zeros((draws, 0)))
    target_loc = model.location(x, target, unseen_delta)
    u = np.zeros((draws, len(targets)))
    step = GRID[1] - GRID[0]
    for g in set(target.group):
        cols = [i for i, tg in enumerate(target.group) if tg == g]
        logw = np.broadcast_to(_GRID_LOGW, (draws, len(GRID))).copy()
        if g in train_groups:
            idx = train_groups[g]
            loc_u = train_loc[:, idx, None] + sigma_u[:, None, None] * GRID[None, None, :]
            sub = Design(
                rows=[fit.train.rows[i] for i in idx], region=fit.train.region[idx],
                group=[g] * len(idx), agent=fit.train.agent[idx], route=fit.train.route[idx],
                log_x=fit.train.log_x[idx], log_x_load=fit.train.log_x_load[idx],
                photo=fit.train.photo[idx], oral_trial=fit.train.oral_trial[idx],
                week=fit.train.week[idx],
                patterns=_patterns([fit.train.rows[i] for i in idx]),
            )  # fmt: skip
            logw = logw + model.row_loglik(x, sub, loc_u).sum(axis=1)
        prob = np.exp(logw - logsumexp(logw, axis=1, keepdims=True))
        cdf = np.cumsum(prob, axis=1)
        pick = (cdf < rng.random((draws, 1))).sum(axis=1).clip(0, len(GRID) - 1)
        z = GRID[pick] + step * (rng.random(draws) - 0.5)
        u[:, cols] = (sigma_u * z)[:, None]
    p_all = model.cumulative(x, target, (target_loc + u)[:, :, None])[:, :, 0, :]
    return [p_all[:, i, [THRESHOLDS.index(k) for k in a.thresholds]] for i, a in enumerate(targets)]


def _patterns(rows: list[ArmWeek]) -> dict[tuple[int, ...], np.ndarray]:
    out: dict[tuple[int, ...], list[int]] = {}
    for i, a in enumerate(rows):
        out.setdefault(a.thresholds, []).append(i)
    return {k: np.array(v) for k, v in out.items()}
