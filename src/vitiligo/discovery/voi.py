"""Value of information: how much a piece of evidence would change an answer, before we see it.

An evidence item is a list of independent arm-weeks. For each one the model
supplies per-draw cumulative responder probabilities ``P(>= k)`` at the item's
thresholds, shape ``(K, D, m)``. Here K counts replicate draws of new-trial
random effects (1 for arms of trials already in the fit), D counts posterior
draws and m counts thresholds. The question is a per-draw quantity ``q`` of
shape ``(D,)``.

- **Expected variance reduction (EVR).** Simulate outcomes from the posterior
  predictive, reweight the draws by each outcome's likelihood, and take the
  variance of the posterior mean of ``q`` across outcomes. By the law of total
  variance this equals ``Var(q) - E[Var(q | outcome)]``, which is also the
  expected squared shift of the mean.
- **Model discrimination.** The mutual information between an outcome and which
  of several models is right.

Reweighting replaces refitting. When one outcome dominates the weights
(effective sample size near 1), the estimate is unreliable, and the reported
ESS says so.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

_EPS = 1e-12


@dataclass(frozen=True)
class ArmWeek:
    """One arm at one week: per-draw cumulative probabilities and the arm size."""

    cumulative: np.ndarray  # (K, D, m), non-increasing along m
    n: int


def _bins(cumulative: np.ndarray) -> np.ndarray:
    p = np.minimum.accumulate(np.clip(cumulative, 0.0, 1.0), axis=-1)
    ones = np.ones((*p.shape[:-1], 1))
    zeros = np.zeros((*p.shape[:-1], 1))
    return np.asarray(
        np.clip(np.concatenate([ones, p], -1) - np.concatenate([p, zeros], -1), _EPS, 1.0)
    )


def simulate_counts(
    arm: ArmWeek, draw: int, rng: np.random.Generator, replicate: int = 0
) -> np.ndarray:
    """Bin counts for one simulated outcome of ``arm`` under posterior draw ``draw``."""
    k = min(replicate, arm.cumulative.shape[0] - 1)
    return np.asarray(rng.multinomial(arm.n, _bins(arm.cumulative[k, draw])))


def _simulate_item(
    item: Sequence[ArmWeek], draw: int, rng: np.random.Generator
) -> list[np.ndarray]:
    """One simulated outcome of every arm, sharing one replicate of the trial effects."""
    replicates = max(arm.cumulative.shape[0] for arm in item)
    k = int(rng.integers(replicates))
    return [simulate_counts(arm, draw, rng, k) for arm in item]


def counts_from_cumulative(n: int, responders: Sequence[int]) -> np.ndarray:
    """Observed cumulative responders at increasing thresholds -> bin counts."""
    r = np.asarray(responders, dtype=float)
    return np.asarray(np.concatenate([[n], r]) - np.concatenate([r, [0.0]]))


def item_loglik(item: Sequence[ArmWeek], counts: Sequence[np.ndarray]) -> np.ndarray:
    """(D,) log-likelihood of an item's bin counts per draw.

    Replicate k is one draw of the new trial's random effects, shared by every
    arm of the item (the arms of one trial share its baseline and treatment
    effect). So arm log-likelihoods are summed within a replicate *before*
    averaging over replicates. Averaging each arm separately would treat the
    arms as coming from different trials.
    """
    total: np.ndarray | None = None
    for arm, c in zip(item, counts, strict=True):
        ll = (c * np.log(_bins(arm.cumulative))).sum(axis=-1)  # (K, D); K = 1 broadcasts
        total = ll if total is None else total + ll
    assert total is not None
    peak = total.max(axis=0)
    return np.asarray(peak + np.log(np.mean(np.exp(total - peak), axis=0)))


def loglik(arm: ArmWeek, counts: np.ndarray) -> np.ndarray:
    """(D,) log-likelihood of one arm's bin ``counts`` per draw."""
    return item_loglik([arm], [counts])


def _weights(log_w: np.ndarray) -> tuple[np.ndarray, float]:
    w = np.exp(log_w - log_w.max())
    w /= w.sum()
    return w, float(1.0 / np.sum(w**2))


@dataclass
class ValueEstimate:
    evr: float  # expected variance reduction of q
    prior_var: float
    mean_ess: float  # mean effective sample size of the reweighting
    min_ess: float


def expected_variance_reduction(
    q: np.ndarray, item: Sequence[ArmWeek], *, sims: int = 400, seed: int = 0
) -> ValueEstimate:
    rng = np.random.default_rng(seed)
    draws = q.shape[0]
    means, ess = [], []
    for _ in range(sims):
        j = int(rng.integers(draws))
        log_w = item_loglik(item, _simulate_item(item, j, rng))
        w, e = _weights(log_w)
        means.append(float(w @ q))
        ess.append(e)
    return ValueEstimate(
        evr=float(np.var(means, ddof=1)),
        prior_var=float(np.var(q)),
        mean_ess=float(np.mean(ess)),
        min_ess=float(np.min(ess)),
    )


def realized_shift(
    q: np.ndarray, item: Sequence[ArmWeek], observed: Sequence[np.ndarray]
) -> tuple[float, float, float]:
    """(shift of q's mean, ESS, Pareto k) after reweighting by the observed bin counts.

    Trust the shift only when Pareto k < 0.7; otherwise refit.
    """
    log_w = item_loglik(item, observed)
    w, e = _weights(log_w)
    return float(w @ q - q.mean()), e, pareto_khat(log_w)


