"""Tests for the discovery loop: evidence validity, e-LOND, ledger, policy, rounds."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from vitiligo.discovery.evidence import (
    elond_gamma,
    elond_level,
    is_discovery,
    superiority_log_e,
)
from vitiligo.discovery.ledger import Ledger, verify_seal
from vitiligo.discovery.policy import ThompsonPolicy, arm_name
from vitiligo.models.jak_mbma import freeze
from vitiligo.reports.jak_arms import ArmEndpointRow

# ------------------------------------------------------------------ evidence


@pytest.mark.parametrize(
    ("p_control", "margin", "alt_active", "alt_control", "n_active", "n_control"),
    [
        (0.07, 0.00, 0.30, 0.07, 220, 110),
        (0.10, 0.10, 0.40, 0.10, 60, 60),
        (0.30, 0.00, 0.31, 0.30, 400, 200),
    ],
)
def test_e_value_is_valid_on_the_null_boundary(
    p_control: float,
    margin: float,
    alt_active: float,
    alt_control: float,
    n_active: int,
    n_control: int,
) -> None:
    """Universal inference: E[e] <= 1 when the truth sits exactly on the null boundary."""
    rng = np.random.default_rng(1)
    p_active = p_control + margin
    e = np.array(
        [
            math.exp(
                superiority_log_e(
                    int(rng.binomial(n_active, p_active)),
                    n_active,
                    int(rng.binomial(n_control, p_control)),
                    n_control,
                    predicted_active=alt_active,
                    predicted_control=alt_control,
                    margin=margin,
                )
            )
            for _ in range(5000)
        ]
    )
    assert e.mean() <= 1.0 + 4 * e.std() / math.sqrt(len(e))
    assert (e >= 20).mean() <= 0.05  # Markov: P(e >= 1/a) <= a


def test_e_value_rewards_true_effects_and_never_beats_the_mle() -> None:
    strong = superiority_log_e(66, 221, 8, 109, predicted_active=0.30, predicted_control=0.07)
    assert strong / math.log(10) > 4  # TRuE-V1-sized effect: overwhelming evidence
    # Observed difference inside the null: the alternative cannot beat the MLE.
    assert superiority_log_e(10, 100, 10, 100, predicted_active=0.5, predicted_control=0.1) <= 0
    assert (
        superiority_log_e(
            30, 100, 20, 100, predicted_active=0.5, predicted_control=0.1, margin=0.15
        )
        <= 0
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"r_active": 5, "n_active": 0, "r_control": 0, "n_control": 10},
        {"r_active": 11, "n_active": 10, "r_control": 0, "n_control": 10},
    ],
)
def test_e_value_rejects_impossible_counts(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        superiority_log_e(**kwargs, predicted_active=0.5, predicted_control=0.1)


def test_elond_levels() -> None:
    assert abs(sum(elond_gamma(t) for t in range(1, 200_001)) - 1.0) < 1e-5
    assert elond_level(0.1, 1, 0) == pytest.approx(0.1 * 6 / math.pi**2)
    assert elond_level(0.1, 3, 2) == pytest.approx(3 * elond_level(0.1, 3, 0))
    assert is_discovery(math.log(20.0), 0.05)
    assert not is_discovery(math.log(19.9), 0.05)


# -------------------------------------------------------------- ledger/policy


def test_ledger_round_trip_and_seal_checks(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.db")
    assert (ledger.next_test_index(), ledger.discoveries()) == (1, 0)
    spec = {"family": "x", "unit_key": "u1"}
    hid = ledger.record_hypothesis(
        family="x", statement="s", spec=spec, tier=1, status="proposed", belief=0.9
    )
    assert (
        ledger.record_hypothesis(
            family="x", statement="s", spec=spec, tier=1, status="proposed", belief=0.9
        )
        == hid
    )  # deduplicated by spec hash
    ledger.record_test(
        hypothesis_id=hid, t=1, unit_key="u1", round_id="r", trial="T1", arm="k75-d0.00", log_e=5.0,
        alpha_t=0.06, discovery=True, status="discovery", observed={}, predicted={},
    )  # fmt: skip
    ledger.record_policy_events("r", "T1", [("k75-d0.00", 1.0)])
    assert ledger.next_test_index() == 2
    assert ledger.discoveries() == 1
    assert ledger.consumed_units() == {"u1"}
    assert ledger.arm_stats() == {"k75-d0.00": (1.0, 1.0)}
    # A trial's own history is invisible when choosing what to test on it.
    assert ledger.arm_stats(exclude_trial="T1") == {}
    assert ledger.discoveries(exclude_trial="T1") == 0
    assert ledger.discoveries(exclude_trial="T2") == 1

    record = freeze({"label": "forecast", "prediction": {"p": 0.5}})
    assert verify_seal(record)
    assert ledger.import_forecast(record, "f.json") is True
    assert ledger.import_forecast(record, "f.json") is False
    tampered = {**record, "prediction": {"p": 0.9}}
    assert not verify_seal(tampered)
    with pytest.raises(ValueError):
        ledger.import_forecast(tampered, "bad.json")
    assert ledger.summary()["forecasts_by_status"] == {"pending": 1}


def test_policy_learns_from_rewards() -> None:
    stats = {arm_name(75, 0.0): (40.0, 50.0), arm_name(75, 0.15): (2.0, 50.0)}
    picks = [
        ThompsonPolicy(stats, np.random.default_rng(i)).choose(sorted(stats))[0] for i in range(200)
    ]
    assert picks.count(arm_name(75, 0.0)) > 190
    with pytest.raises(ValueError):
        ThompsonPolicy({}, np.random.default_rng(0)).choose([])


# ---------------------------------------------------------------------- loop


def _row(
    trial: str, role: str, agent: str | None, threshold: int, r: int, n: int = 100,
    dose: float = 10.0,
) -> ArmEndpointRow:  # fmt: skip
    active = role == "active"
    return ArmEndpointRow(
        study_id=trial, source_id=trial, trial_agents=agent or "", arm_label=f"{agent} {dose:g} mg" if active else "Placebo",
        period=None, arm_role=role, arm_agent=agent if active else None, dose_value=dose if active else None,
        dose_unit="mg" if active else None, loading_dose_value=None, frequency="QD" if active else None,
        route="oral" if active else None, phototherapy=False, endpoint=f"F-VASI{threshold}", instrument="F-VASI",
        threshold=threshold, body_region="face", assessor=None, week=24, week_source="outcome_title",
        outcome_type="PRIMARY", n_analyzed=n, percent=100 * r / n, responders=r, responders_derived=False,
        value_raw=str(r), outcome_title="t", row_label=None, flags=[],
    )  # fmt: skip


class _StubPosterior:
    def __init__(self, data: Any) -> None:
        self.data = data


def test_loop_spends_each_unit_once_and_never_trains_on_the_test_trial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vitiligo.discovery import loop

    rows = [
        _row("GOOD", "active", "goodnib", 50, 70), _row("GOOD", "active", "goodnib", 75, 60),
        _row("GOOD", "placebo", None, 50, 15), _row("GOOD", "placebo", None, 75, 10),
        _row("NULL", "active", "nullnib", 50, 15), _row("NULL", "active", "nullnib", 75, 10),
        _row("NULL", "placebo", None, 50, 15), _row("NULL", "placebo", None, 75, 10),
    ]  # fmt: skip
    fitted_on: list[list[str]] = []

    def fake_fit(data: Any, settings: Any) -> _StubPosterior:
        fitted_on.append(sorted(data.trials))
        return _StubPosterior(data)

    def fake_draws(posterior: Any, scenario: Any, **_: Any) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(0)
        control = np.clip(0.1 + 0.01 * rng.standard_normal(1000), 0.01, 0.99)
        lift = 0.5 if scenario.agent == "goodnib" else 0.0  # the model believes goodnib only
        return np.clip(control + lift, 0.01, 0.99), control

    monkeypatch.setattr(loop, "predict_draws", fake_draws)
    ledger = Ledger(tmp_path / "ledger.db")
    logs = loop.run_discovery(
        rows, ledger, loop.LoopConfig(instruments=("F-VASI",)), fit_fn=fake_fit,
        converged_fn=lambda _p: True,
    )  # fmt: skip

    # Every round's generator model excluded that round's trial.
    assert [log.trial not in fitted for log, fitted in zip(logs, fitted_on, strict=True)] == [
        True,
        True,
    ]
    by_trial = {log.trial: log for log in logs}
    assert len(by_trial["GOOD"].tests) == 1 and by_trial["GOOD"].tests[0]["status"] == "discovery"
    assert (len(by_trial["NULL"].tests), by_trial["NULL"].abstained) == (0, 1)
    assert ledger.summary()["tests"] == 1

    # A second run: GOOD's unit is spent; NULL abstains again (abstaining spends nothing).
    again = loop.run_discovery(
        rows, ledger, loop.LoopConfig(instruments=("F-VASI",)), fit_fn=fake_fit,
        converged_fn=lambda _p: True,
    )  # fmt: skip
    assert [log.trial for log in again] == ["NULL"]
    assert ledger.summary()["tests"] == 1
    assert ledger.summary()["hypotheses_by_status"] == {"abstained": 1, "discovery": 1}
    assert sum(n for _r, n in ledger.arm_stats().values()) == 1.0


def test_loop_skips_unconverged_fits_without_spending(tmp_path: Path) -> None:
    from vitiligo.discovery import loop

    rows = [_row("GOOD", "active", "goodnib", 50, 70), _row("GOOD", "placebo", None, 50, 15)]
    logs = loop.run_discovery(
        rows, Ledger(tmp_path / "l.db"), loop.LoopConfig(instruments=("F-VASI",)),
        fit_fn=lambda data, settings: _StubPosterior(data), converged_fn=lambda _p: False,
    )  # fmt: skip
    assert logs[0].tests == [] and "did not converge" in logs[0].notes[0]


def test_import_forecasts_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    import vitiligo.config as cfg
    from vitiligo.cli import app

    folder = tmp_path / "forecasts"
    folder.mkdir()
    (folder / "f1.json").write_text(json.dumps(freeze({"label": "a", "prediction": {"p": 0.4}})))
    (folder / "backtest.json").write_text(json.dumps({"leave_one_trial_out": {}}))
    monkeypatch.setenv("VITILIGO_LEDGER_PATH", str(tmp_path / "ledger.db"))
    cfg._settings = None
    result = CliRunner().invoke(app, ["discover", "import-forecasts", str(folder)])
    assert result.exit_code == 0, result.output
    assert "imported" in result.output and "backtest" not in result.output
    assert Ledger(tmp_path / "ledger.db").summary()["forecasts_by_status"] == {"pending": 1}


def test_mixture_e_value_matches_point_and_stays_valid() -> None:
    from vitiligo.discovery.evidence import mixture_log_e

    point = superiority_log_e(66, 221, 8, 109, predicted_active=0.3, predicted_control=0.07)
    single = mixture_log_e(
        66, 221, 8, 109, alt_active=np.array([0.3]), alt_control=np.array([0.07])
    )
    assert single[0] == pytest.approx(point, abs=1e-6)

    rng = np.random.default_rng(5)
    alt_a = np.clip(rng.normal(0.45, 0.12, 300), 0.01, 0.99)
    alt_c = np.clip(rng.normal(0.20, 0.08, 300), 0.01, 0.99)
    r_a, r_c = (
        rng.binomial(60, 0.30, 20000),
        rng.binomial(60, 0.20, 20000),
    )  # null boundary, margin .1
    e = np.exp(mixture_log_e(r_a, 60, r_c, 60, alt_active=alt_a, alt_control=alt_c, margin=0.10))
    assert e.mean() <= 1.0 + 4 * e.std() / math.sqrt(len(e))


def test_discovery_power_tracks_sample_size() -> None:
    from vitiligo.discovery.evidence import discovery_power

    rng = np.random.default_rng(2)
    control = np.clip(0.1 + 0.02 * rng.standard_normal(1000), 0.01, 0.99)
    active = np.clip(control + 0.25, 0.01, 0.99)
    kwargs = {"draws_active": active, "draws_control": control, "margin": 0.0, "alpha_t": 0.05}
    assert discovery_power(n_active=200, n_control=200, **kwargs) > 0.9
    assert discovery_power(n_active=6, n_control=6, **kwargs) < 0.5
    assert discovery_power(n_active=200, n_control=200, **{**kwargs, "margin": 0.5}) == 0.0


def test_loop_abstains_when_predicted_power_is_low(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A believed claim on a tiny trial is not tested: it would waste budget."""
    from vitiligo.discovery import loop

    rows = [
        _row("TINY", "active", "goodnib", 50, 4, n=6),
        _row("TINY", "placebo", None, 50, 1, n=6),
        _row("OTHER", "active", "goodnib", 50, 70),
        _row("OTHER", "placebo", None, 50, 15),
    ]

    def fake_draws(posterior: Any, scenario: Any, **_: Any) -> tuple[np.ndarray, np.ndarray]:
        control = np.full(1000, 0.1)
        return control + 0.3, control

    monkeypatch.setattr(loop, "predict_draws", fake_draws)
    ledger = Ledger(tmp_path / "ledger.db")
    logs = loop.run_discovery(
        rows, ledger, loop.LoopConfig(instruments=("F-VASI",)),
        fit_fn=lambda data, settings: _StubPosterior(data), converged_fn=lambda _p: True,
    )  # fmt: skip
    tiny = next(log for log in logs if log.trial == "TINY")
    assert (tiny.tests, tiny.abstained) == ([], 1)
    assert tiny.abstain_reasons == {"low predicted power": 1}
    assert not any("TINY" in key for key in ledger.consumed_units())


