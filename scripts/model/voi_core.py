"""Value-of-information core: retrospective gate and model discrimination.

Pre-registered in docs/voi-preregistration.md.

    python scripts/model/voi_core.py retro F-VASI    # one instrument: M0, predicted value, refits
    python scripts/model/voi_core.py retro T-VASI
    python scripts/model/voi_core.py gate            # G1 and G2 over the 11 items
    python scripts/model/voi_core.py discriminate    # sealed targets: which would separate models

Results go to forecasts/voi/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo.cli import PAPER_CURATION, TOPLINE_CURATION, model_inputs_v03
from vitiligo.discovery import voi
from vitiligo.discovery.forecasts import comparison_key, sealed_records
from vitiligo.models.jak_mbma import (
    FitSettings,
    Posterior,
    Scenario,
    build_dataset,
    daily_dose,
    fit,
)
from vitiligo.reports.jak_arms import ArmEndpointRow
from vitiligo.reports.paper_results import load_curation, load_toplines, new_rows, to_arm_rows

OUT = Path("forecasts/voi")
SETTINGS = FitSettings(version="v0.3", target_accept=0.995)
K_Q = 32  # new-trial replicates averaged into q
K_ITEM = 8  # new-trial replicates in an item's likelihood
TOPLINE_TRIALS = ("NCT05583526", "NCT06072183", "NCT06118411-S1", "NCT06118411-S2")
PAPER_ITEMS = {
    "F-VASI": [("NCT03099304", "ruxolitinib phase 2 1.5% BID, F-VASI rows")],
    "T-VASI": [
        ("NCT03099304", "ruxolitinib phase 2 1.5% BID, T-VASI rows"),
        ("NCT04927975", "upadacitinib phase 2, T-VASI50 week 24"),
    ],
}


def _threshold(instrument: str) -> int:
    return 75 if instrument == "F-VASI" else 50


def _questions(instrument: str) -> dict[str, Scenario]:
    k = _threshold(instrument)
    return {
        "oral": Scenario(agent="ritlecitinib", dose=50.0, dose_unit="mg", frequency="QD",
                         week=52, threshold=k, phase3=True, route="oral"),
        "topical": Scenario(agent="ruxolitinib", dose=1.5, dose_unit="%", frequency="BID",
                            week=24, threshold=k, phase3=True, route="topical"),
    }  # fmt: skip


def q_draws(posterior: Posterior, scenario: Scenario) -> np.ndarray:
    """Expected rate in a new trial per posterior draw (new-trial effects averaged out)."""
    from vitiligo.models.jak_mbma import predict_draws

    return np.mean(
        [predict_draws(posterior, scenario, seed=1000 + s)[0] for s in range(K_Q)], axis=0
    )


def _items(registry: list[ArmEndpointRow], instrument: str) -> list[dict[str, Any]]:
    toplines = load_toplines(TOPLINE_CURATION)
    paper = [
        r
        for r in new_rows(to_arm_rows(load_curation(PAPER_CURATION)), registry)
        if "population:nri" in r.flags
    ]
    items = []
    for trial in TOPLINE_TRIALS:
        rows = [r for r in toplines if r.source_id == trial and r.instrument == instrument]
        items.append({"name": f"topline {trial} {instrument}", "kind": "topline", "rows": rows})
    for trial, label in PAPER_ITEMS[instrument]:
        rows = [r for r in paper if r.source_id == trial and r.instrument == instrument]
        items.append({"name": f"paper: {label}", "kind": "paper", "rows": rows})
    assert all(item["rows"] for item in items), [i["name"] for i in items if not i["rows"]]
    return items


def _arm_index(posterior: Posterior, row: ArmEndpointRow) -> int | None:
    dose = daily_dose(row.dose_value, row.frequency)
    for i, arm in enumerate(posterior.data.arms):
        if (arm.source_id, arm.active, arm.agent, arm.daily_dose, arm.loading_dose, arm.phototherapy) == (
            row.source_id, True, row.arm_agent, dose, row.loading_dose_value, row.phototherapy,
        ):  # fmt: skip
            return i
    return None


def item_armweeks(
    posterior: Posterior,
    rows: list[ArmEndpointRow],
    routes: dict[str, str],
    phase3: dict[str, bool],
) -> tuple[list[voi.ArmWeek], list[np.ndarray]]:
    """The item's arm-weeks as per-draw cumulative probabilities, and the observed bin counts."""
    from vitiligo.models.jak_mbma import predict_draws

    groups: dict[tuple[Any, ...], list[ArmEndpointRow]] = {}
    for r in rows:
        key = (r.source_id, r.arm_role, r.arm_agent, r.dose_value, r.frequency,
               r.loading_dose_value, r.phototherapy, r.week)  # fmt: skip
        groups.setdefault(key, []).append(r)
    reference = next(r for r in rows if r.arm_role == "active")  # placebo arms borrow its scenario
    arms, observed = [], []
    for members in groups.values():
        members.sort(key=lambda r: r.threshold or 0)
        first = members[0]
        source = first if first.arm_role == "active" else reference
        trial = first.source_id if first.source_id in posterior.data.trials else None
        arm = _arm_index(posterior, first) if trial and first.arm_role == "active" else None
        replicates = (
            1 if trial is not None and (arm is not None or first.arm_role != "active") else K_ITEM
        )
        cumulative = np.zeros((replicates, len(posterior.draws["mu0"]), len(members)))
        for m, row in enumerate(members):
            assert source.arm_agent is not None and source.dose_value is not None and row.threshold
            scenario = Scenario(
                agent=source.arm_agent, dose=source.dose_value, dose_unit=source.dose_unit or "",
                frequency=source.frequency, week=first.week or 0, threshold=row.threshold,
                loading_dose=source.loading_dose_value is not None, phototherapy=source.phototherapy,
                route=routes.get(source.arm_agent), phase3=phase3.get(first.source_id, False),
            )  # fmt: skip
            for k in range(replicates):
                p_active, p_control = predict_draws(
                    posterior, scenario, trial=trial, arm=arm, seed=7 + k
                )
                cumulative[k, :, m] = p_active if first.arm_role == "active" else p_control
        n = first.n_analyzed
        assert n and all(r.responders is not None for r in members)
        arms.append(voi.ArmWeek(cumulative=cumulative, n=n))
        observed.append(voi.counts_from_cumulative(n, [int(r.responders or 0) for r in members]))
    return arms, observed


