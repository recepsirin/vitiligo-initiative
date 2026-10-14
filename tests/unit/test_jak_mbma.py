"""Tests for the JAK scenario model (dataset shaping always; fitting only with PyMC)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from vitiligo.models.jak_mbma import (
    DESIGN_ANNOTATIONS,
    Scenario,
    build_dataset,
    daily_dose,
    freeze,
)
from vitiligo.reports.jak_arms import ArmEndpointRow


def _row(**kwargs: Any) -> ArmEndpointRow:
    base: dict[str, Any] = {
        "study_id": "NCT1",
        "source_id": "NCT1",
        "trial_agents": "ritlecitinib",
        "arm_label": "Ritlecitinib 50 mg QD",
        "period": None,
        "arm_role": "active",
        "arm_agent": "ritlecitinib",
        "dose_value": 50.0,
        "dose_unit": "mg",
        "loading_dose_value": None,
        "frequency": "QD",
        "route": "oral",
        "phototherapy": False,
        "endpoint": "F-VASI75",
        "instrument": "F-VASI",
        "threshold": 75,
        "body_region": "face",
        "assessor": None,
        "week": 24,
        "week_source": "outcome_title",
        "outcome_type": "SECONDARY",
        "n_analyzed": 100,
        "percent": 20.0,
        "responders": 20,
        "responders_derived": True,
        "value_raw": "20",
        "outcome_title": "F-VASI75 at Week 24",
        "row_label": None,
        "flags": [],
    }
    base.update(kwargs)
    return ArmEndpointRow(**base)


def _placebo(**kwargs: Any) -> ArmEndpointRow:
    return _row(
        arm_label="Placebo",
        arm_role="placebo",
        arm_agent=None,
        dose_value=None,
        dose_unit=None,
        frequency=None,
        **kwargs,
    )


def test_daily_dose_scales_by_frequency() -> None:
    assert daily_dose(1.5, "BID") == 3.0
    assert daily_dose(50.0, "QD") == 50.0
    assert daily_dose(50.0, None) == 50.0
    assert daily_dose(None, "BID") is None


def test_build_dataset_nests_thresholds_and_clips() -> None:
    rows = [
        _row(threshold=50, responders=40),
        _row(threshold=75, responders=20),
        _row(threshold=90, responders=25),  # rounding artefact above F-VASI75: clipped
        _placebo(threshold=50, responders=5),
    ]
    data = build_dataset(rows, "F-VASI")
    active = next(o for o in data.observations if data.arms[o.arm].active)
    assert active.thresholds == (50, 75, 90)
    assert active.responders == (40, 20, 20)
    assert data.reference_dose == {"ritlecitinib": 50.0}


def test_build_dataset_prefers_central_reads_and_applies_exclusions() -> None:
    rows = [
        _row(assessor="central", responders=20),
        _row(assessor="local", responders=30),
        _row(source_id="NCT2", flags=["treatment_changes_within_arm"]),
        _row(source_id="NCT3", flags=["extension_study"]),
        _row(source_id="NCT4", flags=["extension_period"]),  # continuation: kept
        _row(source_id="NCT5", arm_role="sequence"),
        _row(source_id="NCT6", week=None),
    ]
    data = build_dataset(rows, "F-VASI")
    assert sorted(data.trials) == ["NCT1", "NCT4"]
    nct1 = next(o for o in data.observations if data.arms[o.arm].source_id == "NCT1")
    assert nct1.responders == (20,)
    assert data.excluded == {
        "local read where central exists": 1,
        "treatment switch or extension study": 2,
        "arm role": 1,
        "week, n or responders missing": 1,
    }


def test_build_dataset_keeps_loading_regimens_apart() -> None:
    rows = [
        _row(arm_label="200 mg - 50 mg", loading_dose_value=200.0, responders=12),
        _row(arm_label="100 mg - 50 mg", loading_dose_value=100.0, responders=8),
        _row(arm_label="50 mg", responders=7),
    ]
    data = build_dataset(rows, "F-VASI")
    assert sorted((a.loading_dose or 0.0) for a in data.arms) == [0.0, 100.0, 200.0]
    assert len(data.observations) == 3


def test_build_dataset_design_annotation_and_holdout() -> None:
    annotated = next(iter(DESIGN_ANNOTATIONS))
    cap = DESIGN_ANNOTATIONS[annotated]["max_week"]
    rows = [
        _row(source_id=annotated, week=cap),
        _row(source_id=annotated, week=cap + 28),
        _placebo(source_id="NCT9"),
        _row(source_id="NCT9"),
    ]
    data = build_dataset(rows, "F-VASI", drop=[("NCT9", True)])
    weeks = {
        (data.arms[o.arm].source_id, data.arms[o.arm].active, o.week) for o in data.observations
    }
    assert weeks == {(annotated, True, cap), ("NCT9", False, 24)}
    assert data.excluded["design annotation: post-randomization selection"] == 1
    assert data.excluded["held out"] == 1


def test_freeze_seals_content() -> None:
    import hashlib
    import json

    record = freeze({"label": "x", "value": 1})
    body = {k: v for k, v in record.items() if k != "sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    assert record["sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert record["frozen_at"]


@pytest.mark.model
def test_fit_recovers_simulated_parameters() -> None:
    """Simulation check: data generated from known parameters are recovered."""
    pytest.importorskip("pymc")
    from scipy.special import ndtr

    from vitiligo.models.jak_mbma import FitSettings, fit, predict

    rng = np.random.default_rng(3)
    cuts = {50: 0.0, 75: 0.7, 90: 1.4}
    alpha, beta, t50, mu0 = 1.2, 0.4, 16.0, -1.4
    rows: list[ArmEndpointRow] = []
    for t in range(4):
        mu = mu0 + 0.3 * rng.standard_normal()
        for week in (12, 24):
            h = (week / (week + t50)) * ((24 + t50) / 24)
            for dose in (None, 10.0, 30.0):  # placebo, two active doses
                effect = 0.0 if dose is None else (alpha + beta * np.log(dose / 30.0)) * h
                n, prev = 400, None
                for k, c in cuts.items():
                    p = float(ndtr(mu + effect - c))
                    r = (
                        int(rng.binomial(n, p))
                        if prev is None
                        else min(prev, int(rng.binomial(n, p)))
                    )
                    prev = r
                    kw = {
                        "source_id": f"SIM{t}",
                        "week": week,
                        "threshold": k,
                        "responders": r,
                        "n_analyzed": n,
                        "percent": 100 * r / n,
                    }
                    rows.append(_placebo(**kw) if dose is None else _row(dose_value=dose, **kw))
    posterior = fit(build_dataset(rows, "F-VASI"), FitSettings(draws=500, tune=800, chains=2))
    d = posterior.draws
    lo, hi = np.quantile(d["alpha"][:, 0], [0.025, 0.975])
    assert lo <= alpha <= hi
    lo, hi = np.quantile(d["cut"][:, posterior.data.thresholds.index(75)], [0.025, 0.975])
    assert lo <= cuts[75] <= hi

    truth = float(ndtr(mu0 + alpha - cuts[75]))  # new trial, 30 mg, week 24, threshold 75
    pred = predict(posterior, Scenario("ritlecitinib", 30.0, "mg", "QD", 24, 75))
    assert pred["p_active"]["lo95"] <= truth <= pred["p_active"]["hi95"]
    assert pred["extrapolation"] == []


# ----------------------------------------------------------------- v0.3


def test_v03_data_rules_for_paper_rows() -> None:
    """As-observed rows are excluded; paper rows pass the registry-only week cap."""
    trial = next(iter(DESIGN_ANNOTATIONS))
    cap = DESIGN_ANNOTATIONS[trial]["max_week"]
    rows = [
        _row(source_id=trial, study_id=trial, week=cap),
        _placebo(source_id=trial, study_id=trial, week=cap),
        _row(source_id=trial, study_id=trial, week=cap + 28),  # registry, past the cap
        _row(source_id=trial, study_id=trial, week=cap + 28, threshold=90, endpoint="F-VASI90",
             responders=5, flags=["from_publication", "population:nri"]),
        _row(source_id=trial, study_id=trial, week=cap + 80,
             flags=["from_publication", "population:as_observed"]),
    ]  # fmt: skip
    data = build_dataset(rows, "F-VASI", trial_phase3={trial: True})
    weeks = sorted({o.week for o in data.observations})
    assert weeks == [cap, cap + 28]  # only the paper row survives past the cap
    later = next(o for o in data.observations if o.week == cap + 28)
    assert later.thresholds == (90,)
    assert (
        data.excluded["as-observed population (not comparable with non-responder imputation)"] == 1
    )
    assert data.trial_phase3 == {trial: True}


def _v03_posterior(*, version: str) -> Any:
    from vitiligo.models.jak_mbma import MBMAData, Posterior

    n = 2000
    data = MBMAData(
        instrument="F-VASI", thresholds=[50], trials=["P2", "P3"], arms=[], agents=["nib"],
        reference_dose={"nib": 50.0}, observations=[], agent_route={"nib": "oral"},
        trial_phase3={"P2": False, "P3": True},
    )  # fmt: skip
    draws: dict[str, Any] = {
        "mu0": np.full(n, -1.5), "sigma_mu": np.full(n, 0.0), "mu": np.full((n, 2), -1.5),
        "pi": np.zeros(n), "cut": np.zeros((n, 1)), "T50": np.full((n, 1), 20.0),
        "routes": np.array(["oral"]), "trial_route": np.array([0, 0]),
        "trial_phase3": np.array([0.0, 1.0]), "alpha": np.full((n, 1), 1.0),
        "beta": np.full((n, 1), 0.0), "lambda": np.zeros(n), "phi": np.zeros(n),
        "tau": np.zeros(n), "eps_z": np.zeros((n, 0)), "arm_eps_position": np.array([], dtype=int),
    }  # fmt: skip
    if version == "v0.3":
        draws |= {"sigma_gamma": np.full(n, 0.4), "gamma": np.tile([0.2, -0.3], (n, 1)),
                  "kappa": np.full((n, 1), -0.8)}  # fmt: skip
    return Posterior(data=data, draws=draws, diagnostics={})


def test_v03_trial_effect_and_phase_shift() -> None:
    from vitiligo.models.jak_mbma import _trial_effect

    sc = Scenario(agent="nib", dose=50, dose_unit="mg", week=24, threshold=50)
    rng = np.random.default_rng(0)
    state = rng.bit_generator.state
    assert _trial_effect(_v03_posterior(version="v0.2"), sc, None, rng) == 0.0
    assert rng.bit_generator.state == state  # v0.2 predictions stay reproducible
    v03 = _v03_posterior(version="v0.3")
    assert np.allclose(_trial_effect(v03, sc, "P2", rng), 0.2)  # fitted gamma, phase 2
    assert np.allclose(_trial_effect(v03, sc, "P3", rng), -0.3 - 0.8)  # gamma + phase 3 shift
    new_p3 = _trial_effect(v03, Scenario(**{**sc.__dict__, "phase3": True}), None, rng)
    assert abs(float(np.mean(new_p3)) + 0.8) < 0.05 and abs(float(np.std(new_p3)) - 0.4) < 0.03


def test_toplines_load_with_derived_responders() -> None:
    from pathlib import Path

    from vitiligo.reports.paper_results import load_toplines

    rows = load_toplines(Path("curation/topline-results.json"))
    assert len(rows) == 16
    tranquillo = next(r for r in rows if r.source_id == "NCT05583526" and r.arm_role == "active"
                      and r.instrument == "F-VASI")  # fmt: skip
    assert (tranquillo.responders, tranquillo.n_analyzed) == (50, 401)  # 12.5% of 401
    assert all("from_topline" in r.flags and r.responders_derived for r in rows)


def test_v05_new_trial_baseline_follows_its_route() -> None:
    from vitiligo.models.jak_mbma import _new_baseline

    post = _v03_posterior(version="v0.3")
    post.data.agent_route["cream"] = "topical"
    post.draws["routes"] = np.array(["oral", "topical"])
    post.draws["mu0_route"] = np.tile([-2.5, -1.0], (2000, 1))
    oral = _new_baseline(
        post, Scenario(agent="nib", dose=50, dose_unit="mg"), np.random.default_rng(0)
    )
    topical = _new_baseline(
        post, Scenario(agent="cream", dose=3, dose_unit="%"), np.random.default_rng(0)
    )
    assert np.allclose(oral, -2.5) and np.allclose(topical, -1.0)  # sigma_mu is 0 in the stub
    del post.draws["mu0_route"]  # earlier versions: the shared mean, same random stream
    assert np.allclose(
        _new_baseline(
            post, Scenario(agent="cream", dose=3, dose_unit="%"), np.random.default_rng(0)
        ),
        -1.5,
    )