# ------------------------------------------------------------ v1 families


@pytest.mark.parametrize(
    ("p_y", "ratio", "margin", "n_x", "n_y"),
    [(0.40, 0.50, 0.0, 60, 60), (0.30, 0.75, 0.0, 45, 45), (0.20, 1.0, -0.10, 50, 50)],
)
def test_linear_null_e_value_is_valid_on_the_boundary(
    p_y: float, ratio: float, margin: float, n_x: int, n_y: int
) -> None:
    """E[e] <= 1 at p_x = ratio * p_y + margin (retention and non-unit nulls)."""
    from vitiligo.discovery.evidence import mixture_log_e

    rng = np.random.default_rng(11)
    p_x = ratio * p_y + margin
    alt_y = np.clip(rng.normal(p_y, 0.08, 300), 0.01, 0.99)
    alt_x = np.clip(alt_y * (ratio + 0.4), 0.01, 0.99)  # claim holds in the alternative
    e = np.exp(
        mixture_log_e(
            rng.binomial(n_x, p_x, 20000), n_x, rng.binomial(n_y, p_y, 20000), n_y,
            alt_active=alt_x, alt_control=alt_y, margin=margin, ratio=ratio,
        )
    )  # fmt: skip
    assert e.mean() <= 1.0 + 4 * e.std() / math.sqrt(len(e))
    assert (e >= 20).mean() <= 0.05


