"""Cost comparison of vitiligo maintenance regimens: daily ruxolitinib vs twice-weekly tacrolimus.

    python scripts/durability/maintenance_cost.py

Compares the annual direct medication costs, and the cost per relapse prevented, of:
- Continuous daily ruxolitinib 1.5% cream (standard of care continuing)
- Intermittent twice-weekly ruxolitinib 1.5% cream (step-down JAK)
- Proactive twice-weekly tacrolimus 0.1% ointment (cheap generic step-down)
- Complete treatment cessation (vehicle / observation), the comparator

Cost per relapse prevented is a year's drug cost divided by the share of responders
whose relapse the regimen prevents in that year: the loss after stopping minus the
loss on the regimen, from the regimen's own hazard ratio against stopping. The loss
after stopping is unknown for the people who would be treated, so the figure is given
for each of the three scenarios ``vitiligo.models.relapse_evidence`` works out, and a
regimen no trial has tested gets none. That module also says what the model assumed
before (one relapse rate misread, and every regimen as good as continuous ruxolitinib).

Addresses roadmap item 4.1 for the stop-vs-step-down trial concept (docs/durability/maintenance-trial-concept.md)
and the safety and access evidence map (docs/safety-access/README.md).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vitiligo.models.relapse_evidence import MAINTENANCE, STOP_LOSS, maintained_loss

# Pricing benchmarks (2026):
# US Wholesale Acquisition Cost (WAC) / Retail cash benchmark (GoodRx/Drugs.com)
US_RUX_TUBE_COST = 2094.00  # 60 g tube ($34.90 / g)
US_RUX_TUBE_GRAMS = 60.0
US_TAC_TUBE_COST = 45.00  # 60 g generic ointment ($0.75 / g)
US_TAC_TUBE_GRAMS = 60.0

# England / NHS Drug Tariff & NICE List Price (TA1140)
UK_RUX_TUBE_COST = 657.00  # 100 g tube (£6.57 / g)
UK_RUX_TUBE_GRAMS = 100.0
UK_TAC_TUBE_COST = 31.50  # 60 g generic ointment (£0.525 / g)
UK_TAC_TUBE_GRAMS = 60.0


@dataclass
class RegimenCost:
    profile: str
    regimen: str
    frequency: str
    annual_grams: float
    tubes_needed: int
    cost_usd: float
    cost_gbp: float
    usd_savings_vs_cont_rux: float
    pct_savings_vs_cont_rux: float
    hazard_ratio: float | None
    relapse_prevention: list[dict[str, float]] | None


def relapse_prevention(
    cost_usd: float, cost_gbp: float, hazard_ratio: float | None
) -> list[dict[str, float]] | None:
    """Relapses prevented and their cost, for each loss-after-stopping scenario."""
    if hazard_ratio is None:
        return None
    rows = []
    for scenario in STOP_LOSS:
        on_regimen = maintained_loss(scenario.value, hazard_ratio)
        prevented = scenario.value - on_regimen
        rows.append(
            {
                "stop_loss_52w": scenario.value,
                "maintained_loss_52w": round(on_regimen, 3),
                "relapses_prevented_per_100": round(prevented * 100, 1),
                "cost_per_relapse_prevented_usd": round(cost_usd / prevented, 2),
                "cost_per_relapse_prevented_gbp": round(cost_gbp / prevented, 2),
            }
        )
    return rows


def compute_costs(
    profile_name: str,
    daily_rux_grams: float,
    twice_weekly_grams_per_application: float,
) -> list[RegimenCost]:
    """Compute annual costs for a given patient extent profile."""
    # 1. Continuous daily ruxolitinib 1.5% cream (365 days)
    ann_g_rux_cont = daily_rux_grams * 365.0
    tubes_rux_us = int(-(-ann_g_rux_cont // US_RUX_TUBE_GRAMS))
    tubes_rux_uk = int(-(-ann_g_rux_cont // UK_RUX_TUBE_GRAMS))
    cost_rux_cont_us = tubes_rux_us * US_RUX_TUBE_COST
    cost_rux_cont_uk = tubes_rux_uk * UK_RUX_TUBE_COST

    # 2. Intermittent twice-weekly ruxolitinib 1.5% cream (104 applications)
    ann_g_rux_2w = twice_weekly_grams_per_application * 104.0
    tubes_rux_2w_us = int(-(-ann_g_rux_2w // US_RUX_TUBE_GRAMS))
    tubes_rux_2w_uk = int(-(-ann_g_rux_2w // UK_RUX_TUBE_GRAMS))
    cost_rux_2w_us = tubes_rux_2w_us * US_RUX_TUBE_COST
    cost_rux_2w_uk = tubes_rux_2w_uk * UK_RUX_TUBE_COST

    # 3. Proactive twice-weekly tacrolimus 0.1% ointment (104 applications)
    ann_g_tac_2w = twice_weekly_grams_per_application * 104.0
    tubes_tac_2w_us = int(-(-ann_g_tac_2w // US_TAC_TUBE_GRAMS))
    tubes_tac_2w_uk = int(-(-ann_g_tac_2w // UK_TAC_TUBE_GRAMS))
    cost_tac_2w_us = tubes_tac_2w_us * US_TAC_TUBE_COST
    cost_tac_2w_uk = tubes_tac_2w_uk * UK_TAC_TUBE_COST

    def saving(cost: float) -> tuple[float, float]:
        return round(cost_rux_cont_us - cost, 2), round(
            (cost_rux_cont_us - cost) / cost_rux_cont_us * 100, 1
        )

    def arm(
        regimen: str, frequency: str, grams: float, tubes: int, us: float, uk: float, key: str
    ) -> RegimenCost:
        hr = MAINTENANCE[key].hazard_ratio
        usd_saving, pct_saving = saving(us)
        return RegimenCost(
            profile=profile_name,
            regimen=regimen,
            frequency=frequency,
            annual_grams=round(grams, 1),
            tubes_needed=tubes,
            cost_usd=round(us, 2),
            cost_gbp=round(uk, 2),
            usd_savings_vs_cont_rux=usd_saving,
            pct_savings_vs_cont_rux=pct_saving,
            hazard_ratio=hr,
            relapse_prevention=relapse_prevention(us, uk, hr),
        )

    return [
        arm(
            "Continuous Ruxolitinib 1.5% Cream",
            "Twice daily (365 days)",
            ann_g_rux_cont,
            tubes_rux_us,
            cost_rux_cont_us,
            cost_rux_cont_uk,
            "continuous_ruxolitinib",
        ),
        arm(
            "Twice-Weekly Ruxolitinib 1.5% Cream",
            "Twice weekly (104 days)",
            ann_g_rux_2w,
            tubes_rux_2w_us,
            cost_rux_2w_us,
            cost_rux_2w_uk,
            "twice_weekly_ruxolitinib",
        ),
        arm(
            "Twice-Weekly Tacrolimus 0.1% Ointment",
            "Twice weekly (104 days)",
            ann_g_tac_2w,
            tubes_tac_2w_us,
            cost_tac_2w_us,
            cost_tac_2w_uk,
            "twice_weekly_tacrolimus",
        ),
        # The comparator every hazard ratio is measured against.
        RegimenCost(
            profile=profile_name,
            regimen="Complete Cessation (Stop)",
            frequency="None (Observation)",
            annual_grams=0.0,
            tubes_needed=0,
            cost_usd=0.0,
            cost_gbp=0.0,
            usd_savings_vs_cont_rux=round(cost_rux_cont_us, 2),
            pct_savings_vs_cont_rux=100.0,
            hazard_ratio=None,
            relapse_prevention=None,
        ),
    ]


def assumptions() -> dict[str, Any]:
    names = {
        "continuous_ruxolitinib": "Continuous Ruxolitinib 1.5% Cream",
        "twice_weekly_ruxolitinib": "Twice-Weekly Ruxolitinib 1.5% Cream",
        "twice_weekly_tacrolimus": "Twice-Weekly Tacrolimus 0.1% Ointment",
    }
    return {
        "us_rux_60g_wac_usd": US_RUX_TUBE_COST,
        "us_tac_60g_retail_usd": US_TAC_TUBE_COST,
        "uk_rux_100g_nice_gbp": UK_RUX_TUBE_COST,
        "uk_tac_60g_tariff_gbp": UK_TAC_TUBE_COST,
        "stop_loss_scenarios": [{"value": s.value, "basis": s.basis} for s in STOP_LOSS],
        "maintenance_hazard_ratios": [
            {"regimen": names[k], "hazard_ratio": e.hazard_ratio, "basis": e.basis}
            for k, e in MAINTENANCE.items()
        ],
    }


def main() -> None:
    # Profile 1: Facial-only repigmentation (~1.0 g cream/day daily, 0.5 g/app twice weekly)
    facial = compute_costs(
        "Facial-only responder", daily_rux_grams=1.0, twice_weekly_grams_per_application=0.5
    )

    # Profile 2: Face + limited neck/hand patches (~2.0 g/day daily, 1.0 g/app twice weekly)
    face_body = compute_costs(
        "Face + limited body responder", daily_rux_grams=2.0, twice_weekly_grams_per_application=1.0
    )

    # Profile 3: Moderate body responder (~4.0 g/day daily, 2.0 g/app twice weekly)
    extensive = compute_costs(
        "Moderate body responder", daily_rux_grams=4.0, twice_weekly_grams_per_application=2.0
    )

    all_results = {
        "title": "Vitiligo Maintenance Therapy Pharmacoeconomic Model",
        "assumptions": assumptions(),
        "profiles": {
            "facial_only": [asdict(r) for r in facial],
            "face_and_limited_body": [asdict(r) for r in face_body],
            "moderate_body": [asdict(r) for r in extensive],
        },
    }

    out_dir = Path("docs/durability/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "maintenance-cost.json"
    out_json.write_text(json.dumps(all_results, indent=2) + "\n")
    print(f"Saved maintenance cost JSON to {out_json}")


if __name__ == "__main__":
    main()
