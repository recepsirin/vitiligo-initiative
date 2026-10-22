"""Reference numbers from the TRuE-V randomized withdrawal (NCT04530344) for durability forecasts.

    python scripts/durability/truev_reference.py

Reads the posted results (docs/durability/data/nct04530344-results.json) and
derives, with stated approximations:

- **Events per arm from a hazard ratio's 95% CI** (Schoenfeld). With 1:1
  allocation, var(log HR) is about 4 / D, so D = 4 / SE²; the events split
  between arms in the ratio of their hazards, assuming similar exposure.
- **One-year retention from a median** under a constant hazard:
  S(364 days) = 0.5 ** (364 / median).

Writes docs/durability/data/truev-reference.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

POSTED = Path("docs/durability/data/nct04530344-results.json")
OUT = Path("docs/durability/data/truev-reference.json")
YEAR = 364  # days from week 52 to week 104
Z = 1.959964


def _measure(results: dict, prefix: str) -> dict:
    return next(m for m in results["outcome_measures"] if m["title"].startswith(prefix))


def _hr(measure: dict) -> dict[str, float]:
    a = measure["analyses"][0]
    hr, lo, hi = (float(a[k]) for k in ("paramValue", "ciLowerLimit", "ciUpperLimit"))
    se = (math.log(hi) - math.log(lo)) / (2 * Z)
    return {"hr": hr, "ci_low": lo, "ci_high": hi, "se_log_hr": se}


def _events(hr: float, se: float, n_stop: int, n_continue: int) -> dict[str, float]:
    total = 4 / se**2
    stopped = total / (1 + hr)
    continued = total - stopped
    return {
        "total": total,
        "stopped": stopped,
        "continued": continued,
        "share_stopped": stopped / n_stop,
        "share_continued": continued / n_continue,
    }


def main() -> None:
    results = json.loads(POSTED.read_text())
    relapse = _measure(results, "Time to Relapse")
    loss90 = _measure(results, "Time to Loss of Adequate Response")
    n_stop = int(relapse["denominators"]["OG000"])  # vehicle (stopped)
    n_continue = int(relapse["denominators"]["OG001"])  # ruxolitinib (continued)

    relapse_hr = _hr(relapse)
    loss90_hr = _hr(loss90)
    median_90 = loss90["values"][0]["by_group"]["OG000"]
    median, low, high = (float(median_90[k]) for k in ("value", "lowerLimit", "upperLimit"))

    out = {
        "source": results["source"],
        "n_stopped": n_stop,
        "n_continued": n_continue,
        "relapse_below_f_vasi75": {
            **relapse_hr,
            "events_schoenfeld": _events(
                relapse_hr["hr"], relapse_hr["se_log_hr"], n_stop, n_continue
            ),
            "median_stopped": "not reached (lower 95% limit 238 days)",
        },
        "loss_of_f_vasi90": {
            **loss90_hr,
            "events_schoenfeld": _events(
                loss90_hr["hr"], loss90_hr["se_log_hr"], n_stop, n_continue
            ),
            "median_stopped_days": {"median": median, "ci_low": low, "ci_high": high},
            "one_year_retention_stopped_constant_hazard": {
                "point": 0.5 ** (YEAR / median),
                "from_ci_low_median": 0.5 ** (YEAR / low),
                "from_ci_high_median": 0.5 ** (YEAR / high),
            },
        },
        "approximations": [
            "Schoenfeld: var(log HR) ~ 4 / events with 1:1 allocation",
            "events split by the hazard ratio, assuming similar exposure in both arms",
            "constant hazard after stopping for retention from a median",
        ],
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
