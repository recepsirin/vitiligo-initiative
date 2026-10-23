"""Compare the scenario model with simple baselines on the same held-out points.

Roadmap item 0.1. The scenario model's leave-one-trial-out back-test is read
from its stored output, and each baseline is scored on exactly the points that
back-test scored, so the two differ only in the method.

    python scripts/model/baseline_compare.py \
        --backtest exports/model/backtest-v02-F-VASI.json --instrument F-VASI \
        --out exports/model/baseline-comparison-F-VASI.json

**This comparison is post hoc.** These trials' results were public and shaped
the model's development (v0.1 fixed v0's back-test failures), and the
baselines were written by someone who had read the model's results. It can
show that the model is not earning its complexity; it cannot establish that it
is. The prospective version is to seal a baseline forecast beside every model
forecast and score both as results post.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo.models.baseline import (
    MIN_POOL,
    Prediction,
    active_rates,
    control_rates,
    effect_samples,
    fits_a_time_trend,
    metrics,
    paired_error_difference,
    predict_placebo_anchored,
    predict_placebo_anchored_time,
    predict_pooled_rate,
)
from vitiligo.reports import build_jak_atlas
from vitiligo.reports.jak_arms import ArmEndpointRow, harmonize_arms
from vitiligo.storage import init_db

METHODS = ("pooled_rate", "placebo_anchored", "placebo_anchored_time")


def model_points(backtest: dict[str, Any]) -> list[dict[str, Any]]:
    """Every scored point of the stored leave-one-trial-out back-test."""
    folds = backtest["leave_one_trial_out"]["folds"]
    return [{**point, "trial": trial} for trial, fold in folds.items() for point in fold["points"]]


def _route_of_trial(
    rows: list[ArmEndpointRow], trial: str, agent_routes: dict[str, str]
) -> str | None:
    """The route of a trial's active arms (they share one in this atlas)."""
    routes = {
        agent_routes.get(r.arm_agent or "", r.route)
        for r in rows
        if r.source_id == trial and r.arm_role == "active"
    }
    routes.discard(None)
    return routes.pop() if len(routes) == 1 else None


def baseline_predictions(
    point: dict[str, Any],
    rows: list[ArmEndpointRow],
    controls: dict[tuple[str, int, int], Any],
    agent_routes: dict[str, str],
    rng: np.random.Generator,
) -> dict[str, Prediction | None]:
    """Each baseline's prediction for one held-out point (``None`` where it abstains).

    Pooling prefers arms of the same route. Topical trials report a control arm
    only at week 24, so a route-specific pool is often too thin; the fallback
    pools every JAK trial at that threshold instead, and the prediction records
    which pool it used (``pool_level``).
    """
    trial, week, threshold, n = point["trial"], point["week"], point["threshold"], point["n"]
    instrument = point["instrument"]
    route = _route_of_trial(rows, trial, agent_routes)

    def pools(select: Any) -> tuple[Any, str]:
        """Route-specific pool when it is big enough, else the all-routes pool."""
        if route is not None:
            narrow = select(route)
            if len(narrow) >= MIN_POOL:
                return narrow, "route"
        return select(None), "any_route"

    rates, rate_level = pools(
        lambda r: active_rates(
            rows,
            instrument=instrument,
            route=r,
            threshold=threshold,
            week=week,
            exclude_trial=trial,
            agent_routes=agent_routes,
        )
    )
    out: dict[str, Prediction | None] = {
        "pooled_rate": predict_pooled_rate(rates, n, rng, rate_level)
    }

    control = controls.get((trial, threshold, week))
    if control is None:  # e.g. TRuE-V week 52, where the vehicle arm switched to active
        out["placebo_anchored"] = None
        out["placebo_anchored_time"] = None
        return out

    def effects_for(r: str | None) -> list[Any]:
        return effect_samples(
            rows,
            controls,
            instrument=instrument,
            route=r,
            threshold=threshold,
            exclude_trial=trial,
            agent_routes=agent_routes,
        )

    effects, level = pools(effects_for)
    out["placebo_anchored"] = predict_placebo_anchored(control, effects, n, rng, level)

    # The time variant needs a slope, so it may need the wider pool even when
    # the narrow one was large enough for a flat effect.
    time_effects, time_level = effects, level
    if route is not None and not fits_a_time_trend(time_effects):
        time_effects, time_level = effects_for(None), "any_route"
    out["placebo_anchored_time"] = predict_placebo_anchored_time(
        control, time_effects, week, n, rng, time_level
    )
    return out


