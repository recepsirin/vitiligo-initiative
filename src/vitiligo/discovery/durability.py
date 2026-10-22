"""Scoring of durability forecasts (docs/durability-forecast-preregistration.md).

A posted estimate (a hazard ratio, or a retention probability) comes with a
95% confidence interval. Its log score under a forecast is the density of the
estimate after widening the forecast by the estimate's own sampling error, so
a small trial is not punished for its noise. Each score is paired with an
uninformed benchmark scored the same way.
"""

from __future__ import annotations

import math

import numpy as np

_Z = 1.959964


def _se_log(ci_low: float, ci_high: float) -> float:
    return (math.log(ci_high) - math.log(ci_low)) / (2 * _Z)


def _log_normal_pdf(x: float, mean: float, var: float) -> float:
    return -0.5 * (math.log(2 * math.pi * var) + (x - mean) ** 2 / var)


def hr_log_score(hr: float, ci_low: float, ci_high: float, mean: float, sd: float) -> float:
    """Log score of a posted hazard ratio under a normal forecast of log HR."""
    se = _se_log(ci_low, ci_high)
    return _log_normal_pdf(math.log(hr), mean, sd**2 + se**2)


def hr_benchmark_log_score(hr: float, ci_low: float, ci_high: float) -> float:
    """The uninformed benchmark: log HR ~ N(0, 1)."""
    return hr_log_score(hr, ci_low, ci_high, 0.0, 1.0)


def retention_log_score(estimate: float, ci_low: float, ci_high: float, draws: np.ndarray) -> float:
    """Log score of a posted retention probability: the forecast draws' average density."""
    se = (ci_high - ci_low) / (2 * _Z)
    z = (estimate - np.asarray(draws, dtype=float)) / se
    return float(np.log(np.mean(np.exp(-0.5 * z**2)) / (se * math.sqrt(2 * math.pi))))


def retention_benchmark_log_score(estimate: float, ci_low: float, ci_high: float) -> float:
    """The uninformed benchmark: retention uniform on [0, 1]."""
    se = (ci_high - ci_low) / (2 * _Z)

    def cdf(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    return math.log(cdf((1 - estimate) / se) - cdf((0 - estimate) / se))
