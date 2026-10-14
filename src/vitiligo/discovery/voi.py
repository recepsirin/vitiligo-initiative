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


def simulate_counts(arm: ArmWeek, draw: int, rng: np.random.Generator) -> np.ndarray:
    """Bin counts for one simulated outcome of ``arm`` under posterior draw ``draw``."""
    return np.asarray(rng.multinomial(arm.n, _bins(arm.cumulative[0, draw])))


def counts_from_cumulative(n: int, responders: Sequence[int]) -> np.ndarray:
    """Observed cumulative responders at increasing thresholds -> bin counts."""
    r = np.asarray(responders, dtype=float)
    return np.asarray(np.concatenate([[n], r]) - np.concatenate([r, [0.0]]))


def loglik(arm: ArmWeek, counts: np.ndarray) -> np.ndarray:
    """(D,) log-likelihood of bin ``counts`` per draw, averaging over K replicates."""
    ll = (counts * np.log(_bins(arm.cumulative))).sum(axis=-1)  # (K, D)
    peak = ll.max(axis=0)
    return np.asarray(peak + np.log(np.mean(np.exp(ll - peak), axis=0)))


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
        log_w = np.zeros(draws)
        for arm in item:
            log_w += loglik(arm, simulate_counts(arm, j, rng))
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
) -> tuple[float, float]:
    """(shift of q's mean, ESS) after reweighting by the observed bin counts."""
    log_w = np.zeros(q.shape[0])
    for arm, counts in zip(item, observed, strict=True):
        log_w += loglik(arm, counts)
    w, e = _weights(log_w)
    return float(w @ q - q.mean()), e


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
