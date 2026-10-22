"""How much can Tranquillo LTE tell us about durability forecast 1? (Post hoc, after sealing.)

    python scripts/durability/informativeness.py

Simulates the trial at plausible arm sizes. Events within 52 weeks per arm are
binomial; the hazard ratio is estimated with SE = sqrt(1/d_stop + 1/d_continue).
Each posted estimate is scored as pre-registered, the sealed forecast against
the uninformed benchmark. The truth is drawn from the forecast itself, or fixed
at alternatives the forecast would get wrong.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from vitiligo.discovery import durability as dur

RECORD = Path("forecasts/durability/tranquillo-lte-withdrawal.json")
REPS = 4000


def simulate(rng, n, s_w, log_hr, mean, sd):
    advantage, estimable = [], 0
    for sw, lh in zip(s_w, log_hr, strict=True):
        d_stop = rng.binomial(n, 1 - sw)
        d_continue = rng.binomial(n, 1 - sw ** math.exp(lh))
        if d_stop == 0 or d_continue == 0:
            continue  # the hazard ratio is not estimable
        estimable += 1
        se = math.sqrt(1 / d_stop + 1 / d_continue)
        posted = lh + rng.normal(0, se)
        hr, lo, hi = (math.exp(posted + k * 1.96 * se) for k in (0, -1, 1))
        advantage.append(
            dur.hr_log_score(hr, lo, hi, mean, sd) - dur.hr_benchmark_log_score(hr, lo, hi)
        )
    a = np.array(advantage)
    return {
        "mean_advantage_nats": float(a.mean()),
        "forecast_wins": float((a > 0).mean()),
        "hr_estimable": estimable / len(s_w),
    }


def main() -> None:
    record = json.loads(RECORD.read_text())
    p = record["parameters"]
    with np.load(RECORD.parent / record["draws_file"]) as draws:
        s_w, log_hr = draws["s_w"], draws["log_hr"]
    rng = np.random.default_rng(7)
    pick = rng.permutation(len(s_w))[:REPS]
    scenarios = {
        "truth drawn from the forecast": (s_w[pick], log_hr[pick]),
        "continuing does nothing (HR 1, S_w 0.5)": (np.full(REPS, 0.5), np.zeros(REPS)),
        "responses mostly last (S_w 0.9, HR 0.5)": (
            np.full(REPS, 0.9),
            np.full(REPS, math.log(0.5)),
        ),
    }
    out = {
        scenario: {
            f"{n} per arm": simulate(rng, n, sw, lh, p["log_hr_mean"], p["log_hr_sd"])
            for n in (25, 35, 45)
        }
        for scenario, (sw, lh) in scenarios.items()
    }
    path = Path("docs/durability/data/informativeness.json")
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
