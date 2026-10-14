"""Program search on S (weeks <= 24 only), as pre-registered.

Search score: leave-one-trial-out with the control arm kept, mean log predictive
probability per held-out active arm-week (the benchmark's targets exactly).
Evolution: start from the baseline; each generation evaluates every untried
one-component mutation of the current top 3; stop when a generation improves
the best score by < 0.005 nats per arm-week, or at 500 programs.

Run from lab/simulator:  python -m vsim.search
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

import numpy as np

from vsim.data import ROOT, ArmWeek, controlled_trials, load_rows, reference_doses, search_set
from vsim.program import Context, Spec, fit_program, predict
from vsim.score import score

LOG = ROOT / "results" / "programs.jsonl"
BUDGET = 500
MIN_GAIN = 0.005
TOP = 3


def context(rows: Any, routes: dict[str, str]) -> Context:
    s = search_set(rows, routes)
    oral = frozenset(a.trial for a in s if a.active and a.agent and routes[a.agent] == "oral")
    return Context(routes, reference_doses(rows, routes), oral)


def loto_targets(s: list[ArmWeek], trial: str) -> list[ArmWeek]:
    """The benchmark's targets: active arm-weeks of ``trial`` in instruments where it is controlled."""
    out = []
    for instrument in ("F-VASI", "T-VASI"):
        sub = [a for a in s if a.instrument == instrument]
        if trial in controlled_trials(sub):
            out += [a for a in sub if a.trial == trial and a.active]
    return out


def _fold(args: tuple[Spec, str]) -> tuple[str, list[ArmWeek], list[np.ndarray], bool]:
    spec, trial = args
    rows, routes = load_rows()
    ctx = context(rows, routes)
    s = search_set(rows, routes)
    train = search_set(rows, routes, drop_active_of=trial)
    targets = loto_targets(s, trial)
    fit = fit_program(spec, train, ctx)
    return trial, targets, predict(fit, targets, seed=0), fit.success


def evaluate(spec: Spec, pool: ProcessPoolExecutor) -> dict[str, Any]:
    rows, routes = load_rows()
    s = search_set(rows, routes)
    trials = controlled_trials(s)
    start = time.time()
    results = list(pool.map(_fold, [(spec, t) for t in trials]))
    targets = [aw for _t, ts, _p, _ok in results for aw in ts]
    preds = [p for _t, _ts, ps, _ok in results for p in ps]
    scores, detail = score(targets, preds)
    full = fit_program(spec, s, context(rows, routes))
    return {
        "spec": asdict(spec),
        "name": spec.name,
        "score": scores.log_score_mean,
        "scores": scores.as_dict(),
        "params": full.model.size,
        "folds_converged": {t: ok for t, _ts, _p, ok in results},
        "full_fit_converged": full.success,
        "seconds": round(time.time() - start, 1),
        "per_trial": {
            t: round(float(np.mean([d["log_score"] for d in detail if d["trial"] == t])), 4)
            for t in trials
        },
    }


def load_log() -> list[dict[str, Any]]:
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]


def append(record: dict[str, Any]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def run(proposals: list[tuple[Spec, str]] | None = None) -> None:
    """Resume the evolution from the log; ``proposals`` are extra programs to try first."""
    done = load_log()
    tried = {r["name"] for r in done}
    workers = min(6, os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=workers) as pool:

        def try_spec(spec: Spec, parent: str | None, generation: int, by: str) -> None:
            if spec.name in tried or len(done) >= BUDGET:
                return
            record = evaluate(spec, pool)
            record |= {
                "id": len(done) + 1,
                "parent": parent,
                "generation": generation,
                "proposed_by": by,
                "evaluated_at": datetime.now(UTC).isoformat(),
            }
            append(record)
            done.append(record)
            tried.add(spec.name)
            print(f"#{record['id']:<3} gen {generation} score {record['score']:.4f} "
                  f"params {record['params']}  {spec.name}", flush=True)  # fmt: skip

        if not done:
            try_spec(Spec(), None, 0, "baseline")
        for spec, by in proposals or []:
            try_spec(spec.canonical(), None, max(r["generation"] for r in done), by)

        while len(done) < BUDGET:
            best_before = max(r["score"] for r in done)
            generation = max(r["generation"] for r in done) + 1
            top = sorted(done, key=lambda r: -r["score"])[:TOP]
            children = [
                (child, parent["name"])
                for parent in top
                for child in Spec(**parent["spec"]).mutations()
                if child.name not in tried
            ]
            if not children:
                print("no untried mutations of the top programs", flush=True)
                break
            for child, parent_name in children:
                try_spec(child, parent_name, generation, "mutation")
            gain = max(r["score"] for r in done) - best_before
            print(f"generation {generation}: best gain {gain:.4f}", flush=True)
            if gain < MIN_GAIN:
                break


if __name__ == "__main__":
    run()
