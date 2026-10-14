"""Valid evidence for a stream of hypotheses: e-values and online FDR (e-LOND).

Claim family v0, *superiority with margin*: "in trial T, regimen R's
responder rate exceeds the control arm's by more than delta". Null:
``p_active - p_control <= delta``.

e-value (universal inference; Wasserman, Ramdas & Balakrishnan, PNAS 2020)::

    e = L(theta_1) / sup_{theta in H0} L(theta)

where theta_1 = (p_active, p_control) is a prediction fixed *without* using
trial T's data (a model fitted with T held out). Then E[e] <= 1 under the
null, so P(e >= 1/a) <= a (Markov) — valid however theta_1 was chosen, as
long as it did not look at T.

Claim families v1 test the same e-value against a *linear* null
``p_x - ratio * p_y <= margin`` between two independent arms of one trial:
regimen contrasts (ratio 1, a more intensive regimen beats a less intensive
one) and dose retention (margin 0, a lower dose keeps more than ``ratio`` of a
higher dose's response rate).

Online FDR (e-LOND; Xu & Ramdas, AISTATS 2024): test t is a discovery when
``e_t >= 1 / alpha_t`` with ``alpha_t = alpha * gamma_t * (D_{t-1} + 1)``,
``D_{t-1}`` the discoveries so far and ``gamma_t = 6 / (pi^2 t^2)`` (sums to
1). This controls the false discovery rate at alpha under arbitrary
dependence between the e-values.
"""

from __future__ import annotations

import math

import numpy as np

_EPS = 1e-9


def _loglik(r: int, n: int, p: float) -> float:
    """Binomial log-likelihood without the constant; 0 * log 0 treated as 0."""
    p = min(max(p, _EPS), 1.0 - _EPS)
    return (r * math.log(p) if r else 0.0) + ((n - r) * math.log(1.0 - p) if n - r else 0.0)


def _null_mle(r_a: int, n_a: int, r_c: int, n_c: int, margin: float) -> tuple[float, float]:
    """Maximum-likelihood (p_a, p_c) subject to p_a - p_c <= margin."""
    p_a, p_c = r_a / n_a, r_c / n_c
    if p_a - p_c <= margin:
        return p_a, p_c
    # The log-likelihood is concave and the null region convex, so the maximum
    # lies on the boundary p_a = p_c + margin: a 1-D concave problem in p_c.
    lo, hi = max(0.0, -margin) + _EPS, min(1.0, 1.0 - margin) - _EPS

    def f(pc: float) -> float:
        return _loglik(r_a, n_a, pc + margin) + _loglik(r_c, n_c, pc)

    for _ in range(200):  # golden-section search
        m1 = hi - (hi - lo) * 0.6180339887498949
        m2 = lo + (hi - lo) * 0.6180339887498949
        if f(m1) < f(m2):
            lo = m1
        else:
            hi = m2
    p_c_hat = (lo + hi) / 2.0
    return p_c_hat + margin, p_c_hat


def superiority_log_e(
    r_active: int,
    n_active: int,
    r_control: int,
    n_control: int,
    *,
    predicted_active: float,
    predicted_control: float,
    margin: float = 0.0,
) -> float:
    """log e-value against H0: p_active - p_control <= margin (probability units).

    ``predicted_*`` must come from a source that did not see these counts.
    """
    if n_active <= 0 or n_control <= 0:
        raise ValueError("arm sizes must be positive")
    if not (0 <= r_active <= n_active and 0 <= r_control <= n_control):
        raise ValueError("responders must lie between 0 and n")
    if not -1.0 < margin < 1.0:
        raise ValueError("margin must lie strictly between -1 and 1")
    alt = _loglik(r_active, n_active, predicted_active) + _loglik(
        r_control, n_control, predicted_control
    )
    p_a0, p_c0 = _null_mle(r_active, n_active, r_control, n_control, margin)
    null = _loglik(r_active, n_active, p_a0) + _loglik(r_control, n_control, p_c0)
    return alt - null