def model_discrimination(
    models: dict[str, tuple[np.ndarray, np.ndarray]],
    n_active: int,
    n_control: int,
    *,
    sims: int = 2000,
    seed: int = 0,
) -> dict[str, float]:
    """Mutual information (nats) between a trial's outcome and which model is right.

    ``models`` maps a name to its predictive draws ``(p_active, p_control)``,
    with equal prior weight on each model. The maximum is ``log(len(models))``.
    """
    rng = np.random.default_rng(seed)
    names = sorted(models)
    total, decisive = 0.0, 0
    for _ in range(sims):
        true = names[int(rng.integers(len(names)))]
        pa, pc = models[true]
        j = int(rng.integers(len(pa)))
        r_a, r_c = rng.binomial(n_active, pa[j]), rng.binomial(n_control, pc[j])
        log_ev = []
        for name in names:
            a, c = (np.clip(x, _EPS, 1 - _EPS) for x in models[name])
            ll = (
                r_a * np.log(a)
                + (n_active - r_a) * np.log1p(-a)
                + r_c * np.log(c)
                + (n_control - r_c) * np.log1p(-c)
            )
            peak = ll.max()
            log_ev.append(peak + math.log(float(np.mean(np.exp(ll - peak)))))
        log_ev_arr = np.array(log_ev)
        log_post = log_ev_arr - np.logaddexp.reduce(log_ev_arr)
        total += float(log_post[names.index(true)]) + math.log(len(names))
        decisive += int(np.exp(log_post[names.index(true)]) >= 0.75)
    return {
        "mutual_information_nats": total / sims,
        "max_nats": math.log(len(names)),
        "p_true_model_gets_75pct": decisive / sims,
    }


def pareto_khat(log_weights: np.ndarray) -> float:
    """Pareto-k diagnostic of importance weights (PSIS; Vehtari et al. 2024).

    Fits a generalized Pareto distribution to the largest weights (Zhang &
    Stephens estimator with PSIS's weak prior toward 0.5), as in arviz. Above
    0.7 the reweighted estimates are unreliable even when the effective sample
    size looks adequate: the target lies where the draws are too sparse.
    """
    lw = np.asarray(log_weights, dtype=float)
    n = lw.size
    tail_size = math.floor(3 * math.sqrt(n)) if n > 225 else n // 5
    if tail_size < 5:
        return float("nan")
    ordered = np.sort(lw - lw.max())
    cutoff = math.exp(ordered[n - tail_size - 1])
    x = np.exp(ordered[n - tail_size :]) - cutoff  # sorted ascending
    m = x.size
    quartile = x[int(m / 4 + 0.5) - 1]
    if quartile <= x[0]:
        return float("nan")
    grid = 30 + int(math.sqrt(m))
    b = 1.0 / x[-1] + (1.0 - np.sqrt(grid / (np.arange(1, grid + 1) - 0.5))) / (3.0 * quartile)
    k_grid = np.log1p(-b[:, None] * x[None, :]).mean(axis=1)
    log_lik = m * (np.log(-b / k_grid) - k_grid - 1.0)
    w = np.exp(log_lik - log_lik.max())
    w /= w.sum()
    b_post = float((b * w).sum())
    k = float(np.log1p(-b_post * x).mean())
    return float((m * k + 10 * 0.5) / (m + 10))


def surprise(
    item: Sequence[ArmWeek], observed: Sequence[np.ndarray], *, sims: int = 400, seed: int = 0
) -> float:
    """Share of the model's own simulated outcomes that are less likely than the observed one.

    Near 0 means the observed outcome lies far outside what the model expected:
    value-of-information estimates made with that model did not anticipate it.
    """
    rng = np.random.default_rng(seed)

    def log_marginal(counts: Sequence[np.ndarray]) -> float:
        # Unlike reweighting, comparing different outcomes needs the
        # multinomial coefficients, which depend on the counts.
        ll = item_loglik(item, counts)
        const = sum(
            math.lgamma(float(c.sum()) + 1) - sum(math.lgamma(float(x) + 1) for x in c)
            for c in counts
        )
        return float(const + ll.max() + np.log(np.mean(np.exp(ll - ll.max()))))

    observed_lp = log_marginal(observed)
    draws = item[0].cumulative.shape[1]
    simulated = []
    for _ in range(sims):
        j = int(rng.integers(draws))
        simulated.append(log_marginal(_simulate_item(item, j, rng)))
    return float(np.mean(np.asarray(simulated) <= observed_lp))


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation (ties get average ranks)."""

    def ranks(v: Sequence[float]) -> np.ndarray:
        a = np.asarray(v, dtype=float)
        order = np.argsort(a, kind="stable")
        r = np.empty(len(a))
        r[order] = np.arange(len(a), dtype=float)
        for value in np.unique(a):
            tied = a == value
            r[tied] = r[tied].mean()
        return r

    rx, ry = ranks(x), ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def prospective_test(
    evr: Sequence[float], shift: Sequence[float], *, minimum: int = 5, threshold: float = 0.5
) -> dict[str, float | int | bool | None]:
    """Do predicted values track realized impact on results that were not yet public?

    ``evr`` holds each resolved item's predicted expected variance reduction and
    ``shift`` its realized shift of the question after refitting. The verdict
    is None until ``minimum`` items have resolved.
    """
    n = len(evr)
    if n != len(shift):
        raise ValueError("one realized shift per predicted value")
    squared = [s * s for s in shift]
    rho = spearman(evr, squared) if n >= 2 else float("nan")
    ratios = [s / e for s, e in zip(squared, evr, strict=True) if e > 0]
    defined = not math.isnan(rho)  # None, not NaN, in the output: NaN is not valid JSON
    return {
        "resolved": n,
        "spearman": rho if defined else None,
        "mean_surprise_ratio": float(np.mean(ratios)) if ratios else None,
        "passed": None if n < minimum else bool(defined and rho >= threshold),
    }
