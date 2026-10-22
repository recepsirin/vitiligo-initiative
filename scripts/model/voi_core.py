"""Value-of-information core: retrospective gate and model discrimination.

Pre-registered in docs/voi-preregistration.md.

    python scripts/model/voi_core.py retro F-VASI    # one instrument: M0, predicted value, refits
    python scripts/model/voi_core.py retro T-VASI
    python scripts/model/voi_core.py gate            # G1 and G2 over the 11 items
    python scripts/model/voi_core.py diagnose T-VASI # surprise and Pareto-k per item
    python scripts/model/voi_core.py discriminate    # sealed targets: which would separate models
    python scripts/model/voi_core.py rank            # pending evidence (docs/voi-ranking-preregistration.md)
    python scripts/model/voi_core.py rank-mc         # post hoc: Monte Carlo spread of the ranking
    python scripts/model/voi_core.py rank-score      # prospective test on resolved items

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
K_ITEM = 64  # new-trial replicates in an item's likelihood (shared by its arms)
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
        reweighted_shift, reweighted_ess, reweighted_k = voi.realized_shift(q0_sum, arms, observed)
        item_surprise = voi.surprise(arms, observed, sims=400, seed=2)
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
            "reweighted_pareto_k": reweighted_k, "surprise": item_surprise,
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


def diagnose(instrument: str) -> None:
    """Surprise and Pareto-k for each retrospective item, from M0 (cached in exports/)."""
    import pickle

    registry, routes, phase3 = model_inputs_v03(with_toplines=False, with_papers=False)
    phase3 |= dict.fromkeys(TOPLINE_TRIALS, True)
    cache = Path("exports/voi") / f"m0-{instrument}.pkl"
    if cache.exists():
        m0 = pickle.loads(cache.read_bytes())
    else:
        m0 = _fit(registry, instrument, routes, phase3)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps(m0))
    questions = _questions(instrument)
    q_sum = sum(q_draws(m0, sc) for sc in questions.values())
    retro_items = {
        i["item"]: i for i in json.loads((OUT / f"retro-{instrument}.json").read_text())["items"]
    }
    out = []
    for item in _items(registry, instrument):
        arms, observed = item_armweeks(m0, item["rows"], routes, phase3)
        shift, ess, k = voi.realized_shift(q_sum, arms, observed)
        out.append({
            "item": item["name"],
            "surprise": voi.surprise(arms, observed, sims=400, seed=2),
            "reweighted_shift_sum": shift, "reweighted_pareto_k": k, "reweighted_ess": ess,
            "refit_shift_sum": retro_items[item["name"]]["realized_shift_sum"],
        })  # fmt: skip
        print(json.dumps(out[-1]), flush=True)
    (OUT / f"diagnostics-{instrument}.json").write_text(json.dumps(out, indent=1) + "\n")


def rescore(instrument: str) -> None:
    """Predicted values with the current engine, from cached M0, against the stored refits."""
    import pickle

    registry, routes, phase3 = model_inputs_v03(with_toplines=False, with_papers=False)
    phase3 |= dict.fromkeys(TOPLINE_TRIALS, True)
    m0 = pickle.loads((Path("exports/voi") / f"m0-{instrument}.pkl").read_bytes())
    questions = _questions(instrument)
    q0 = {name: q_draws(m0, sc) for name, sc in questions.items()}
    q0_sum = q0["oral"] + q0["topical"]
    stored = json.loads((OUT / f"retro-{instrument}.json").read_text())
    by_name = {i["item"]: i for i in stored["items"]}
    items = []
    for item in _items(registry, instrument):
        arms, _observed = item_armweeks(m0, item["rows"], routes, phase3)
        total = voi.expected_variance_reduction(q0_sum, arms, sims=400, seed=1)
        oral = voi.expected_variance_reduction(q0["oral"], arms, sims=400, seed=1)
        old = by_name[item["name"]]
        items.append({**old, "predicted_evr_sum": total.evr, "predicted_evr_oral": oral.evr,
                      "mean_ess": total.mean_ess,
                      "surprise_ratio": old["realized_shift_sum"] ** 2 / total.evr})  # fmt: skip
        print(
            json.dumps(
                {"item": item["name"], "evr": total.evr, "shift": old["realized_shift_sum"]}
            ),
            flush=True,
        )
    stored["items"] = items
    stored["engine"] = "v1.1 (arms of a trial share replicates; K_ITEM=64); post-hoc re-score"
    (OUT / f"retro-v1.1-{instrument}.json").write_text(
        json.dumps(stored, indent=1, default=str) + "\n"
    )


def _spearman(x: list[float], y: list[float]) -> float:
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def gate(version: str = "") -> None:
    items = []
    converged = True
    for instrument in ("F-VASI", "T-VASI"):
        payload = json.loads((OUT / f"retro{version}-{instrument}.json").read_text())
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
    (OUT / f"gate{version}.json").write_text(json.dumps(result, indent=1) + "\n")
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


# Items of docs/voi-ranking-preregistration.md (sealed 2026-10-22), transcribed as
# (daily dose per regimen, arm size). Drugs B has no data for get a nominal dose of 1:
# their predictions do not depend on dose, so the arms differ only by arm deviations.
RANK_ITEMS: list[dict[str, Any]] = [
    {"item": "1 STOP-V1", "trial": "NCT06113445", "agent": "povorcitinib", "unit": "mg",
     "frequency": "QD", "week": 52, "phase3": True, "arms": [(30.0, 222)], "control": 222,
     "public": ["F-VASI"]},
    {"item": "2 STOP-V2", "trial": "NCT06113471", "agent": "povorcitinib", "unit": "mg",
     "frequency": "QD", "week": 52, "phase3": True, "arms": [(30.0, 222)], "control": 222,
     "public": ["F-VASI"]},
    {"item": "3 povorcitinib China", "trial": "NCT07865312", "agent": "povorcitinib",
     "unit": "mg", "frequency": "QD", "week": 52, "phase3": True, "arms": [(30.0, 87)],
     "control": 87, "public": []},
    {"item": "4 ruxolitinib cream, children (NCT06548360)", "trial": "NCT06548360",
     "agent": "ruxolitinib", "unit": "%", "frequency": "BID", "week": 24, "phase3": True,
     "arms": [(1.5, 90)], "control": 90, "public": []},
    {"item": "5 ruxolitinib cream, children (NCT06804811)", "trial": "NCT06804811",
     "agent": "ruxolitinib", "unit": "%", "frequency": "BID", "week": 24, "phase3": True,
     "arms": [(0.75, 83), (1.5, 83)], "control": 84, "public": []},
    {"item": "6 Tranquillo 2, 50 mg arm", "trial": "NCT06072183", "agent": "ritlecitinib",
     "unit": "mg", "frequency": "QD", "week": 52, "phase3": True, "arms": [(50.0, 206)],
     "control": None, "public": []},
    {"item": "7 zasocitinib", "trial": "NCT07108283", "agent": "zasocitinib", "unit": "mg",
     "frequency": "QD", "week": 24, "phase3": False, "arms": [(1.0, 40)] * 3, "control": 80,
     "public": []},
]  # fmt: skip
B_DATA_SHA256 = {"F-VASI": "48a62f5f4f62", "T-VASI": "249569d81638"}  # the sealed v0.4 records
RANK_SIMS = 1000


def rank_armweeks(
    posterior: Posterior, item: dict[str, Any], threshold: int, routes: dict[str, str]
) -> list[voi.ArmWeek]:
    """An item's arm-weeks: K_ITEM shared replicates of a new trial, or a trial B has fitted."""
    from vitiligo.models.jak_mbma import predict_draws, predict_trial_draws

    regimens = [
        Scenario(agent=item["agent"], dose=dose, dose_unit=item["unit"],
                 frequency=item["frequency"], week=item["week"], threshold=threshold,
                 phase3=item["phase3"], route=routes.get(item["agent"], "oral"))
        for dose, _n in item["arms"]
    ]  # fmt: skip
    draws = len(posterior.draws["mu0"])
    if item["trial"] in posterior.data.trials:
        # A new arm in a fitted trial: the trial's fitted baseline and effects, a new deviation.
        assert item["control"] is None and len(regimens) == 1
        cumulative = np.zeros((K_ITEM, draws, 1))
        for k in range(K_ITEM):
            cumulative[k, :, 0] = predict_draws(
                posterior, regimens[0], trial=item["trial"], seed=7 + k
            )[0]
        return [voi.ArmWeek(cumulative=cumulative, n=item["arms"][0][1])]
    arms = np.zeros((len(regimens), K_ITEM, draws, 1))
    control = np.zeros((K_ITEM, draws, 1))
    for k in range(K_ITEM):
        p_control, p_arms = predict_trial_draws(posterior, regimens, seed=7 + k)
        control[k, :, 0] = p_control
        for a, p in enumerate(p_arms):
            arms[a, k, :, 0] = p
    out = [voi.ArmWeek(cumulative=arms[a], n=n) for a, (_dose, n) in enumerate(item["arms"])]
    return [*out, voi.ArmWeek(cumulative=control, n=item["control"])]