def test_retention_power_needs_informative_rates() -> None:
    """'Keeps half the response' cannot be shown when hardly anyone responds."""
    from vitiligo.discovery.evidence import discovery_power

    rng = np.random.default_rng(3)
    upper = np.clip(rng.normal(0.02, 0.005, 1000), 0.001, 0.99)
    kwargs = {"ratio": 0.5, "margin": 0.0, "alpha_t": 0.05}
    assert (
        discovery_power(
            n_active=40, n_control=40, draws_active=upper, draws_control=upper, **kwargs
        )
        < 0.1
    )
    upper = np.clip(rng.normal(0.45, 0.03, 1000), 0.01, 0.99)
    assert (
        discovery_power(
            n_active=200, n_control=200, draws_active=upper, draws_control=upper, **kwargs
        )
        > 0.9
    )
    with pytest.raises(ValueError):
        from vitiligo.discovery.evidence import mixture_log_e

        mixture_log_e(1, 10, 1, 10, alt_active=upper, alt_control=upper, ratio=0.0)  # fmt: skip


def _arm(label: str, dose: float | None, load: float | None = None, photo: bool = False,
         agent: str | None = "nib", unit: str | None = "mg") -> Any:  # fmt: skip
    from vitiligo.models.jak_mbma import ArmInfo

    return ArmInfo(
        source_id="T", label=label, active=agent is not None, agent=agent, daily_dose=dose,
        dose_unit=unit if agent else None, loading=load is not None, phototherapy=photo,
        loading_dose=load,
    )  # fmt: skip


