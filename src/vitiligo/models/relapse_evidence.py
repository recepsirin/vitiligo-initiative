"""What the project's evidence says about losing a response after repigmentation.

The durability scripts take their relapse figures from here, so the maintenance
trial's sizing (``scripts/durability/maintenance_trial_size.py``) and the cost model
(``scripts/durability/maintenance_cost.py``) cannot disagree. Each figure is worked
out from a published number recorded in ``docs/durability/README.md``.

**Loss of response within 52 weeks of stopping** is not known for the people a
maintenance trial would enrol, so it is carried as three scenarios spanning the
evidence:

- 0.27: relapse below F-VASI75 after stopping ruxolitinib cream in TRuE-V's
  randomized withdrawal. The registry posts a hazard ratio, not proportions; the
  events its confidence interval implies (Schoenfeld), apportioned by the hazard
  ratio, put about 15 in the 56-patient stop arm.
- 0.58: the sealed forecast for Tranquillo LTE (oral ritlecitinib) has 42% still
  responding a year after stopping, so 58% not.
- 0.73: loss of F-VASI90 in TRuE-V, the threshold responders sit just above:
  median 195 days, at a constant hazard over a year.

**A maintenance regimen's effect** is a hazard ratio against stopping:

- Continuous ruxolitinib cream: 0.42 (95% CI 0.18-0.99), TRuE-V's randomized
  withdrawal, relapse below F-VASI75.
- Twice-weekly tacrolimus ointment: the one maintenance trial (J Invest Dermatol
  2015, PMID 25521460) depigmented 26.8% of patches on tacrolimus and 48.4% on
  placebo by intention to treat, not significant once patients' several patches are
  allowed for (OR 2.55, 95% CI 0.65-9.97). Read as a hazard ratio under
  proportional hazards, 0.47.
- Twice-weekly ruxolitinib cream: no trial, so no estimate.

The cost model used to take 42% as the share relapsing after stopping -- it is the
forecast's share still responding -- and gave every maintenance regimen the
forecast's 25%, so twice-weekly tacrolimus and twice-weekly ruxolitinib were
assumed to work exactly as continuous ruxolitinib does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Z_95 = 1.959964

# Published figures, as docs/durability/README.md records them.
TRUEV_RELAPSE_HR = 0.42  # relapse below F-VASI75, continued vs stopped
TRUEV_RELAPSE_CI = (0.18, 0.99)
TRUEV_STOP_ARM = 56
TRUEV_F_VASI90_MEDIAN_DAYS = 195  # stopped arm, time to losing F-VASI90
TRANQUILLO_STILL_RESPONDING_AFTER_STOP = 0.42  # sealed forecast, 2026-10-23
TACROLIMUS_PATCHES_DEPIGMENTED = 0.268  # intention to treat
PLACEBO_PATCHES_DEPIGMENTED = 0.484


@dataclass(frozen=True)
class StopLoss:
    """A scenario for the share of responders who lose response within 52 weeks of stopping."""

    value: float
    basis: str


@dataclass(frozen=True)
class MaintenanceEffect:
    """A maintenance regimen's hazard ratio against stopping; None when no trial measured it."""

    hazard_ratio: float | None
    basis: str


def schoenfeld_stop_arm_loss(hr: float, ci_low: float, ci_high: float, stop_arm: int) -> float:
    """The stop arm's events per patient, from the events a hazard ratio's 95% CI implies."""
    se = (math.log(ci_high) - math.log(ci_low)) / (2 * Z_95)
    events = 4 / se**2
    return events / (1 + hr) / stop_arm


def hazard_ratio_from_proportions(treated: float, control: float) -> float:
    """The hazard ratio two event proportions over the same follow-up imply."""
    return math.log(1 - treated) / math.log(1 - control)


def maintained_loss(stop_loss: float, hazard_ratio: float) -> float:
    """The 52-week loss on a maintenance regimen, under proportional hazards."""
    return float(1 - (1 - stop_loss) ** hazard_ratio)


STOP_LOSS = (
    StopLoss(
        round(schoenfeld_stop_arm_loss(TRUEV_RELAPSE_HR, *TRUEV_RELAPSE_CI, TRUEV_STOP_ARM), 2),
        "TRuE-V randomized withdrawal: relapse below F-VASI75 after stopping ruxolitinib cream",
    ),
    StopLoss(
        round(1 - TRANQUILLO_STILL_RESPONDING_AFTER_STOP, 2),
        "Sealed Tranquillo LTE forecast for an oral JAK inhibitor: 42% still responding after stopping",
    ),
    StopLoss(
        round(1 - 0.5 ** (365 / TRUEV_F_VASI90_MEDIAN_DAYS), 2),
        "TRuE-V: loss of F-VASI90, the threshold responders sit just above (median 195 days)",
    ),
)

MAINTENANCE = {
    "continuous_ruxolitinib": MaintenanceEffect(
        TRUEV_RELAPSE_HR,
        "TRuE-V randomized withdrawal (NCT04530344): relapse below F-VASI75, 95% CI 0.18-0.99",
    ),
    "twice_weekly_tacrolimus": MaintenanceEffect(
        round(
            hazard_ratio_from_proportions(
                TACROLIMUS_PATCHES_DEPIGMENTED, PLACEBO_PATCHES_DEPIGMENTED
            ),
            2,
        ),
        "One trial (PMID 25521460): 26.8% vs 48.4% of patches depigmented, not significant"
        " once patients' several patches are allowed for",
    ),
    "twice_weekly_ruxolitinib": MaintenanceEffect(None, "No trial has tested it"),
}
