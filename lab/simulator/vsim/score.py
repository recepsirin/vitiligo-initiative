"""One scoring function for every model: predictive draws -> log score, coverage, bias.

A model's prediction for an arm-week is an array of shape (draws, thresholds)
holding P(responder at threshold k) in each posterior/predictive draw, with
thresholds in the observation's (ascending) order.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import gammaln, logsumexp

from vsim.data import ArmWeek

_EPS = 1e-12


def bin_probabilities(p: np.ndarray) -> np.ndarray:
    """Cumulative P(>= k_j) (..., m) -> multinomial bin probabilities (..., m + 1)."""
    p = np.clip(p, 0.0, 1.0)
    p = np.minimum.accumulate(p, axis=-1)  # nested thresholds cannot increase
    upper = np.concatenate([np.ones((*p.shape[:-1], 1)), p], axis=-1)
    lower = np.concatenate([p, np.zeros((*p.shape[:-1], 1))], axis=-1)
    return np.clip(upper - lower, _EPS, 1.0)


def bin_counts(aw: ArmWeek) -> np.ndarray:
    r = np.asarray(aw.responders, dtype=float)
    upper = np.concatenate([[aw.n], r])
    lower = np.concatenate([r, [0.0]])
    return upper - lower


def multinomial_logpmf(counts: np.ndarray, probs: np.ndarray) -> np.ndarray:
    """log Multinomial(counts | probs) over the last axis (probs may carry leading axes)."""
    n = counts.sum()
    const = gammaln(n + 1) - gammaln(counts + 1).sum()
    return np.asarray(const + (counts * np.log(probs)).sum(axis=-1))


def log_predictive(aw: ArmWeek, p_draws: np.ndarray) -> float:
    """log of the predictive probability of the observed counts, averaged over draws."""
    lp = multinomial_logpmf(bin_counts(aw), bin_probabilities(p_draws))
    return float(logsumexp(lp) - np.log(len(lp)))


@dataclass
class Scores:
    arm_weeks: int
    rows: int
    log_score_sum: float
    log_score_mean: float
    coverage80: float
    coverage95: float
    mean_signed_error: float
    mean_abs_error: float

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def score(
    targets: list[ArmWeek], predictions: list[np.ndarray], *, seed: int = 0
) -> tuple[Scores, list[dict[str, object]]]:
    """Aggregate metrics plus one detail record per arm-week."""
    rng = np.random.default_rng(seed)
    logs: list[float] = []
    in80: list[bool] = []
    in95: list[bool] = []
    errors: list[float] = []
    detail: list[dict[str, object]] = []
    for aw, p in zip(targets, predictions, strict=True):
        if p.shape[1] != len(aw.thresholds):
            raise ValueError(f"prediction shape {p.shape} vs thresholds {aw.thresholds}")
        lp = log_predictive(aw, p)
        logs.append(lp)
        rows = []
        for j, k in enumerate(aw.thresholds):
            observed = aw.responders[j] / aw.n
            sims = rng.binomial(aw.n, np.clip(p[:, j], 0.0, 1.0)) / aw.n
            q = np.quantile(sims, [0.1, 0.9, 0.025, 0.975])
            in80.append(bool(q[0] <= observed <= q[1]))
            in95.append(bool(q[2] <= observed <= q[3]))
            errors.append(float(np.mean(p[:, j]) - observed))
            rows.append(
                {
                    "threshold": k,
                    "observed": round(observed, 4),
                    "predicted_mean": round(float(np.mean(p[:, j])), 4),
                    "lo80": round(float(q[0]), 4),
                    "hi80": round(float(q[1]), 4),
                }
            )
        detail.append(
            {
                "instrument": aw.instrument,
                "trial": aw.trial,
                "arm": aw.label,
                "week": aw.week,
                "n": aw.n,
                "log_score": round(lp, 4),
                "thresholds": rows,
            }
        )
    err = np.asarray(errors)
    return (
        Scores(
            arm_weeks=len(logs),
            rows=len(errors),
            log_score_sum=float(np.sum(logs)),
            log_score_mean=float(np.mean(logs)),
            coverage80=float(np.mean(in80)),
            coverage95=float(np.mean(in95)),
            mean_signed_error=float(err.mean()),
            mean_abs_error=float(np.abs(err).mean()),
        ),
        detail,
    )