def _loglik_vec(r: np.ndarray, n: float | np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(p, _EPS, 1.0 - _EPS)
    return np.asarray(r * np.log(p) + (n - r) * np.log1p(-p))


def _null_loglik_vec(
    r_a: np.ndarray, n_a: int, r_c: np.ndarray, n_c: int, margin: float, ratio: float = 1.0
) -> np.ndarray:
    """Max log-likelihood under H0 (p_a - ratio * p_c <= margin), vectorized over count pairs."""
    p_a, p_c = r_a / n_a, r_c / n_c
    inside = p_a - ratio * p_c <= margin
    # On the boundary p_a = ratio * p_c + margin, with both probabilities in [0, 1].
    lo = np.full(r_a.shape, max(0.0, -margin / ratio) + _EPS)
    hi = np.full(r_a.shape, min(1.0, (1.0 - margin) / ratio) - _EPS)

    def f(pc: np.ndarray) -> np.ndarray:
        return np.asarray(_loglik_vec(r_a, n_a, ratio * pc + margin) + _loglik_vec(r_c, n_c, pc))

    for _ in range(80):  # golden-section on the concave boundary problem
        m1 = hi - (hi - lo) * 0.6180339887498949
        m2 = lo + (hi - lo) * 0.6180339887498949
        right = f(m1) < f(m2)
        lo = np.where(right, m1, lo)
        hi = np.where(right, hi, m2)
    boundary = f((lo + hi) / 2.0)
    unconstrained = _loglik_vec(r_a, n_a, p_a) + _loglik_vec(r_c, n_c, p_c)
    return np.asarray(np.where(inside, unconstrained, boundary))


def mixture_log_e(
    r_active: int | np.ndarray,
    n_active: int,
    r_control: int | np.ndarray,
    n_control: int,
    *,
    alt_active: np.ndarray,
    alt_control: np.ndarray,
    margin: float = 0.0,
    ratio: float = 1.0,
) -> np.ndarray:
    """log of a *mixture* e-value against H0: p_active - ratio * p_control <= margin.

    ``e = mean_j L(theta_j) / sup_H0 L``, averaging over alternative draws
    theta_j that did not see the counts (e.g. a held-out model's predictive
    draws where the claim holds). Each fixed theta_j gives a valid e-value and
    an average of valid e-values is valid; the mixture is far more robust than
    a single predicted point when the predicted *level* is off. Vectorized over
    count pairs (used for power simulations).
    """
    if ratio <= 0.0:
        raise ValueError("ratio must be positive")
    r_a = np.atleast_1d(np.asarray(r_active, dtype=float))
    r_c = np.atleast_1d(np.asarray(r_control, dtype=float))
    alt_a = np.asarray(alt_active, dtype=float)[None, :]
    alt_c = np.asarray(alt_control, dtype=float)[None, :]
    alt = _loglik_vec(r_a[:, None], n_active, alt_a) + _loglik_vec(r_c[:, None], n_control, alt_c)
    peak = alt.max(axis=1)
    log_mean = peak + np.log(np.mean(np.exp(alt - peak[:, None]), axis=1))
    return np.asarray(log_mean - _null_loglik_vec(r_a, n_active, r_c, n_control, margin, ratio))


def discovery_power(
    *,
    n_active: int,
    n_control: int,
    draws_active: np.ndarray,
    draws_control: np.ndarray,
    margin: float,
    alpha_t: float,
    ratio: float = 1.0,
    simulations: int = 200,
    seed: int = 0,
) -> float:
    """Model-predicted probability that testing this claim yields a discovery.

    Simulates trial outcomes from the (held-out) predictive draws and scores
    each with the same mixture e-value the real test will use. Uses no data
    from the trial being tested, so selecting claims by power is safe.
    """
    keep = draws_active - ratio * draws_control > margin
    if not np.any(keep):
        return 0.0
    rng = np.random.default_rng(seed)
    alt_a, alt_c = draws_active[keep], draws_control[keep]
    pick = rng.integers(0, len(draws_active), simulations)
    r_a = rng.binomial(n_active, draws_active[pick])
    r_c = rng.binomial(n_control, draws_control[pick])
    log_e = mixture_log_e(
        r_a,
        n_active,
        r_c,
        n_control,
        alt_active=alt_a,
        alt_control=alt_c,
        margin=margin,
        ratio=ratio,
    )
    return float(np.mean(log_e >= -math.log(alpha_t)))


def elond_gamma(t: int) -> float:
    """gamma_t = 6 / (pi^2 t^2); sums to exactly 1 over t = 1, 2, ..."""
    if t < 1:
        raise ValueError("test index starts at 1")
    return 6.0 / (math.pi**2 * t * t)


def elond_level(alpha: float, t: int, discoveries_before: int) -> float:
    """alpha_t for the t-th test given the number of earlier discoveries."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    return alpha * elond_gamma(t) * (discoveries_before + 1)


def is_discovery(log_e: float, alpha_t: float) -> bool:
    """e >= 1 / alpha_t, compared on the log scale."""
    return log_e >= -math.log(alpha_t)