def test_more_intensive_is_a_partial_order_within_one_agent() -> None:
    from vitiligo.discovery.loop import more_intensive

    hi, lo = _arm("50", 50.0), _arm("10", 10.0)
    loaded, loaded_more = _arm("100-50", 50.0, 100.0), _arm("200-50", 50.0, 200.0)
    assert more_intensive(hi, lo) and not more_intensive(lo, hi)
    assert more_intensive(loaded_more, loaded) and more_intensive(loaded, hi)
    assert more_intensive(_arm("50+UVB", 50.0, photo=True), hi)
    assert not more_intensive(hi, hi)
    assert not more_intensive(_arm("30 + load", 30.0, 100.0), hi)  # incomparable
    assert not more_intensive(hi, _arm("other", 10.0, agent="othernib"))
    assert not more_intensive(hi, _arm("1%", 1.0, unit="%"))
    assert not more_intensive(hi, _arm("Placebo", None, agent=None))


def _stub_posterior(tau: float) -> Any:
    from vitiligo.models.jak_mbma import MBMAData, Posterior

    n = 4000
    full = lambda v: np.full(n, float(v))  # noqa: E731
    draws = {
        "mu0": full(-1.5), "sigma_mu": full(0.5), "pi": full(0.0), "cut": np.zeros((n, 1)),
        "T50": np.full((n, 1), 20.0), "routes": np.array(["oral"]), "trial_route": np.array([0]),
        "alpha": np.full((n, 1), 1.0), "beta": np.full((n, 1), 0.5), "alpha_route": np.full((n, 1), 1.0),
        "omega_alpha": full(0.5), "beta_class": full(0.5), "omega_beta": full(0.0), "tau": full(tau),
        "lambda": full(0.2), "phi": full(0.3), "arm_eps_position": np.array([], dtype=int),
        "eps_z": np.zeros((n, 0)),
    }  # fmt: skip
    data = MBMAData(
        instrument="F-VASI", thresholds=[50], trials=["A"], arms=[], agents=["seen"],
        reference_dose={"seen": 50.0}, observations=[], agent_route={"seen": "oral"},
    )  # fmt: skip
    return Posterior(data=data, draws=draws, diagnostics={})


