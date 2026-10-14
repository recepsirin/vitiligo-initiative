"""Correctness checks for the simulator: closed form vs brute force, integration, recovery."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import multinomial
from vsim.data import ArmWeek
from vsim.program import (
    GRID,
    THRESHOLDS,
    Context,
    Model,
    Spec,
    build_design,
    fit_program,
    predict,
)
from vsim.score import bin_counts, bin_probabilities, log_predictive

CTX = Context(
    agent_route={"nib": "oral", "cream": "topical"},
    reference={"nib": 50.0, "cream": 3.0},
    oral_trials=frozenset({"T1"}),
)


def _aw(trial: str, active: bool, week: int, dose: float | None = None, load: float | None = None,
        agent: str = "nib", photo: bool = False, instrument: str = "F-VASI", n: int = 100,
        responders: tuple[int, ...] = (60, 40, 20, 10, 2)) -> ArmWeek:  # fmt: skip
    return ArmWeek(
        instrument=instrument, trial=trial, label="x", active=active,
        agent=agent if active else None, daily_dose=dose if active else None,
        dose_unit="mg" if active else None, loading_dose=load, phototherapy=photo, week=week,
        n=n, thresholds=THRESHOLDS, responders=responders,
    )  # fmt: skip


def _theta(model: Model, **values: float) -> np.ndarray:
    theta = model.mean.copy()
    for name, value in values.items():
        theta[model.index[name]] = value
    return theta


def _brute_force(
    theta_g: float, e_fn: object, week: float, tau: float, sigma: float, gamma: float,
    kappa: float, q: float, rng: np.random.Generator, patients: int = 400_000,
) -> np.ndarray:  # fmt: skip
    """P(R >= k) by simulating patients, with A(w) integrated numerically."""
    s = np.linspace(tau, week, 20001)
    exposure = np.trapezoid(np.array([e_fn(t) for t in s]), s)  # type: ignore[operator]
    eta = rng.normal(0.0, sigma, patients)
    lam = np.exp(theta_g + eta) * exposure
    r = 1.0 - np.exp(-(lam**gamma))
    r[rng.random(patients) < q] = 0.0  # non-responders
    cut = [k / 100 for k in THRESHOLDS[:-1]] + [kappa]
    return np.array([(r >= c).mean() for c in cut])


@pytest.mark.parametrize("load", [None, 200.0])
def test_closed_form_matches_patient_simulation(load: float | None) -> None:
    spec = Spec(gamma="free", lag="free", nonresp="shared")
    model = Model(spec, ["nib"])
    theta = _theta(
        model, theta_face=-3.2, alpha_oral=1.1, delta_nib=0.2, beta_oral=0.6, log_sigma=0.3,
        log_gamma=0.25, lag_raw=0.4, kappa_raw=0.5, q_raw=-1.5,
    )  # fmt: skip
    rows = [_aw("T1", True, 16, dose=30.0, load=load), _aw("T1", False, 16)]
    design = build_design(rows, model.spec, CTX, model.agents, [])
    x = theta[None, :]
    loc = model.location(x, design, np.zeros((1, 0)))
    p = model.cumulative(x, design, loc[:, :, None])[0, :, 0, :]

    tau = 3.5 / (1 + math.exp(-0.4))
    kappa = 0.9 + 0.0999 / (1 + math.exp(-0.5))
    e_main = 1.1 + 0.2 + 0.6 * math.log(30 / 50)
    e_load = 1.1 + 0.2 + 0.6 * math.log(200 / 50) if load else e_main
    args = (16.0, tau, math.exp(0.3), math.exp(0.25), kappa, 1 / (1 + math.exp(1.5)))
    rng = np.random.default_rng(0)
    drug = _brute_force(-3.2, lambda t: math.exp(e_load if t < 4 else e_main), *args, rng=rng)
    vehicle = _brute_force(-3.2, lambda t: 1.0, *args, rng=rng)
    assert np.allclose(p[0], drug, atol=0.004)
    assert np.allclose(p[1], vehicle, atol=0.004)


def test_marginal_likelihood_is_insensitive_to_the_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    import vsim.program as prog

    model = Model(Spec(), ["nib"])
    rows = [_aw("T1", True, 24, dose=50.0, n=400, responders=(250, 180, 90, 40, 8)),
            _aw("T1", False, 24, n=400, responders=(90, 40, 12, 4, 0))]  # fmt: skip
    design = build_design(rows, model.spec, CTX, model.agents, [])
    theta = _theta(model, log_sigma_u=math.log(0.8))
    coarse = model.neg_log_posterior(theta, design)
    fine = np.linspace(-8, 8, 4001)
    logw = -0.5 * fine**2
    monkeypatch.setattr(prog, "GRID", fine)
    monkeypatch.setattr(prog, "_GRID_LOGW", logw - np.logaddexp.reduce(logw))
    assert model.neg_log_posterior(theta, design) == pytest.approx(coarse, abs=1e-3)
    assert len(GRID) == 161


def test_fit_recovers_parameters_from_simulated_trials() -> None:
    """Simulate a design like S from known parameters; the fit should land near them."""
    rng = np.random.default_rng(3)
    model = Model(Spec(), ["nib"])
    truth = _theta(model, theta_face=-4.5, theta_body=-5.3, alpha_oral=1.2, delta_nib=0.0,
                   beta_oral=0.4, log_sigma=math.log(1.3), log_sigma_u=math.log(0.3),
                   kappa_raw=1.0)  # fmt: skip
    rows: list[ArmWeek] = []
    for t in range(12):
        trial = f"T{t}"
        u = rng.normal(0.0, 0.3)
        for instrument in ("F-VASI", "T-VASI"):
            for dose in (None, 10.0, 30.0, 50.0):
                for week in (12, 24):
                    aw = _aw(trial, dose is not None, week, dose=dose, instrument=instrument, n=150)
                    d = build_design([aw], model.spec, CTX, model.agents, [])
                    loc = model.location(truth[None, :], d, np.zeros((1, 0))) + u
                    p = model.cumulative(truth[None, :], d, loc[:, :, None])[0, 0, 0]
                    counts = rng.multinomial(150, bin_probabilities(p[None, :])[0])
                    cum = tuple(int(v) for v in np.cumsum(counts[::-1])[::-1][1:])
                    rows.append(_aw(trial, dose is not None, week, dose=dose,
                                    instrument=instrument, n=150, responders=cum))  # fmt: skip
    ctx = Context(CTX.agent_route, CTX.reference, frozenset(f"T{t}" for t in range(12)))
    fit = fit_program(Spec(), rows, ctx)
    sd = np.sqrt(np.diag(fit.cov))
    for name in ("theta_face", "theta_body", "alpha_oral", "beta_oral", "log_sigma"):
        i = fit.model.index[name]
        assert abs(fit.theta[i] - truth[model.index[name]]) < 3 * sd[i] + 0.05, name


def test_prediction_without_conditioning_rows_uses_the_prior() -> None:
    model = Model(Spec(), ["nib"])
    rows = [_aw("T1", False, 24)]
    fit_rows = rows
    fit = fit_program(Spec(), fit_rows, CTX)
    [p] = predict(fit, [_aw("NEW", True, 24, dose=50.0, agent="cream")], draws=4000, seed=1)
    assert p.shape == (4000, 5)
    assert np.all(np.diff(p, axis=1) <= 1e-12)  # nested thresholds
    assert model.spec == fit.model.spec


def test_score_matches_scipy_multinomial() -> None:
    aw = _aw("T", True, 24, n=50, responders=(30, 20, 10, 4, 1))
    p = np.array([[0.6, 0.4, 0.2, 0.08, 0.02]])
    expected = multinomial.logpmf(bin_counts(aw), 50, bin_probabilities(p)[0])
    assert log_predictive(aw, p) == pytest.approx(expected)
    two = np.vstack([p, p * 0.5])
    lp2 = multinomial.logpmf(bin_counts(aw), 50, bin_probabilities(two[1:])[0])
    assert log_predictive(aw, two) == pytest.approx(np.logaddexp(expected, lp2) - np.log(2))


def test_mutations_are_canonical_and_complete() -> None:
    children = list(Spec().mutations())
    assert len(children) == len(set(children)) == 9  # 8 components, nonresp has 3 options
    assert all(c == c.canonical() for c in children)
    assert Spec(cuts="free", gamma="free").canonical() == Spec(cuts="free")


def test_route_kinetics_reduce_to_shared_and_keep_old_names() -> None:
    shared = Model(Spec(gamma="free", lag="free"), ["nib"])
    routed = Model(Spec(gamma="free", lag="free", kinetics="route"), ["nib"])
    rows = [_aw("T1", True, 16, dose=30.0, load=200.0), _aw("T1", False, 8),
            _aw("T2", True, 24, dose=3.0, agent="cream")]  # fmt: skip
    values = {"theta_face": -3.0, "alpha_oral": 1.0, "alpha_topical": 0.7, "kappa_raw": 0.4}
    a = _theta(shared, **values, log_gamma=0.2, lag_raw=0.3)
    b = _theta(routed, **values, log_gamma_topical=0.2, log_gamma_oral=0.2,
               lag_raw_topical=0.3, lag_raw_oral=0.3)  # fmt: skip
    for model, theta in ((shared, a), (routed, b)):
        d = build_design(rows, model.spec, CTX, ["nib"], ["cream"])
        loc = model.location(theta[None, :], d, np.zeros((1, 1)))
        out = model.cumulative(theta[None, :], d, loc[:, :, None])
        if model is shared:
            ref = out
    assert np.allclose(out, ref)
    # Different onset per route changes only that route's rows.
    b2 = b.copy()
    b2[routed.index["lag_raw_oral"]] = 1.5
    d = build_design(rows, routed.spec, CTX, ["nib"], ["cream"])
    out2 = routed.cumulative(
        b2[None, :], d, routed.location(b2[None, :], d, np.zeros((1, 1)))[:, :, None]
    )
    assert not np.allclose(out2[0, :2], ref[0, :2]) and np.allclose(out2[0, 2], ref[0, 2])
    assert (
        Spec().name
        == "gamma=fixed,lag=none,cuts=mechanistic,sigma=shared,nonresp=none,dose=loglinear,trial=shared,placebo=single"
    )
    assert Spec(kinetics="route").canonical() == Spec()