def rank() -> None:
    import hashlib
    from dataclasses import asdict

    from vitiligo.discovery.forecasts import committed_code

    code = committed_code()
    rows, routes, phase3 = model_inputs_v03(with_toplines=True)
    results = []
    diagnostics = {}
    for instrument in ("F-VASI", "T-VASI"):
        data = build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3)
        observations = [asdict(o) for o in data.observations]
        data_sha = hashlib.sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest()
        if not data_sha.startswith(B_DATA_SHA256[instrument]):
            raise SystemExit(f"{instrument}: data {data_sha[:12]} is not the sealed v0.4 data")
        b = fit(data, SETTINGS)
        print(instrument, b.diagnostics, flush=True)
        d = b.diagnostics
        if not (d["max_rhat"] <= 1.01 and d["min_ess_bulk"] >= 400 and d["divergences"] == 0):
            raise SystemExit(f"{instrument}: B did not converge; nothing ranked")
        diagnostics[instrument] = {**d, "data_sha256": data_sha}
        questions = _questions(instrument)
        q = {name: q_draws(b, sc) for name, sc in questions.items()}
        q_sum = q["oral"] + q["topical"]
        for item in RANK_ITEMS:
            arms = rank_armweeks(b, item, _threshold(instrument), routes)
            total = voi.expected_variance_reduction(q_sum, arms, sims=RANK_SIMS, seed=1)
            oral = voi.expected_variance_reduction(q["oral"], arms, sims=RANK_SIMS, seed=1)
            results.append({
                "item": item["item"], "trial": item["trial"], "instrument": instrument,
                "evr_sum": total.evr, "evr_oral": oral.evr, "prior_var_sum": total.prior_var,
                "mean_ess": total.mean_ess, "min_ess": total.min_ess,
                "outcome_public": instrument in item["public"],
            })  # fmt: skip
            print(json.dumps(results[-1]), flush=True)
    order = sorted(
        {r["item"] for r in results},
        key=lambda name: (
            -next(
                r["evr_sum"] for r in results if r["item"] == name and r["instrument"] == "F-VASI"
            )
        ),
    )
    out = OUT / "ranking"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ranking-2026-10-22.json").write_text(
        json.dumps(
            {
                "preregistration": "docs/voi-ranking-preregistration.md",
                "code": code,
                "base_model": diagnostics,
                "order_by_f_vasi_evr": order,
                "items": results,
            },
            indent=1,
        )
        + "\n"
    )


