"""Size of a randomized maintenance trial after JAK-induced repigmentation: stop vs step down.

    python scripts/durability/maintenance_trial_size.py

Schoenfeld's formula for a log-rank test with 1:1 allocation: events needed
D = 4 (z_{1-alpha/2} + z_{power})^2 / (ln HR)^2. Patients needed = D divided by
the average probability of an event within follow-up, inflated for dropout.
The stop arm's 52-week loss probability spans the range our evidence gives
(docs/durability/README.md); the maintenance arm's follows from the hazard
ratio under proportional hazards.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

Z_ALPHA = 1.959964  # two-sided 5%
Z_POWER = 0.841621  # 80% power
DROPOUT = 0.15

# One-year loss of response after stopping, from the evidence:
#   0.27 relapse below F-VASI75 after stopping the cream (TRuE-V, Schoenfeld events)
#   0.58 the sealed oral forecast's median (1 - 0.42)
#   0.73 loss of a threshold patients sit just above (TRuE-V F-VASI90, constant hazard)
STOP_LOSS = (0.27, 0.58, 0.73)
HAZARD_RATIOS = (0.4, 0.5, 0.6)


def size(stop_loss: float, hr: float) -> dict[str, float]:
    events = 4 * (Z_ALPHA + Z_POWER) ** 2 / math.log(hr) ** 2
    maintain_loss = 1 - (1 - stop_loss) ** hr
    p_event = (stop_loss + maintain_loss) / 2
    patients = events / p_event / (1 - DROPOUT)
    return {
        "stop_loss_52w": stop_loss,
        "hazard_ratio": hr,
        "maintenance_loss_52w": round(maintain_loss, 3),
        "events": math.ceil(events),
        "patients_total": math.ceil(patients),
        "per_arm": math.ceil(patients / 2),
    }


def main() -> None:
    rows = [size(s, hr) for s in STOP_LOSS for hr in HAZARD_RATIOS]
    out = Path("docs/durability/data/maintenance-trial-size.json")
    out.write_text(
        json.dumps({"alpha": 0.05, "power": 0.8, "dropout": DROPOUT, "rows": rows}, indent=1) + "\n"
    )
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
