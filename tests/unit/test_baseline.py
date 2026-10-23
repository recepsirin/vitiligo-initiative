"""Tests for the simple baselines the scenario model is measured against.

NumPy only, so they run in CI without the ``[model]`` extra.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from vitiligo.models.baseline import (
    EffectSample,
    Observed,
    active_rates,
    control_rates,
    effect_samples,
    expit,
    fits_a_time_trend,
    jeffreys_rate,
    logit,
    metrics,
    paired_error_difference,
    predict_placebo_anchored,
    predict_placebo_anchored_time,
    predict_pooled_rate,
    usable,
)
from vitiligo.reports.jak_arms import ArmEndpointRow

ROUTES = {"ritlecitinib": "oral", "ruxolitinib": "topical"}


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


def _rng() -> np.random.Generator:
    return np.random.default_rng(20261023)


def test_jeffreys_rate_never_hits_the_boundaries() -> None:
    """logit(0) is undefined, and control arms at week 24 are often zero."""
    assert 0 < jeffreys_rate(0, 50) < 1
    assert 0 < jeffreys_rate(50, 50) < 1
    assert jeffreys_rate(20, 100) == pytest.approx(20.5 / 101)


def test_jeffreys_rate_rejects_an_empty_arm() -> None:
    with pytest.raises(ValueError, match="n must be positive"):
        jeffreys_rate(0, 0)


def test_logit_and_expit_round_trip() -> None:
    for p in (0.01, 0.2, 0.5, 0.93):
        assert float(expit(np.array([logit(p)]))[0]) == pytest.approx(p)


def test_expit_does_not_overflow_on_large_log_odds() -> None:
    values = expit(np.array([-1500.0, -40.0, 0.0, 40.0, 1500.0]))
    assert values[0] == 0.0
    assert values[-1] == 1.0
    assert values[2] == pytest.approx(0.5)
    assert np.all(np.isfinite(values))


def test_usable_applies_the_models_own_filters() -> None:
    assert usable(_row(), "F-VASI")
    assert not usable(_row(instrument="T-VASI"), "F-VASI")
    assert not usable(_row(flags=["extension_study"]), "F-VASI")
    assert not usable(_row(flags=["population:as_observed"]), "F-VASI")
    assert not usable(_row(responders=None), "F-VASI")
    assert not usable(_row(n_analyzed=0), "F-VASI")
    assert not usable(_row(week=None), "F-VASI")


def test_usable_respects_a_trials_annotated_maximum_week() -> None:
    """NCT03099304's arms were re-assigned after week 24, so later weeks are excluded."""
    late = _row(source_id="NCT03099304", week=52)
    assert not usable(late, "F-VASI")
    assert usable(_row(source_id="NCT03099304", week=24), "F-VASI")


def test_control_rates_keeps_the_largest_population_per_cell() -> None:
    rows = [
        _row(arm_role="placebo", arm_agent=None, responders=2, n_analyzed=40, assessor="central"),
        _row(arm_role="placebo", arm_agent=None, responders=3, n_analyzed=60),
    ]
    controls = control_rates(rows, "F-VASI")
    assert controls[("NCT1", 75, 24)] == Observed(3, 60)


def test_effect_samples_measure_active_against_its_own_control() -> None:
    rows = [
        _row(source_id="NCT2", responders=30, n_analyzed=100),
        _row(source_id="NCT2", arm_role="placebo", arm_agent=None, responders=10, n_analyzed=100),
    ]
    controls = control_rates(rows, "F-VASI")
    [sample] = effect_samples(
        rows,
        controls,
        instrument="F-VASI",
        route="oral",
        threshold=75,
        exclude_trial="NCT9",
        agent_routes=ROUTES,
    )
    expected = logit(jeffreys_rate(30, 100)) - logit(jeffreys_rate(10, 100))
    assert sample.delta == pytest.approx(expected)
    assert (sample.trial, sample.week) == ("NCT2", 24)