def rank_mc(seeds: tuple[int, ...] = (2, 3, 4, 5, 6)) -> None:
    """Post hoc, not pre-registered: the ranking's EVR repeated with other simulation seeds."""
    from vitiligo.discovery.forecasts import committed_code

    code = committed_code()
    rows, routes, phase3 = model_inputs_v03(with_toplines=True)
    out: dict[str, Any] = {"code": code, "seeds": list(seeds), "items": []}
    for instrument in ("F-VASI", "T-VASI"):
        b = fit(build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3), SETTINGS)
        print(instrument, b.diagnostics, flush=True)
        q_sum = sum(q_draws(b, sc) for sc in _questions(instrument).values())
        for item in RANK_ITEMS:
            arms = rank_armweeks(b, item, _threshold(instrument), routes)
            evr = [
                voi.expected_variance_reduction(q_sum, arms, sims=RANK_SIMS, seed=seed).evr
                for seed in seeds
            ]
            out["items"].append({"item": item["item"], "instrument": instrument, "evr_sum": evr,
                                 "mean": float(np.mean(evr)), "sd": float(np.std(evr, ddof=1))})  # fmt: skip
            print(json.dumps(out["items"][-1]), flush=True)
    (OUT / "ranking" / "monte-carlo-2026-10-22.json").write_text(json.dumps(out, indent=1) + "\n")


