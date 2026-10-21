"""Evaluate scenario model v0.3 as pre-registered (docs/model-v0.3-preregistration.md).

    python scripts/model/evaluate_v03.py e1              # topline hold-out (decides adoption)
    python scripts/model/evaluate_v03.py e2 F-VASI       # back-tests, one instrument
    python scripts/model/evaluate_v03.py decide          # apply the adoption rule
    python scripts/model/evaluate_v03.py production      # if adopted: fit with toplines, seal E3
    python scripts/model/evaluate_v03.py v04-seal        # v0.4 challenger: seal the P targets
    python scripts/model/evaluate_v03.py v04-lopo        # v0.4: leave one oral programme out
    python scripts/model/evaluate_v03.py v05-seal        # v0.5 challenger (per-route baselines)
    python scripts/model/evaluate_v03.py v05-lopo

v0.4 is pre-registered in docs/model-v0.4-preregistration.md.

Results go to forecasts/v0.3/.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo import __version__
from vitiligo.cli import model_inputs_v03
from vitiligo.discovery.forecasts import (
    ForecastTarget,
    _log_score,
    committed_code,
    forecast_target,
    write_forecast,
)
from vitiligo.discovery.ledger import verify_seal
from vitiligo.models.jak_mbma import (
    PRIORS,
    FitSettings,
    Scenario,
    backtest_leave_one_trial_out,
    backtest_time_extrapolation,
    build_dataset,
    converged,
    fit,
    predict_draws,
)
from vitiligo.reports.paper_results import load_toplines

OUT = Path("forecasts/v0.3")
V03 = FitSettings(version="v0.3", target_accept=0.995)  # amendment 1 of the pre-registration
TOPLINES = Path("curation/topline-results.json")
V02_FORECASTS = Path("forecasts/2026-10-14-auto")
# Topline trial -> (v0.2 sealed-record trial id, label fragment) for pairs with sealed draws.
V02_MATCH = {
    "NCT06072183": ("NCT06072183", "Arm 1"),
    "NCT06118411-S1": ("NCT06118411", "Study 1"),
    "NCT06118411-S2": ("NCT06118411", "Study 2"),
}


def _pairs() -> list[dict[str, Any]]:
    """Active/placebo topline pairs with observed counts."""
    rows = load_toplines(TOPLINES)
    pairs = []
    for a in rows:
        if a.arm_role != "active":
            continue
        c = next(
            r
            for r in rows
            if r.arm_role == "placebo"
            and (r.source_id, r.instrument, r.threshold, r.week)
            == (a.source_id, a.instrument, a.threshold, a.week)
        )
        assert a.responders is not None and c.responders is not None
        assert a.n_analyzed and c.n_analyzed and a.arm_agent and a.dose_value
        pairs.append(
            {
                "trial": a.source_id,
                "agent": a.arm_agent,
                "dose": a.dose_value,
                "instrument": a.instrument,
                "threshold": a.threshold,
                "week": a.week,
                "observed": {
                    "responders_active": a.responders,
                    "n_active": a.n_analyzed,
                    "responders_control": c.responders,
                    "n_control": c.n_analyzed,
                },
            }
        )
    return pairs


def _v02_draws(pair: dict[str, Any]) -> tuple[np.ndarray, np.ndarray] | None:
    match = V02_MATCH.get(pair["trial"])
    if match is None:
        return None
    trial, fragment = match
    endpoint = f"{pair['instrument']}{pair['threshold']} at week {pair['week']}"
    for path in sorted(V02_FORECASTS.glob("*.json")):
        record = json.loads(path.read_text())
        if "sha256" not in record or not verify_seal(record):
            continue
        label = record["label"]
        if label.startswith(trial) and fragment in label and label.endswith(endpoint):
            draws_path = path.parent / record["draws_file"]
            assert hashlib.sha256(draws_path.read_bytes()).hexdigest() == record["draws_sha256"]
            with np.load(draws_path) as d:
                return np.asarray(d["p_active"]), np.asarray(d["p_control"])
    raise FileNotFoundError(f"no sealed v0.2 forecast for {pair}")


def _interval(x: np.ndarray) -> dict[str, float]:
    q = np.quantile(x, [0.1, 0.5, 0.9])
    return {"lo80": float(q[0]), "median": float(q[1]), "hi80": float(q[2])}


def e1() -> None:
    rows, routes, phase3 = model_inputs_v03(with_toplines=False)
    posteriors = {}
    for instrument in ("F-VASI", "T-VASI"):
        data = build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3)
        posteriors[instrument] = fit(data, V03)
        print(instrument, posteriors[instrument].diagnostics, flush=True)
    results = []
    for pair in _pairs():
        posterior = posteriors[pair["instrument"]]
        scenario = Scenario(
            agent=pair["agent"], dose=pair["dose"], dose_unit="mg", frequency="QD",
            week=pair["week"], threshold=pair["threshold"], phase3=True, route=routes.get(pair["agent"]),
        )  # fmt: skip
        p_a, p_c = predict_draws(posterior, scenario)
        obs = pair["observed"]
        entry = {
            **pair,
            "v03": {
                "log_score": _log_score(obs, p_a, p_c),
                "active": _interval(p_a),
                "control": _interval(p_c),
            },
        }
        v02 = _v02_draws(pair)
        if v02 is not None:
            entry["v02"] = {
                "log_score": _log_score(obs, *v02),
                "active": _interval(v02[0]),
                "control": _interval(v02[1]),
            }
        results.append(entry)
        print(json.dumps({k: entry[k] for k in ("trial", "instrument", "threshold")}), flush=True)
    both = [r for r in results if "v02" in r]
    summary = {
        "pairs_with_both": len(both),
        "v03_log_score_sum": sum(r["v03"]["log_score"] for r in both),
        "v02_log_score_sum": sum(r["v02"]["log_score"] for r in both),
    }
    diagnostics = {k: p.diagnostics for k, p in posteriors.items()}
    converged_all = all(converged(p) for p in posteriors.values())
    _write("e1.json", {"summary": summary, "pairs": results, "diagnostics": diagnostics,
                       "converged": converged_all})  # fmt: skip
    print(summary, "converged:", converged_all)


def e2(instrument: str) -> None:
    rows, routes, phase3 = model_inputs_v03(with_toplines=False)
    loto = backtest_leave_one_trial_out(rows, instrument, V03, routes, trial_phase3=phase3)
    print("LOTO", loto["overall"], "converged:", loto["all_folds_converged"], flush=True)
    timing = backtest_time_extrapolation(rows, instrument, V03, routes, trial_phase3=phase3)
    print("time", timing["overall"], "converged:", timing["converged"], flush=True)
    _write(
        f"backtest-v03-{instrument}.json",
        {"leave_one_trial_out": loto, "time_extrapolation": timing},
    )


def decide() -> dict[str, Any]:
    e1_result = json.loads((OUT / "e1.json").read_text())
    loto = {
        i: json.loads((OUT / f"backtest-v03-{i}.json").read_text()) for i in ("F-VASI", "T-VASI")
    }
    summary = e1_result["summary"]
    criteria = {
        "a_e1_log_score_beats_v02": summary["v03_log_score_sum"] > summary["v02_log_score_sum"],
        "b_loto_coverage80_at_least_0.75": all(
            loto[i]["leave_one_trial_out"]["overall"]["coverage80"] >= 0.75 for i in loto
        ),
        "c_all_fits_converged": e1_result["converged"]
        and all(
            loto[i]["leave_one_trial_out"]["all_folds_converged"]
            and loto[i]["time_extrapolation"]["converged"]
            for i in loto
        ),
    }
    decision = {
        "decided_at": datetime.now(UTC).isoformat(),
        "criteria": criteria,
        "adopt_v03": all(criteria.values()),
        "e1": summary,
        "loto_overall": {i: loto[i]["leave_one_trial_out"]["overall"] for i in loto},
        "time_overall": {i: loto[i]["time_extrapolation"]["overall"] for i in loto},
    }
    _write("decision.json", decision)
    print(json.dumps(decision, indent=1))
    return decision


E3_PUBLIC_CHECK = (
    "2026-10-14: searched Pfizer and Incyte press releases, EADV 2026 reports (HCPLive, "
    "Dermatology Times) and PMC. Tranquillo week-24 numbers and Tranquillo 2 50 mg numbers are "
    "not public; Pfizer stated only that both doses improved over placebo at week 52 and that "
    "disease stabilization appeared from week 24. Nothing found for NCT06548360 or NCT06804811."
)


def _e3_targets() -> list[ForecastTarget]:
    targets = []
    # The 3 prospective pediatric ruxolitinib targets, exactly as v0.2 sealed them.
    for path in sorted(V02_FORECASTS.glob("*.json")):
        record = json.loads(path.read_text())
        t = record.get("target") or {}
        if t.get("trial") in ("NCT06548360", "NCT06804811"):
            fields = {k: v for k, v in t.items() if k != "key"}
            fields["assumptions"] = tuple(fields.get("assumptions") or ())
            targets.append(ForecastTarget(**fields, phase3=True))
    common: dict[str, Any] = {
        "agent": "ritlecitinib", "dose_unit": "mg", "frequency": "QD",
        "phototherapy": False, "phase3": True,
    }  # fmt: skip
    for instrument, k in (("F-VASI", 75), ("T-VASI", 50)):
        targets.append(ForecastTarget(
            trial="NCT05583526", group=None, arm_label="Ritlecitinib 50 mg", control_label="Placebo",
            dose_value=50.0, instrument=instrument, threshold=k, week=24,
            registry_measure="Tranquillo secondary endpoint at week 24", **common,
        ))  # fmt: skip
        targets.append(ForecastTarget(
            trial="NCT06072183", group=None, arm_label="Arm 2- Ritlecitinib 50mg", control_label="Arm 3- Placebo",
            dose_value=50.0, instrument=instrument, threshold=k, week=52,
            registry_measure="Tranquillo 2 co-primary endpoint at week 52 (50 mg arm, exploratory)", **common,
        ))  # fmt: skip
    return targets


def production() -> None:
    decision = json.loads((OUT / "decision.json").read_text())
    if not decision["adopt_v03"]:
        raise SystemExit("v0.3 was not adopted; no v0.3 forecasts are sealed.")
    _seal_targets(
        OUT / "forecasts", "jak_mbma ordered-probit v0.3", "docs/model-v0.3-preregistration.md"
    )


OUT_V04 = Path("forecasts/v0.4")
PROGRAMMES = {
    "ritlecitinib": {"NCT05583526", "NCT06072183"},
    "upadacitinib": {"NCT06118411-S1", "NCT06118411-S2"},
}


OUT_V05 = Path("forecasts/v0.5")
V05 = FitSettings(version="v0.5", target_accept=0.995)


def v04_seal() -> None:
    _seal_targets(
        OUT_V04 / "forecasts",
        "jak_mbma ordered-probit v0.4 (challenger)",
        "docs/model-v0.4-preregistration.md",
    )


def v05_seal() -> None:
    _seal_targets(
        OUT_V05 / "forecasts",
        "jak_mbma ordered-probit v0.5 (challenger)",
        "docs/model-v0.5-preregistration.md",
        settings=V05,
    )


def v04_lopo(settings: FitSettings = V03, out: Path = OUT_V04, label: str = "v04") -> None:
    rows_all, routes, phase3 = model_inputs_v03(with_toplines=True)
    results = []
    for programme, trials in PROGRAMMES.items():
        rows = [r for r in rows_all if r.source_id not in trials]
        posteriors = {}
        for instrument in ("F-VASI", "T-VASI"):
            data = build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3)
            posteriors[instrument] = fit(data, settings)
            print(programme, instrument, posteriors[instrument].diagnostics, flush=True)
        for pair in _pairs():
            if pair["trial"] not in trials:
                continue
            scenario = Scenario(
                agent=pair["agent"], dose=pair["dose"], dose_unit="mg", frequency="QD",
                week=pair["week"], threshold=pair["threshold"], phase3=True,
                route=routes.get(pair["agent"]),
            )  # fmt: skip
            p_a, p_c = predict_draws(posteriors[pair["instrument"]], scenario)
            entry = {
                **pair,
                "held_out_programme": programme,
                label: {"log_score": _log_score(pair["observed"], p_a, p_c),
                        "active": _interval(p_a), "control": _interval(p_c)},
                "converged": all(converged(p) for p in posteriors.values()),
            }  # fmt: skip
            v02 = _v02_draws(pair)
            if v02 is not None:
                entry["v02"] = {"log_score": _log_score(pair["observed"], *v02),
                                "active": _interval(v02[0]), "control": _interval(v02[1])}  # fmt: skip
            results.append(entry)
    both = [r for r in results if "v02" in r]
    summary = {
        "pairs_with_both": len(both),
        f"{label}_log_score_sum": sum(r[label]["log_score"] for r in both),
        "v02_log_score_sum": sum(r["v02"]["log_score"] for r in both),
        "note": "Report only (pre-registration L); not first-look.",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "lopo.json").write_text(
        json.dumps({"summary": summary, "pairs": results}, indent=1, default=str) + "\n"
    )
    print(summary)


def _seal_targets(
    directory: Path, model_label: str, prereg: str, settings: FitSettings = V03
) -> None:
    code = committed_code()
    rows, routes, phase3 = model_inputs_v03(with_toplines=True)
    posteriors = {}
    for instrument in ("F-VASI", "T-VASI"):
        data = build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3)
        posterior = fit(data, settings)
        print(instrument, posterior.diagnostics, flush=True)
        if not converged(posterior):
            raise SystemExit(f"{instrument} production fit did not converge; nothing sealed")
        observations = [asdict(o) for o in data.observations]
        posteriors[instrument] = (
            posterior,
            data,
            hashlib.sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest(),
        )
    for target in _e3_targets():
        posterior, data, data_sha = posteriors[target.instrument]
        summary, p_active, p_control = forecast_target(posterior, target, routes=routes)
        write_forecast(
            target, summary, p_active, p_control, directory,
            context={
                "engine_version": __version__,
                "model": model_label,
                "priors": PRIORS | {"sigma_gamma (trial-by-treatment SD)": "HalfNormal(0.5)",
                                    "kappa_route (phase 3 shift of the drug effect)": "Normal(0, 0.5)"}
                | ({"mu0_route (mean baseline per route, replaces mu0)": "Normal(-1.5, 1.0)"}
                   if settings.version == "v0.5" else {}),
                "fit_settings": asdict(settings),
                "dataset": data.summary(),
                "data_sha256": data_sha,
                "diagnostics": posterior.diagnostics,
                "preregistration": prereg,
                "public_results_check": E3_PUBLIC_CHECK,
                "code": code,
                "disclaimer": "Research forecast; not medical advice. No results for this target were consulted.",
            },
        )  # fmt: skip
        a, c = summary["p_active"], summary["p_control"]
        print(f"sealed {target.key}: active {100 * a['median']:.1f}% "
              f"(80%: {100 * a['lo80']:.1f}-{100 * a['hi80']:.1f}) vs control {100 * c['median']:.1f}%")  # fmt: skip


def _write(name: str, payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=1, default=str) + "\n")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "e1":
        e1()
    elif command == "e2":
        e2(sys.argv[2])
    elif command == "decide":
        decide()
    elif command == "production":
        production()
    elif command == "v04-seal":
        v04_seal()
    elif command == "v04-lopo":
        v04_lopo()
    elif command == "v05-seal":
        v05_seal()
    elif command == "v05-lopo":
        v04_lopo(V05, OUT_V05, "v05")
    else:
        raise SystemExit(__doc__)