def test_effect_samples_exclude_the_held_out_trial() -> None:
    rows = [
        _row(source_id="NCT2"),
        _row(source_id="NCT2", arm_role="placebo", arm_agent=None, responders=5),
    ]
    controls = control_rates(rows, "F-VASI")
    assert (
        effect_samples(
            rows,
            controls,
            instrument="F-VASI",
            route="oral",
            threshold=75,
            exclude_trial="NCT2",
            agent_routes=ROUTES,
        )
        == []
    )


def test_effect_samples_filter_by_route_unless_pooling_across_routes() -> None:
    rows = [
        _row(source_id="NCT2", arm_agent="ruxolitinib", route="topical"),
        _row(
            source_id="NCT2",
            arm_role="placebo",
            arm_agent=None,
            route="topical",
            responders=5,
        ),
    ]
    controls = control_rates(rows, "F-VASI")
    kwargs: dict[str, Any] = {
        "instrument": "F-VASI",
        "threshold": 75,
        "exclude_trial": "NCT9",
        "agent_routes": ROUTES,
    }
    assert effect_samples(rows, controls, route="oral", **kwargs) == []
    assert len(effect_samples(rows, controls, route="topical", **kwargs)) == 1
    assert len(effect_samples(rows, controls, route=None, **kwargs)) == 1


def test_active_rates_need_the_same_week() -> None:
    rows = [_row(source_id="NCT2", week=24), _row(source_id="NCT3", week=52)]
    kwargs: dict[str, Any] = {
        "instrument": "F-VASI",
        "route": "oral",
        "threshold": 75,
        "exclude_trial": "NCT9",
        "agent_routes": ROUTES,
    }
    assert len(active_rates(rows, week=24, **kwargs)) == 1
    assert len(active_rates(rows, week=12, **kwargs)) == 0


def test_baselines_abstain_rather_than_guess_from_one_arm() -> None:
    control = Observed(10, 100)
    one = [EffectSample("NCT2", 24, 0.8)]
    assert predict_placebo_anchored(control, one, 100, _rng()) is None
    assert predict_pooled_rate([logit(0.2)], 100, _rng()) is None
    assert predict_placebo_anchored_time(control, one, 24, 100, _rng()) is None


def test_placebo_anchored_centres_on_the_control_plus_the_pooled_effect() -> None:
    control = Observed(10, 100)
    effects = [EffectSample("NCT2", 24, 1.0), EffectSample("NCT3", 24, 1.0)]
    prediction = predict_placebo_anchored(control, effects, 400, _rng())
    assert prediction is not None
    expected = float(expit(np.array([logit(control.rate) + 1.0]))[0])
    assert prediction.median == pytest.approx(expected, abs=0.02)
    assert prediction.pooled_from == 2
    assert prediction.lo80 < prediction.median < prediction.hi80


def test_a_wider_spread_of_effects_widens_the_interval() -> None:
    control = Observed(10, 100)
    tight = [EffectSample("A", 24, 1.0), EffectSample("B", 24, 1.05)]
    loose = [EffectSample("A", 24, 0.0), EffectSample("B", 24, 2.0)]
    narrow = predict_placebo_anchored(control, tight, 400, _rng())
    wide = predict_placebo_anchored(control, loose, 400, _rng())
    assert narrow is not None and wide is not None
    assert (wide.hi80 - wide.lo80) > (narrow.hi80 - narrow.lo80)


def test_time_variant_needs_effects_from_more_than_one_week() -> None:
    same_week = [EffectSample(t, 24, 1.0) for t in ("A", "B", "C")]
    assert not fits_a_time_trend(same_week)
    assert predict_placebo_anchored_time(Observed(10, 100), same_week, 52, 100, _rng()) is None

    spread = [EffectSample("A", 12, 0.5), EffectSample("B", 24, 1.0), EffectSample("C", 48, 1.5)]
    assert fits_a_time_trend(spread)
    assert predict_placebo_anchored_time(Observed(10, 100), spread, 52, 100, _rng()) is not None


def test_time_variant_follows_the_slope_it_was_given() -> None:
    """Effects rising with log(week) should predict more at week 52 than at week 12."""
    control = Observed(10, 100)
    rising = [
        EffectSample("A", 12, 0.0),
        EffectSample("B", 24, 0.7),
        EffectSample("C", 48, 1.4),
    ]
    early = predict_placebo_anchored_time(control, rising, 12, 400, _rng())
    late = predict_placebo_anchored_time(control, rising, 52, 400, _rng())
    assert early is not None and late is not None
    assert late.median > early.median