RESOLVED = OUT / "ranking" / "resolved.json"


def rank_score() -> None:
    """The pre-registered prospective test: realized shifts of resolved items against their EVR.

    Resolved results are curated in ``forecasts/voi/ranking/resolved.json`` in the
    format of ``curation/topline-results.json``, each with the ``item`` it resolves.
    """
    import hashlib
    from dataclasses import asdict

    from vitiligo.discovery.forecasts import committed_code
    from vitiligo.reports.paper_results import toplines_from

    code = committed_code()
    ranking = json.loads((OUT / "ranking" / "ranking-2026-10-22.json").read_text())
    predicted = {(r["item"], r["instrument"]): r for r in ranking["items"]}
    entries = json.loads(RESOLVED.read_text())["results"] if RESOLVED.exists() else []
    pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in entries:
        if (e["item"], e["instrument"]) not in predicted:
            raise SystemExit(f"not a ranked item-instrument pair: {e['item']}, {e['instrument']}")
        pairs.setdefault((e["item"], e["instrument"]), []).append(e)
    rows, routes, phase3 = model_inputs_v03(with_toplines=True)
    item_phase3 = {i["item"]: i["phase3"] for i in RANK_ITEMS}
    scored = []
    for instrument in ("F-VASI", "T-VASI"):
        todo = {k: v for k, v in pairs.items() if k[1] == instrument}
        if not todo:
            continue
        data = build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3)
        observations = [asdict(o) for o in data.observations]
        data_sha = hashlib.sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest()
        if not data_sha.startswith(B_DATA_SHA256[instrument]):
            raise SystemExit(f"{instrument}: data {data_sha[:12]} is not the sealed v0.4 data")
        b = fit(data, SETTINGS)
        questions = _questions(instrument)
        q0 = sum(q_draws(b, sc) for sc in questions.values())
        for (item, _instrument), item_entries in sorted(todo.items()):
            new_rows = toplines_from(item_entries)
            item_flags = dict.fromkeys({r.source_id for r in new_rows}, item_phase3[item])
            refit = fit(
                build_dataset(rows + new_rows, instrument, agent_routes=routes,
                              trial_phase3=phase3 | item_flags),
                SETTINGS,
            )  # fmt: skip
            d = refit.diagnostics
            ok = d["max_rhat"] <= 1.01 and d["min_ess_bulk"] >= 400 and d["divergences"] == 0
            q1 = sum(q_draws(refit, sc) for sc in questions.values())
            p = predicted[(item, instrument)]
            scored.append({
                "item": item, "instrument": instrument, "evr_sum": p["evr_sum"],
                "realized_shift_sum": float(q1.mean() - q0.mean()),
                "outcome_public_at_sealing": p["outcome_public"], "refit_converged": ok,
                "refit_diagnostics": d, "sources": sorted({e["source_url"] for e in item_entries}),
            })  # fmt: skip
            print(json.dumps(scored[-1]), flush=True)
    eligible = [s for s in scored if not s["outcome_public_at_sealing"] and s["refit_converged"]]
    result = {
        "preregistration": "docs/voi-ranking-preregistration.md",
        "code": code,
        "test": voi.prospective_test(
            [s["evr_sum"] for s in eligible], [s["realized_shift_sum"] for s in eligible]
        ),
        "scored": scored,
    }
    (OUT / "ranking" / "prospective.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result["test"]))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "retro":
        retro(sys.argv[2])
    elif command == "gate":
        gate(sys.argv[2] if len(sys.argv) > 2 else "")
    elif command == "rescore":
        rescore(sys.argv[2])
    elif command == "diagnose":
        diagnose(sys.argv[2])
    elif command == "discriminate":
        discriminate()
    elif command == "rank":
        rank()
    elif command == "rank-mc":
        rank_mc()
    elif command == "rank-score":
        rank_score()
    else:
        raise SystemExit(__doc__)
