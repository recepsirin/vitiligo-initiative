"""Out-of-sample check: povorcitinib phase 3 (STOP-V1, STOP-V2) against v0.2, v0.4 and v0.5.

    python scripts/model/povorcitinib_check.py          # F-VASI75 check -> check.json
    python scripts/model/povorcitinib_check.py seal     # seal T-VASI50 forecasts

The check is not a sealed forecast. Incyte announced the toplines on 2026-04-28, our sealing
checks missed them, and these predictions were computed on 2026-10-21, after
the results were known. What keeps the check honest: every model is refitted
on exactly the data it was sealed with (the data hashes are compared with the
sealed records below), with its pre-registered settings, and nothing was
changed after seeing the results.

No model has povorcitinib F-VASI data (the phase 2 registry record posts only
T-VASI), so on F-VASI75 every model predicts povorcitinib as an unseen oral
JAK inhibitor; the dose does not enter. Both trials randomized 1:1 (EU CTIS
2023-505782-86-00 and 2023-506011-18-00), but exact arm sizes are not public,
so log scores use a 1:1 split of the registered enrolment and are approximate;
2:1 and 3:1 show how little the split matters. The position of the observed
rates in each predictive distribution needs no arm sizes.

T-VASI50 at week 52 has no public numbers yet (Incyte reported it only as
statistically significant), so ``seal`` seals it under all three models, with
that disclosure in the record. v0.4 and v0.5 have povorcitinib's phase 2
T-VASI data; v0.2 has it too.

Writes forecasts/povorcitinib-phase3/.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo import __version__
from vitiligo.cli import _model_inputs, model_inputs_v03
from vitiligo.discovery.forecasts import (
    ForecastTarget,
    _log_score,
    committed_code,
    forecast_target,
    write_forecast,
)
from vitiligo.models.jak_mbma import (
    FitSettings,
    Scenario,
    build_dataset,
    converged,
    fit,
    predict_draws,
)

OUT = Path("forecasts/povorcitinib-phase3")
SOURCE = (
    "Incyte Q1 2026 results, 2026-04-28, SEC Form 8-K Exhibit 99.1: "
    "https://www.sec.gov/Archives/edgar/data/0000879169/000087916926000023/incy-q12026xexx991.htm"
)
# Observed F-VASI75 at week 52 (povorcitinib 30 mg QD vs placebo) and registered enrolment.
TRIALS = {
    "NCT06113445 (STOP-V1)": {"active": 0.189, "control": 0.068, "enrolled": 467},
    "NCT06113471 (STOP-V2)": {"active": 0.189, "control": 0.031, "enrolled": 450},
}
RATIOS = (1, 2, 3)
# data_sha256 of the sealed records each refit must reproduce.
SEALED_DATA = {
    "v0.2": {"F-VASI": "9f48bcbb3f86", "T-VASI": "6b220531dc91"},
    "v0.4": {"F-VASI": "48a62f5f4f62", "T-VASI": "249569d81638"},
    "v0.5": {"F-VASI": "48a62f5f4f62", "T-VASI": "249569d81638"},
}
MODELS = {
    "v0.2": FitSettings(),
    "v0.4": FitSettings(version="v0.3", target_accept=0.995),
    "v0.5": FitSettings(version="v0.5", target_accept=0.995),
}


def _split(enrolled: int, ratio: int, active: float, control: float) -> dict[str, int]:
    """A ratio:1 split of the enrolment with the nearest whole responder counts.

    Approximate: the analysis set and imputation method are not public (the
    printed percentages need not be whole counts of the enrolled).
    """
    n_a = round(enrolled * ratio / (ratio + 1))
    n_c = enrolled - n_a
    return {
        "responders_active": round(active * n_a),
        "n_active": n_a,
        "responders_control": round(control * n_c),
        "n_control": n_c,
    }


def _interval(x: np.ndarray) -> dict[str, float]:
    q = np.quantile(x, [0.05, 0.1, 0.5, 0.9, 0.95])
    return dict(zip(("lo90", "lo80", "median", "hi80", "hi90"), map(float, q), strict=True))


def _inputs(model: str) -> tuple[list[Any], dict[str, str], dict[str, bool] | None]:
    if model == "v0.2":
        rows, routes = _model_inputs()
        return rows, routes, None
    return model_inputs_v03(with_toplines=True)


def _fit(model: str, instrument: str) -> dict[str, Any]:
    """Fit one model as sealed; refit once at target_accept 0.995 if it does not converge."""
    settings = MODELS[model]
    rows, routes, phase3 = _inputs(model)
    data = (
        build_dataset(rows, instrument, agent_routes=routes)
        if phase3 is None
        else build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3)
    )
    observations = [asdict(o) for o in data.observations]
    data_sha = hashlib.sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest()
    posterior = fit(data, settings)
    print(model, instrument, posterior.diagnostics, flush=True)
    first_try = None
    if not converged(posterior) and settings.target_accept < 0.995:
        # The committed code does not reproduce the sealed v0.2 fit exactly (it was
        # sealed before the code was committed). As for v0.3, raise target_accept
        # once and report both runs.
        first_try = posterior.diagnostics
        settings = replace(settings, target_accept=0.995)
        posterior = fit(data, settings)
        print(model, instrument, "refit at 0.995:", posterior.diagnostics, flush=True)
    return {
        "data": data,
        "data_sha256": data_sha,
        "posterior": posterior,
        "settings": settings,
        "first_try": first_try,
        "routes": routes,
    }


def main() -> None:
    results: dict[str, Any] = {}
    for model in MODELS:
        results[model] = {}
        for instrument, threshold in (("F-VASI", 75), ("T-VASI", 50)):
            fitted = _fit(model, instrument)
            posterior = fitted["posterior"]
            scenario = Scenario(
                agent="povorcitinib", dose=30, dose_unit="mg", frequency="QD", week=52,
                threshold=threshold, phase3=True, route="oral",
            )  # fmt: skip
            p_a, p_c = predict_draws(posterior, scenario)
            entry: dict[str, Any] = {
                "data_sha256": fitted["data_sha256"],
                "matches_sealed_data": fitted["data_sha256"].startswith(
                    SEALED_DATA[model][instrument]
                ),
                "povorcitinib_in_data": "povorcitinib" in fitted["data"].agents,
                "diagnostics": posterior.diagnostics,
                "first_try_diagnostics": fitted["first_try"],
                "converged": converged(posterior),
                "active": _interval(p_a),
                "control": _interval(p_c),
                "difference": _interval(p_a - p_c),
            }
            if instrument == "F-VASI":
                entry["trials"] = {}
                for trial, obs in TRIALS.items():
                    a, c = obs["active"], obs["control"]
                    entry["trials"][trial] = {
                        # Share of predictive draws below the observed rate (0.5 = dead centre).
                        "quantile_of_observed": {
                            "active": float(np.mean(p_a < a)),
                            "control": float(np.mean(p_c < c)),
                            "difference": float(np.mean(p_a - p_c < a - c)),
                        },
                        "log_score_by_allocation": {
                            f"{r}:1": {
                                "counts": (counts := _split(obs["enrolled"], r, a, c)),
                                "log_score": _log_score(counts, p_a, p_c),
                            }
                            for r in RATIOS
                        },
                    }
            results[model][instrument] = entry
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "computed": "2026-10-21",
        "status": "post-hoc check, not a sealed forecast; results were public before it ran",
        "source": SOURCE,
        "scenario": "povorcitinib 30 mg QD, new phase 3 trial, week 52",
        "observed_f_vasi75": TRIALS,
        "t_vasi50": "reported only as statistically significant; no numbers to score",
        "models": results,
    }
    (OUT / "check.json").write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps(payload, indent=1))


PUBLIC_CHECK = (
    "Searched 2026-10-21: Incyte's first-quarter 2026 release (2026-04-28, SEC Form 8-K "
    "Exhibit 99.1), Healio (2026-05-05), Practical Dermatology (2026-04-28), EADV 2026 and "
    "the ClinicalTrials.gov and EU CTIS records. T-VASI50 at week 52 is reported only as "
    "'statistically significant and clinically meaningful' in both studies, with no numbers; "
    "so the direction is known and only the size is forecast. The F-VASI75 results "
    "(18.9% vs 6.8% and 3.1%) were read, but no model was refitted or changed: each fit "
    "reproduces the data hash of its earlier sealed records."
)
MODEL_LABELS = {
    "v0.2": ("jak_mbma ordered-probit v0.2", "docs/jak-scenario-model.md"),
    "v0.4": ("jak_mbma ordered-probit v0.4 (challenger)", "docs/model-v0.4-preregistration.md"),
    "v0.5": ("jak_mbma ordered-probit v0.5 (challenger)", "docs/model-v0.5-preregistration.md"),
}


def seal() -> None:
    code = committed_code()
    targets = [
        ForecastTarget(
            trial=trial,
            group=None,
            arm_label="Experimental: Povorcitinib Dose A",
            control_label="Placebo",
            agent="povorcitinib",
            dose_value=30.0,
            dose_unit="mg",
            frequency="QD",
            phototherapy=False,
            instrument="T-VASI",
            threshold=50,
            week=52,
            registry_measure="Proportion of Participants Achieving a >= 50% Improvement From "
            "Baseline in the Total Body Vitiligo Area Scoring Index (T-VASI50), key secondary",
            assumptions=("Dose A is 30 mg once daily (Incyte, 2026-04-28)",),
            phase3=True,
        )
        for trial in ("NCT06113445", "NCT06113471")
    ]
    # Fit every model before sealing anything, so a failed fit cannot leave a partial set.
    fits = {model: _fit(model, "T-VASI") for model in MODEL_LABELS}
    for model, fitted in fits.items():
        if not converged(fitted["posterior"]):
            raise SystemExit(f"{model} T-VASI fit did not converge; nothing sealed")
    for model, (label, prereg) in MODEL_LABELS.items():
        fitted = fits[model]
        posterior = fitted["posterior"]
        for target in targets:
            summary, p_active, p_control = forecast_target(
                posterior, target, routes=fitted["routes"]
            )
            write_forecast(
                target, summary, p_active, p_control, OUT / "sealed" / model,
                context={
                    "engine_version": __version__,
                    "model": label,
                    "fit_settings": asdict(fitted["settings"]),
                    "first_try_diagnostics": fitted["first_try"],
                    "dataset": fitted["data"].summary(),
                    "data_sha256": fitted["data_sha256"],
                    "diagnostics": posterior.diagnostics,
                    "preregistration": prereg,
                    "public_results_check": PUBLIC_CHECK,
                    "code": code,
                    "disclaimer": "Research forecast; not medical advice. The direction of "
                    "this result was public when it was sealed; its size was not.",
                },
            )  # fmt: skip
            a, c = summary["p_active"], summary["p_control"]
            print(f"sealed {model} {target.trial}: active {100 * a['median']:.1f}% "
                  f"(80%: {100 * a['lo80']:.1f}-{100 * a['hi80']:.1f}) "
                  f"vs control {100 * c['median']:.1f}%")  # fmt: skip


if __name__ == "__main__":
    seal() if sys.argv[1:] == ["seal"] else main()