@pytest.mark.parametrize("agent", ["seen", "unseen"])
def test_pair_draws_share_trial_and_agent_but_not_arm_deviations(agent: str) -> None:
    pytest.importorskip("scipy")  # installed with the optional [model] extra
    from vitiligo.models.jak_mbma import Scenario, predict_draws, predict_pair_draws

    def sc(dose: float) -> Scenario:
        return Scenario(agent=agent, dose=dose, dose_unit="mg", frequency=None, week=24,
                        threshold=50, route="oral")  # fmt: skip

    same_hi, same_lo = predict_pair_draws(_stub_posterior(tau=0.0), sc(50.0), sc(10.0))
    # No arm deviation: the higher dose is higher in *every* draw (shared baseline
    # and agent effect), including for an agent the model has not seen.
    assert np.all(same_hi > same_lo)
    # Two separate predict_draws calls would erase the dose effect for an unseen
    # agent (each call's reference dose is its own dose).
    if agent == "unseen":
        hi, _ = predict_draws(_stub_posterior(tau=0.0), sc(50.0))
        lo, _ = predict_draws(_stub_posterior(tau=0.0), sc(10.0))
        assert np.allclose(hi, lo)
    # With arm deviations the two arms are no longer locked together.
    hi, lo = predict_pair_draws(_stub_posterior(tau=0.3), sc(50.0), sc(10.0))
    assert 0.0 < np.mean(hi > lo) < 1.0
    with pytest.raises(ValueError):
        predict_pair_draws(
            _stub_posterior(tau=0.0), sc(50.0), Scenario(agent="x", dose=1.0, dose_unit="mg")
        )