def _fit(
    rows: list[ArmEndpointRow], instrument: str, routes: dict[str, str], phase3: dict[str, bool]
) -> Posterior:
    posterior = fit(
        build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3), SETTINGS
    )
    print(instrument, len(rows), posterior.diagnostics, flush=True)
    return posterior


def retro(instrument: str) -> None:
    registry, routes, phase3 = model_inputs_v03(with_toplines=False, with_papers=False)
    phase3 |= dict.fromkeys(TOPLINE_TRIALS, True)
    m0 = _fit(registry, instrument, routes, phase3)
    questions = _questions(instrument)
    q0 = {name: q_draws(m0, sc) for name, sc in questions.items()}
    q0_sum = q0["oral"] + q0["topical"]
    results = []
    for item in _items(registry, instrument):
        arms, observed = item_armweeks(m0, item["rows"], routes, phase3)
        predicted_sum = voi.expected_variance_reduction(q0_sum, arms, sims=400, seed=1)
        predicted_oral = voi.expected_variance_reduction(q0["oral"], arms, sims=400, seed=1)
        reweighted_shift, reweighted_ess = voi.realized_shift(q0_sum, arms, observed)
        refit = _fit(registry + item["rows"], instrument, routes, phase3)
        q1 = {name: q_draws(refit, sc) for name, sc in questions.items()}
        realized_shift = float((q1["oral"] + q1["topical"]).mean() - q0_sum.mean())
        results.append({
            "item": item["name"], "kind": item["kind"], "instrument": instrument,
            "predicted_evr_sum": predicted_sum.evr, "predicted_evr_oral": predicted_oral.evr,
            "prior_var_sum": predicted_sum.prior_var, "mean_ess": predicted_sum.mean_ess,
            "realized_shift_sum": realized_shift, "realized_shift_oral": float(q1["oral"].mean() - q0["oral"].mean()),
            "surprise_ratio": realized_shift**2 / predicted_sum.evr if predicted_sum.evr > 0 else None,
            "reweighted_shift_sum": reweighted_shift, "reweighted_ess": reweighted_ess,
            "refit_diagnostics": refit.diagnostics,
        })  # fmt: skip
        print(
            json.dumps(
                {k: results[-1][k] for k in ("item", "predicted_evr_sum", "realized_shift_sum")}
            ),
            flush=True,
        )
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "instrument": instrument,
        "m0_diagnostics": m0.diagnostics,
        "q0": {name: {"mean": float(q.mean()), "sd": float(q.std())} for name, q in q0.items()},
        "items": results,
    }
    (OUT / f"retro-{instrument}.json").write_text(json.dumps(payload, indent=1, default=str) + "\n")