def test_pooled_rate_centres_on_the_pooled_rates() -> None:
    rates = [logit(0.3), logit(0.32), logit(0.28)]
    prediction = predict_pooled_rate(rates, 500, _rng())
    assert prediction is not None
    assert prediction.median == pytest.approx(0.30, abs=0.03)
    assert prediction.pool_level == "route"


def test_prediction_records_the_pool_it_used() -> None:
    effects = [EffectSample("A", 24, 1.0), EffectSample("B", 24, 1.2)]
    prediction = predict_placebo_anchored(Observed(10, 100), effects, 100, _rng(), "any_route")
    assert prediction is not None
    assert prediction.pool_level == "any_route"


def test_metrics_match_the_back_tests_definitions() -> None:
    prediction = predict_pooled_rate([logit(0.3), logit(0.31)], 400, _rng())
    assert prediction is not None
    scored = [(prediction, prediction.median), (prediction, prediction.hi95 + 0.2)]
    result = metrics(scored)
    assert result["points"] == 2
    assert result["coverage80"] == 0.5
    assert result["coverage95"] == 0.5
    assert result["mean_abs_error_pp"] == pytest.approx(
        100 * (prediction.hi95 + 0.2 - prediction.median) / 2, abs=0.01
    )


def test_metrics_of_nothing_is_not_a_crash() -> None:
    assert metrics([]) == {"points": 0}


def test_paired_difference_favours_whichever_method_is_closer() -> None:
    # (trial, baseline error, model error): the model is 5 pp closer everywhere.
    errors = [(f"NCT{i}", 0.10, 0.05) for i in range(6)]
    result = paired_error_difference(errors, _rng())
    assert result["favours"] == "model"
    assert result["mean_difference_pp"] == pytest.approx(5.0)
    assert result["separates_from_zero"]

    flipped = [(f"NCT{i}", 0.05, 0.10) for i in range(6)]
    assert paired_error_difference(flipped, _rng())["favours"] == "baseline"


def test_paired_difference_is_uncertain_when_trials_disagree() -> None:
    """One trial favouring each way must not read as a settled difference."""
    errors = [("NCT1", 0.20, 0.05), ("NCT2", 0.05, 0.20)]
    result = paired_error_difference(errors, _rng())
    assert result["trials"] == 2
    assert not result["separates_from_zero"]


def test_paired_difference_clusters_by_trial() -> None:
    """Points from one trial are not independent; the interval must reflect that."""
    one_trial = [("NCT1", 0.10, 0.05)] * 40
    many_trials = [(f"NCT{i}", 0.10, 0.05) for i in range(40)]
    spread_one = paired_error_difference(one_trial, _rng())["ci95_pp"]
    spread_many = paired_error_difference(many_trials, _rng())["ci95_pp"]
    assert spread_one[0] == spread_one[1] == pytest.approx(5.0)  # nothing to resample
    assert spread_many[0] == pytest.approx(5.0)


def test_paired_difference_of_nothing_is_not_a_crash() -> None:
    assert paired_error_difference([], _rng()) == {"points": 0}


def test_draws_are_reproducible_for_a_fixed_seed() -> None:
    effects = [EffectSample("A", 24, 1.0), EffectSample("B", 24, 1.3)]
    first = predict_placebo_anchored(Observed(10, 100), effects, 200, _rng())
    second = predict_placebo_anchored(Observed(10, 100), effects, 200, _rng())
    assert first == second


def test_predictions_stay_inside_zero_and_one() -> None:
    """Even an extreme pooled effect cannot predict a rate outside the unit interval."""
    effects = [EffectSample("A", 24, 40.0), EffectSample("B", 24, 60.0)]
    prediction = predict_placebo_anchored(Observed(1, 100), effects, 50, _rng())
    assert prediction is not None
    assert 0.0 <= prediction.lo95 <= prediction.hi95 <= 1.0
    assert not math.isnan(prediction.median)