def test_loop_tests_regimen_pairs_with_contrast_and_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vitiligo.discovery import loop

    rows = [
        _row("DOSE", "active", "dosenib", 50, 70, n=200, dose=30.0),
        _row("DOSE", "active", "dosenib", 50, 20, n=200, dose=10.0),
        _row("DOSE", "placebo", None, 50, 10, n=200),
        _row("SAME", "active", "flatnib", 50, 60, n=200, dose=30.0),
        _row("SAME", "active", "flatnib", 50, 58, n=200, dose=10.0),
    ]

    def fake_pair(
        posterior: Any, first: Any, second: Any, **_: Any
    ) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(1)
        lower = np.clip(0.3 + 0.03 * rng.standard_normal(2000), 0.01, 0.99)
        if first.agent == "dosenib":  # the model believes in a steep dose response
            return np.clip(lower + 0.25, 0.01, 0.99), np.clip(lower - 0.2, 0.01, 0.99)
        return lower + 0.01, lower  # ... and a flat one for flatnib

    def fake_draws(posterior: Any, scenario: Any, **_: Any) -> tuple[np.ndarray, np.ndarray]:
        return np.full(2000, 0.12), np.full(2000, 0.05)  # superiority: not believed strongly

    monkeypatch.setattr(loop, "predict_pair_draws", fake_pair)
    monkeypatch.setattr(loop, "predict_draws", fake_draws)
    ledger = Ledger(tmp_path / "ledger.db")
    logs = loop.run_discovery(
        rows, ledger, loop.LoopConfig(instruments=("F-VASI",), thresholds=(50,)),
        fit_fn=lambda data, settings: _StubPosterior(data), converged_fn=lambda _p: True,
    )  # fmt: skip
    tests = {log.trial: log.tests for log in logs}
    [dose_test] = [t for t in tests["DOSE"] if t["family"] != loop.SUPERIORITY]
    assert dose_test["family"] == loop.CONTRAST and dose_test["status"] == "discovery"
    assert dose_test["statement"].startswith("dosenib 30 mg beats dosenib 10 mg by more than")
    [flat_test] = tests["SAME"]
    assert flat_test["family"] == loop.RETENTION and flat_test["status"] == "discovery"
    assert flat_test["statement"].startswith("flatnib 10 mg keeps more than")
    assert all(key.startswith("pair|") for key in ledger.consumed_units())


def test_ledger_migrates_trial_columns_from_round_ids(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:  # the v0.1 layout, without trial columns
        conn.executescript(
            """
            CREATE TABLE tests (id INTEGER PRIMARY KEY, t INTEGER NOT NULL UNIQUE,
                hypothesis_id INTEGER NOT NULL, unit_key TEXT NOT NULL UNIQUE,
                round_id TEXT NOT NULL, arm TEXT NOT NULL, log_e REAL NOT NULL,
                alpha_t REAL NOT NULL, discovery INTEGER NOT NULL, observed_json TEXT NOT NULL,
                predicted_json TEXT NOT NULL, tested_at TEXT NOT NULL);
            CREATE TABLE policy_events (id INTEGER PRIMARY KEY, round_id TEXT NOT NULL,
                arm TEXT NOT NULL, reward REAL NOT NULL, created_at TEXT NOT NULL);
            INSERT INTO tests VALUES (1, 1, 1, 'u', '20261014T114531-NCT04052425', 'k75-d0.00',
                8.5, 0.06, 1, '{}', '{}', 'now');
            INSERT INTO policy_events VALUES (1, '20261014T114531-NCT04052425', 'k75-d0.00', 1.0, 'now');
            """
        )  # fmt: skip
    ledger = Ledger(path)
    assert ledger.discoveries(exclude_trial="NCT04052425") == 0
    assert ledger.discoveries(exclude_trial="NCT04057573") == 1
    assert ledger.arm_stats(exclude_trial="NCT04052425") == {}