def _spearman(x: list[float], y: list[float]) -> float:
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def gate() -> None:
    items = []
    converged = True
    for instrument in ("F-VASI", "T-VASI"):
        payload = json.loads((OUT / f"retro-{instrument}.json").read_text())
        items += payload["items"]
        diagnostics = [payload["m0_diagnostics"]] + [
            i["refit_diagnostics"] for i in payload["items"]
        ]
        converged &= all(
            d["max_rhat"] <= 1.01 and d["min_ess_bulk"] >= 400 and d["divergences"] == 0
            for d in diagnostics
        )
    g1 = all(
        min(
            i["predicted_evr_oral"]
            for i in items
            if i["kind"] == "topline" and i["instrument"] == inst
        )
        > max(
            i["predicted_evr_oral"]
            for i in items
            if i["kind"] == "paper" and i["instrument"] == inst
        )
        for inst in ("F-VASI", "T-VASI")
    )
    rho = _spearman(
        [i["predicted_evr_sum"] for i in items], [i["realized_shift_sum"] ** 2 for i in items]
    )
    result = {
        "G1_toplines_above_paper_rows_for_q_oral": g1,
        "G2_spearman_predicted_vs_realized": rho,
        "G2_passed": rho >= 0.5,
        "all_fits_converged": converged,
        "passed": g1 and rho >= 0.5,
        "items": [
            {
                k: i[k]
                for k in (
                    "item",
                    "predicted_evr_sum",
                    "realized_shift_sum",
                    "surprise_ratio",
                    "mean_ess",
                )
            }
            for i in items
        ],
    }
    (OUT / "gate.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))


# Arm sizes for the sealed targets: registered enrollment split equally across arms,
# except where public reports give them (Tranquillo, Tranquillo 2: EADV 2026).
TARGET_SIZES = {
    ("NCT06548360", 1.5): (90, 90),  # 180 enrolled, 2 arms
    ("NCT06804811", 0.75): (83, 83),  # 250 enrolled, 3 arms
    ("NCT06804811", 1.5): (83, 83),
    ("NCT05583526", 50.0): (401, 202),
    ("NCT06072183", 50.0): (206, 208),
}


def discriminate() -> None:
    from vitiligo.reports.paper_results import load_toplines  # noqa: F401  (keeps imports explicit)

    by_target: dict[tuple[Any, ...], dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    for path, record in sealed_records([Path("forecasts")]):
        if not record.get("draws_file"):
            continue
        model = (
            str(record.get("model", "?"))
            .removeprefix("jak_mbma ordered-probit ")
            .removesuffix(" (challenger)")
        )
        with np.load(path.parent / record["draws_file"]) as d:
            draws = (
                np.asarray(d["p_active"], dtype=float),
                np.asarray(d["p_control"], dtype=float),
            )
        key = comparison_key(record)
        if key is not None:
            by_target.setdefault(key, {})[model] = draws
    results = []
    for key, models in sorted(by_target.items()):
        sizes = TARGET_SIZES.get((key[0], key[4]))
        if sizes is None or len(models) < 2:
            continue
        info = voi.model_discrimination(models, *sizes, sims=2000, seed=0)
        results.append({"target": list(key), "models": sorted(models), "n_active": sizes[0],
                        "n_control": sizes[1], **info})  # fmt: skip
    results.sort(key=lambda r: -r["mutual_information_nats"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "discrimination.json").write_text(json.dumps(results, indent=1) + "\n")
    for r in results:
        print(f"{r['mutual_information_nats']:.3f} / {r['max_nats']:.3f} nats  "
              f"P(true model >= 75%) {r['p_true_model_gets_75pct']:.2f}  {r['target']}  {r['models']}")  # fmt: skip


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "retro":
        retro(sys.argv[2])
    elif command == "gate":
        gate()
    elif command == "discriminate":
        discriminate()
    else:
        raise SystemExit(__doc__)