def compare(instrument: str, backtest_path: Path, seed: int) -> dict[str, Any]:
    init_db()
    atlas = build_jak_atlas()
    rows = harmonize_arms(atlas)
    agent_routes = {s.name: s.routes[0] for s in atlas.agents if len(s.routes) == 1}
    controls = control_rates(rows, instrument)
    backtest = json.loads(backtest_path.read_text())
    rng = np.random.default_rng(seed)

    scored: list[dict[str, Any]] = []
    for point in model_points(backtest):
        preds = baseline_predictions(
            {**point, "instrument": instrument}, rows, controls, agent_routes, rng
        )
        scored.append({"point": point, "baselines": preds})

    results: dict[str, Any] = {
        "instrument": instrument,
        "backtest_file": str(backtest_path),
        "model_overall_reported": backtest["leave_one_trial_out"]["overall"],
        "seed": seed,
        "post_hoc": (
            "These results were public before this comparison and shaped the model's "
            "development; the baselines were written after reading the model's back-test. "
            "A clean test seals a baseline beside a model forecast before results exist."
        ),
    }

    # Each method on every point it can predict.
    per_method: dict[str, Any] = {}
    for method in METHODS:
        pairs = [
            (s["baselines"][method], s["point"]["observed"])
            for s in scored
            if s["baselines"][method] is not None
        ]
        per_method[method] = metrics(pairs)
    model_pairs_all = [(_as_prediction(s["point"]), s["point"]["observed"]) for s in scored]
    per_method["scenario_model"] = metrics(model_pairs_all)
    results["each_method_on_its_own_points"] = per_method

    # The headline comparison: points both anchor-free and anchored baselines
    # could predict, with the model scored on exactly those points.
    headline_methods = ("pooled_rate", "placebo_anchored")
    common = [s for s in scored if all(s["baselines"][m] is not None for m in headline_methods)]
    head: dict[str, Any] = {
        "points": len(common),
        "of_model_points": len(scored),
        "methods": list(headline_methods),
        "scenario_model": metrics(
            [(_as_prediction(s["point"]), s["point"]["observed"]) for s in common]
        ),
    }
    for method in headline_methods:
        head[method] = metrics([(s["baselines"][method], s["point"]["observed"]) for s in common])
    for method in headline_methods:
        head[f"{method}_vs_model"] = paired_error_difference(
            [
                (
                    s["point"]["trial"],
                    abs(s["baselines"][method].median - s["point"]["observed"]),
                    abs(s["point"]["predicted"]["median"] - s["point"]["observed"]),
                )
                for s in common
            ],
            rng,
        )
    results["common_points"] = head

    # The time variant separately: it can rarely be estimated at all.
    with_time = [s for s in scored if s["baselines"]["placebo_anchored_time"] is not None]
    results["time_variant"] = {
        "points": len(with_time),
        "why_so_few": (
            "A slope in log(week) needs control-anchored arms at more than one week. "
            "Outside the two oral trials, every control arm in this corpus reports only "
            "week 24, so holding out an oral trial leaves nothing to fit a time trend on."
        ),
        "placebo_anchored_time": metrics(
            [(s["baselines"]["placebo_anchored_time"], s["point"]["observed"]) for s in with_time]
        ),
        "scenario_model_same_points": metrics(
            [(_as_prediction(s["point"]), s["point"]["observed"]) for s in with_time]
        ),
        "placebo_anchored_same_points": metrics(
            [
                (s["baselines"]["placebo_anchored"], s["point"]["observed"])
                for s in with_time
                if s["baselines"]["placebo_anchored"] is not None
            ]
        ),
    }

    # How often each baseline needed the all-routes fallback.
    results["pool_levels"] = {
        method: dict(
            Counter(
                s["baselines"][method].pool_level
                for s in scored
                if s["baselines"][method] is not None
            )
        )
        for method in METHODS
    }

    results["points"] = [
        {
            "trial": s["point"]["trial"],
            "arm": s["point"]["arm_label"],
            "week": s["point"]["week"],
            "threshold": s["point"]["threshold"],
            "n": s["point"]["n"],
            "observed": s["point"]["observed"],
            "scenario_model_median": s["point"]["predicted"]["median"],
            **{
                m: (None if s["baselines"][m] is None else s["baselines"][m].median)
                for m in METHODS
            },
        }
        for s in scored
    ]
    return results


def _as_prediction(point: dict[str, Any]) -> Prediction:
    """The stored model prediction, in the baseline's shape, for one metrics function."""
    p = point["predicted"]
    return Prediction(
        method="scenario_model",
        mean=p["mean"],
        median=p["median"],
        lo80=p["lo80"],
        hi80=p["hi80"],
        lo95=p["lo95"],
        hi95=p["hi95"],
        pooled_from=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument", default="F-VASI", choices=["F-VASI", "T-VASI"])
    parser.add_argument("--backtest", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--seed", type=int, default=20261023)
    args = parser.parse_args()

    results = compare(args.instrument, args.backtest, args.seed)
    head = results["common_points"]
    print(
        f"{args.instrument}: {head['points']} of {head['of_model_points']} held-out points "
        f"where every headline method predicts\n"
    )
    print(f"{'method':<26} {'points':>6} {'cov80':>6} {'cov95':>6} {'MAE pp':>7}")
    for name in ("scenario_model", *head["methods"]):
        m = head[name]
        print(
            f"{name:<26} {m['points']:>6} {m['coverage80']:>6} "
            f"{m['coverage95']:>6} {m['mean_abs_error_pp']:>7}"
        )
    print("\nBaseline error minus model error, bootstrapped over trials (+ favours the model):")
    for name in head["methods"]:
        d = head[f"{name}_vs_model"]
        print(
            f"  {name:<26} {d['mean_difference_pp']:>6} pp  95% CI {d['ci95_pp']}  "
            f"{'separates from 0' if d['separates_from_zero'] else 'overlaps 0'}"
        )
    time_v = results["time_variant"]
    print(f"\nTime variant, on the {time_v['points']} points where a slope is estimable:")
    for name in (
        "placebo_anchored_time",
        "placebo_anchored_same_points",
        "scenario_model_same_points",
    ):
        print(f"  {name:<30} {time_v[name]}")
    print(f"  why so few: {time_v['why_so_few']}")
    print("\nEach method on every point it could predict:")
    for name, m in results["each_method_on_its_own_points"].items():
        print(f"  {name:<26} {m}")
    print(f"\nPool level used: {results['pool_levels']}")
    print(f"\n{results['post_hoc']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2, default=str) + "\n")
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
