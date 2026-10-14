"""Selection and the locked exam, as pre-registered.

python -m vsim.exam select   # seal the selected program (once)
python -m vsim.exam run      # score it and the benchmark on E (needs the seal)
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from datetime import UTC, datetime
from typing import Any

import numpy as np

from vsim.benchmark import benchmark_draws
from vsim.data import ROOT, exam_targets_unlocked, load_rows, search_set
from vsim.program import Spec, fit_program, predict
from vsim.score import log_predictive, score
from vsim.search import context, load_log

SELECTION = ROOT / "results" / "selection.json"
EXAM = ROOT / "results" / "exam.json"
TIE = 0.01  # nats per arm-week
LOTO_TOLERANCE = 0.05
MIN_COVERAGE = 0.70


def _seal(record: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return {**record, "sha256": hashlib.sha256(body.encode()).hexdigest()}


def _verify(record: dict[str, Any]) -> bool:
    body = {k: v for k, v in record.items() if k != "sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest() == record.get("sha256")


def select() -> dict[str, Any]:
    """Best search score; within TIE of the best, fewer parameters win."""
    if SELECTION.exists():
        raise SystemExit(f"selection already sealed: {SELECTION}")
    log = load_log()
    best = max(r["score"] for r in log)
    tied = [r for r in log if r["score"] >= best - TIE]
    chosen = min(tied, key=lambda r: (r["params"], -r["score"]))
    record = _seal(
        {
            "selected_at": datetime.now(UTC).isoformat(),
            "programs_evaluated": len(log),
            "best_score": best,
            "tied_within": TIE,
            "tied": [{"id": r["id"], "score": r["score"], "params": r["params"]} for r in tied],
            "program": {k: chosen[k] for k in ("id", "name", "spec", "score", "params")},
        }
    )
    SELECTION.write_text(json.dumps(record, indent=1) + "\n")
    return record


def _bootstrap(trials: list[str], sim: dict[str, float], bench: dict[str, float]) -> list[float]:
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(4000):
        pick = rng.choice(trials, size=len(trials), replace=True)
        diffs.append(float(sum(sim[t] - bench[t] for t in pick)))
    return [float(q) for q in np.quantile(diffs, [0.025, 0.5, 0.975])]


def run() -> dict[str, Any]:
    if not SELECTION.exists():
        raise SystemExit("no sealed selection: run `python -m vsim.exam select` first")
    selection = json.loads(SELECTION.read_text())
    if not _verify(selection):
        raise SystemExit("selection seal does not match its content")
    spec = Spec(**selection["program"]["spec"])

    rows, routes = load_rows()
    targets = exam_targets_unlocked(rows, routes)

    fit = fit_program(spec, search_set(rows, routes), context(rows, routes))
    sim_preds = predict(fit, targets, seed=0)

    posteriors = {}
    for instrument in ("F-VASI", "T-VASI"):
        with open(ROOT / "results" / "benchmark" / f"posterior_s_{instrument}.pkl", "rb") as fh:
            posteriors[instrument] = pickle.load(fh)
    bench_preds = [
        benchmark_draws(posteriors[a.instrument], a, routes, condition_arm=True) for a in targets
    ]

    sim_scores, sim_detail = score(targets, sim_preds)
    bench_scores, bench_detail = score(targets, bench_preds)

    per_trial: dict[str, dict[str, float]] = {"simulator": {}, "benchmark": {}}
    for a, ps, pb in zip(targets, sim_preds, bench_preds, strict=True):
        for name, p in (("simulator", ps), ("benchmark", pb)):
            per_trial[name][a.trial] = per_trial[name].get(a.trial, 0.0) + log_predictive(a, p)
    trials = sorted(per_trial["simulator"])

    loto_bench = json.loads((ROOT / "results" / "benchmark" / "loto_s_score.json").read_text())
    criteria = {
        "1_exam_log_score_beats_benchmark": sim_scores.log_score_sum > bench_scores.log_score_sum,
        "2_exam_coverage80_at_least_0.70": sim_scores.coverage80 >= MIN_COVERAGE,
        "3_search_score_within_0.05_of_benchmark": selection["program"]["score"]
        >= loto_bench["scores"]["log_score_mean"] - LOTO_TOLERANCE,
    }
    result = {
        "run_at": datetime.now(UTC).isoformat(),
        "selection_sha256": selection["sha256"],
        "program": selection["program"],
        "fit": {"success": fit.success, "message": fit.message, "nlp": fit.nlp},
        "exam_arm_weeks": len(targets),
        "simulator": sim_scores.as_dict(),
        "benchmark": bench_scores.as_dict(),
        "search_score": {
            "simulator": selection["program"]["score"],
            "benchmark": loto_bench["scores"]["log_score_mean"],
        },
        "criteria": criteria,
        "decision": "continue" if all(criteria.values()) else "stop",
        "exploratory": {
            "per_trial_log_score": per_trial,
            "bootstrap_over_trials_sum_difference_q025_q50_q975": _bootstrap(
                trials, per_trial["simulator"], per_trial["benchmark"]
            ),
        },
        "detail": {"simulator": sim_detail, "benchmark": bench_detail},
    }
    EXAM.write_text(json.dumps(result, indent=1) + "\n")
    return result


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "select":
        print(json.dumps(select(), indent=1))
    elif command == "run":
        out = run()
        print(json.dumps({k: out[k] for k in ("program", "simulator", "benchmark",
                                              "search_score", "criteria", "decision")}, indent=1))  # fmt: skip
        print(json.dumps(out["exploratory"], indent=1))
    else:
        raise SystemExit(__doc__)
