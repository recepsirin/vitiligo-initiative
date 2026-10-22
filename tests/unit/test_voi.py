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
    shift, ess, khat = voi.realized_shift(p, [_beta_arm(p, 100)], [counts])
    exact = (2 + 80) / (4 + 100) - 0.5
    assert shift == pytest.approx(exact, abs=0.01) and 1 < ess < 20000
    assert khat < 0.7  # bounded likelihood: the reweighting is reliable, and exact here
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


def test_pareto_khat_separates_good_and_bad_importance_weights() -> None:
    rng = np.random.default_rng(6)
    x = rng.normal(0.0, 1.0, 8000)
    matched = -0.5 * (x / 1.1) ** 2 + 0.5 * x**2  # proposal N(0,1), target N(0,1.1^2)
    shifted = -0.5 * (x - 3.0) ** 2 + 0.5 * x**2  # target N(3,1): far into the proposal's tail
    assert voi.pareto_khat(matched) < 0.5
    assert voi.pareto_khat(shifted) > 0.7
    stats = pytest.importorskip("arviz_stats.base.array")
    for lw in (matched, shifted):
        _, k_ref = stats.array_stats.psislw(-lw)  # arviz takes negated log weights
        assert voi.pareto_khat(lw) == pytest.approx(float(k_ref), abs=1e-6)


def test_surprise_flags_outcomes_the_model_did_not_expect() -> None:
    p = np.random.default_rng(7).beta(2, 8, 6000)  # expects about 20% responders
    arm = _beta_arm(p, 100)
    typical = voi.surprise([arm], [voi.counts_from_cumulative(100, [20])], sims=400)
    extreme = voi.surprise([arm], [voi.counts_from_cumulative(100, [95])], sims=400)
    assert typical > 0.3 and extreme < 0.01


def test_arms_of_one_trial_share_its_random_effects() -> None:
    """Two arms sharing a random baseline u: the item likelihood must integrate u jointly.

    p_active = L(theta + u + 1), p_control = L(theta + u), u ~ N(0, 1) per trial (L logistic;
    the link is irrelevant here). A low placebo with a moderate active arm is only likely if
    u is low for *both*.
    """

    def ndtr(x: np.ndarray) -> np.ndarray:  # logistic link: NumPy only, so the test runs in CI
        return np.asarray(1.0 / (1.0 + np.exp(-x)))

    rng = np.random.default_rng(8)
    theta = rng.normal(-1.0, 0.3, 4000)
    k = 400
    u = rng.normal(0.0, 1.0, (k, 1))
    active = voi.ArmWeek(cumulative=ndtr(theta[None, :] + u + 1.0)[..., None], n=200)
    control = voi.ArmWeek(cumulative=ndtr(theta[None, :] + u)[..., None], n=200)
    counts = [voi.counts_from_cumulative(200, [60]), voi.counts_from_cumulative(200, [20])]
    got = voi.item_loglik([active, control], counts)
    # Exact: integrate u on a fine grid, jointly for both arms.
    grid = np.linspace(-6, 6, 2001)
    w = np.exp(-0.5 * grid**2)
    w /= w.sum()
    pa = ndtr(theta[:, None] + grid[None, :] + 1.0)
    pc = ndtr(theta[:, None] + grid[None, :])
    joint = 60 * np.log(pa) + 140 * np.log1p(-pa) + 20 * np.log(pc) + 180 * np.log1p(-pc)
    exact = np.log((np.exp(joint - joint.max(axis=1, keepdims=True)) * w).sum(axis=1)) + joint.max(
        axis=1
    )

    def posterior_mean(log_w: np.ndarray) -> float:
        w_ = np.exp(log_w - log_w.max())
        return float(w_ @ theta / w_.sum())

    truth = posterior_mean(exact)
    assert abs(posterior_mean(got) - truth) < 0.03
    # Integrating each arm separately (the old behaviour) overshoots the update.
    separate = voi.loglik(active, counts[0]) + voi.loglik(control, counts[1])
    assert abs(posterior_mean(separate) - truth) > 0.05


def test_spearman_handles_ties_and_constant_input() -> None:
    assert voi.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert voi.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    # Ties get average ranks: [1, 2.5, 2.5, 4] against [1, 2, 3, 4].
    assert voi.spearman([1, 2, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9486833, abs=1e-6)
    assert np.isnan(voi.spearman([1, 1, 1], [1, 2, 3]))


def test_prospective_test_waits_for_five_results() -> None:
    evr = [1.0, 2.0, 3.0, 4.0]
    early = voi.prospective_test(evr, [0.5, 1.0, 1.5, 2.0])
    assert early["resolved"] == 4 and early["passed"] is None
    assert early["spearman"] == pytest.approx(1.0)
    assert early["mean_surprise_ratio"] == pytest.approx(np.mean([0.25, 0.5, 0.75, 1.0]))
    # Signs of shifts do not matter (value is about squared shifts).
    passed = voi.prospective_test([*evr, 5.0], [0.5, -1.0, 1.5, -2.0, 2.5])
    assert passed["passed"] is True
    failed = voi.prospective_test([*evr, 5.0], [2.5, 2.0, 1.5, 1.0, 0.5])
    assert failed["spearman"] == pytest.approx(-1.0) and failed["passed"] is False
    with pytest.raises(ValueError):
        voi.prospective_test([1.0], [1.0, 2.0])
