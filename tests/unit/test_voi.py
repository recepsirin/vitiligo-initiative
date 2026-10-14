"""Tests for the value-of-information core against exact answers."""

from __future__ import annotations

import math

import numpy as np
import pytest

from vitiligo.discovery import voi


def _beta_arm(p: np.ndarray, n: int) -> voi.ArmWeek:
    return voi.ArmWeek(cumulative=p[None, :, None], n=n)


@pytest.mark.parametrize(("a", "b", "n"), [(2.0, 8.0, 20), (5.0, 5.0, 100), (1.0, 3.0, 5)])
def test_evr_matches_the_beta_binomial_answer(a: float, b: float, n: int) -> None:
    """For p ~ Beta(a, b) and r ~ Bin(n, p): EVR of p = Var(p) * n / (a + b + n)."""
    p = np.random.default_rng(1).beta(a, b, 20000)
    est = voi.expected_variance_reduction(p, [_beta_arm(p, n)], sims=1500, seed=2)
    exact = (a * b / ((a + b) ** 2 * (a + b + 1))) * n / (a + b + n)
    assert est.evr == pytest.approx(exact, rel=0.15)
    assert est.prior_var == pytest.approx(a * b / ((a + b) ** 2 * (a + b + 1)), rel=0.05)


def test_evr_grows_with_size_and_vanishes_for_unrelated_evidence() -> None:
    rng = np.random.default_rng(3)
    p = rng.beta(3, 7, 8000)
    small = voi.expected_variance_reduction(p, [_beta_arm(p, 10)], sims=600).evr
    large = voi.expected_variance_reduction(p, [_beta_arm(p, 400)], sims=600).evr
    unrelated = rng.permutation(p)  # evidence about an independent quantity
    none = voi.expected_variance_reduction(unrelated, [_beta_arm(p, 400)], sims=600).evr
    assert large > 2 * small and none < 0.1 * large


def test_realized_shift_and_counts() -> None:
    p = np.random.default_rng(4).beta(2, 2, 20000)
    counts = voi.counts_from_cumulative(100, [80])  # 80 of 100 responded
    shift, ess = voi.realized_shift(p, [_beta_arm(p, 100)], [counts])
    exact = (2 + 80) / (4 + 100) - 0.5
    assert shift == pytest.approx(exact, abs=0.01) and 1 < ess < 20000
    assert voi.counts_from_cumulative(50, [30, 20, 5]).tolist() == [20, 10, 15, 5]


def test_model_discrimination_limits() -> None:
    rng = np.random.default_rng(5)
    same = np.clip(rng.normal(0.3, 0.02, 2000), 0.01, 0.99), np.full(2000, 0.05)
    apart = np.clip(rng.normal(0.6, 0.02, 2000), 0.01, 0.99), np.full(2000, 0.05)
    tie = voi.model_discrimination({"a": same, "b": same}, 300, 150, sims=500)
    clear = voi.model_discrimination({"a": same, "b": apart}, 300, 150, sims=500)
    assert tie["mutual_information_nats"] < 0.02
    assert clear["mutual_information_nats"] == pytest.approx(math.log(2), abs=0.02)
    assert clear["p_true_model_gets_75pct"] > 0.98
