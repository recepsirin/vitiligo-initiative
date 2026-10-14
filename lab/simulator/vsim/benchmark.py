"""The benchmark (jak_mbma v0.2) on the pre-registered splits.

- Leave-one-trial-out on S (control arm kept): predictive draws for each held-out
  active arm-week, saved for scoring with ``score.py``.
- Fit on all of S per instrument: posteriors saved for the exam (``exam.py``).

Run from lab/simulator:  python -m vsim.benchmark
"""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict

import numpy as np

from vitiligo.models.jak_mbma import (
    FitSettings,
    Posterior,
    Scenario,
    build_dataset,
    converged,
    fit,
    predict_draws,
)
from vsim.data import (
    INSTRUMENTS,
    ROOT,
    SEARCH_MAX_WEEK,
    ArmWeek,
    controlled_trials,
    load_rows,
    search_set,
)

OUT = ROOT / "results" / "benchmark"


def _arm_index(posterior: Posterior, aw: ArmWeek) -> int | None:
    for i, arm in enumerate(posterior.data.arms):
        key = (
            arm.source_id,
            arm.active,
            arm.agent,
            arm.daily_dose,
            arm.dose_unit,
            arm.loading_dose,
            arm.phototherapy,
        )
        if key == aw.arm_key:
            return i
    return None


def benchmark_draws(
    posterior: Posterior, aw: ArmWeek, routes: dict[str, str], *, condition_arm: bool
) -> np.ndarray:
    """(draws, thresholds) response probabilities for one active arm-week."""
    assert aw.active and aw.agent is not None and aw.daily_dose is not None
    trial = aw.trial if aw.trial in posterior.data.trials else None
    arm = _arm_index(posterior, aw) if condition_arm else None
    columns = []
    for k in aw.thresholds:
        scenario = Scenario(
            agent=aw.agent,
            dose=aw.daily_dose,
            dose_unit=aw.dose_unit or "",
            frequency=None,  # daily dose already
            week=aw.week,
            threshold=k,
            loading_dose=aw.loading_dose is not None,
            phototherapy=aw.phototherapy,
            route=routes.get(aw.agent),
        )
        p_active, _ = predict_draws(posterior, scenario, trial=trial, arm=arm)
        columns.append(p_active)
    return np.stack(columns, axis=1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, routes = load_rows()
    settings = FitSettings()
    full_s = search_set(rows, routes)

    folds: dict[str, object] = {}
    targets: list[dict[str, object]] = []
    draws: dict[str, np.ndarray] = {}
    for instrument in INSTRUMENTS:
        in_s = [a for a in full_s if a.instrument == instrument]
        for trial in controlled_trials(in_s):
            data = build_dataset(
                rows, instrument, max_week=SEARCH_MAX_WEEK, drop=[(trial, True)],
                agent_routes=routes,
            )  # fmt: skip
            posterior = fit(data, settings)
            ok = converged(posterior)
            folds[f"{instrument}|{trial}"] = {"converged": ok, "diagnostics": posterior.diagnostics}
            print(f"{instrument} {trial}: converged={ok}", flush=True)
            for aw in in_s:
                if aw.trial == trial and aw.active:
                    key = f"{len(targets)}"
                    draws[key] = benchmark_draws(posterior, aw, routes, condition_arm=False)
                    targets.append({"key": key, **asdict(aw)})
    np.savez_compressed(OUT / "loto_s_draws.npz", **draws)
    (OUT / "loto_s_targets.json").write_text(json.dumps(targets, indent=1) + "\n")
    (OUT / "loto_s_folds.json").write_text(json.dumps(folds, indent=1) + "\n")

    for instrument in INSTRUMENTS:
        data = build_dataset(rows, instrument, max_week=SEARCH_MAX_WEEK, agent_routes=routes)
        posterior = fit(data, settings)
        print(f"{instrument} full S: converged={converged(posterior)}", flush=True)
        with open(OUT / f"posterior_s_{instrument}.pkl", "wb") as fh:
            pickle.dump(posterior, fh)


if __name__ == "__main__":
    main()
