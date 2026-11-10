"""Cost comparison of vitiligo maintenance regimens: daily ruxolitinib vs twice-weekly tacrolimus.

    python scripts/durability/maintenance_cost.py

Compares the annual direct medication costs and cost per relapse prevented across:
- Continuous daily ruxolitinib 1.5% cream (standard of care continuing)
- Intermittent twice-weekly ruxolitinib 1.5% cream (step-down JAK)
- Proactive twice-weekly tacrolimus 0.1% ointment (cheap generic step-down)
- Complete treatment cessation (vehicle / observation)

Addresses roadmap item 4.1 for the stop-vs-step-down trial concept (docs/durability/maintenance-trial-concept.md)
and the safety and access evidence map (docs/safety-access/README.md).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

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

# Durability & Relapse Rates over 52 weeks (from TRuE-V randomized withdrawal, docs/durability/README.md):
# Stopping: ~42% lose response (< F-VASI75); Continuing: ~25% lose response.
P_RELAPSE_STOP = 0.42
P_RELAPSE_CONTINUE = 0.25
ARR_CONTINUE = P_RELAPSE_STOP - P_RELAPSE_CONTINUE  # 0.17
NNT_CONTINUE = 1.0 / ARR_CONTINUE  # 5.88 patients per relapse prevented


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
    cost_per_relapse_prevented_usd: float
    cost_per_relapse_prevented_gbp: float


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

    # 4. Complete cessation (vehicle / stop)
    cost_stop_us = 0.0
    cost_stop_uk = 0.0

    # NNT cost proxy (cost per relapse prevented assuming maintain HR ~ 0.50)
    rux_cont_icer_us = cost_rux_cont_us * NNT_CONTINUE
    rux_cont_icer_uk = cost_rux_cont_uk * NNT_CONTINUE
    rux_2w_icer_us = cost_rux_2w_us * NNT_CONTINUE
    rux_2w_icer_uk = cost_rux_2w_uk * NNT_CONTINUE
    tac_2w_icer_us = cost_tac_2w_us * NNT_CONTINUE
    tac_2w_icer_uk = cost_tac_2w_uk * NNT_CONTINUE

    return [
        RegimenCost(
            profile=profile_name,
            regimen="Continuous Ruxolitinib 1.5% Cream",
            frequency="Twice daily (365 days)",
            annual_grams=round(ann_g_rux_cont, 1),
            tubes_needed=tubes_rux_us,
            cost_usd=round(cost_rux_cont_us, 2),
            cost_gbp=round(cost_rux_cont_uk, 2),
            usd_savings_vs_cont_rux=0.0,
            pct_savings_vs_cont_rux=0.0,
            cost_per_relapse_prevented_usd=round(rux_cont_icer_us, 2),
            cost_per_relapse_prevented_gbp=round(rux_cont_icer_uk, 2),
        ),
        RegimenCost(
            profile=profile_name,
            regimen="Twice-Weekly Ruxolitinib 1.5% Cream",
            frequency="Twice weekly (104 days)",
            annual_grams=round(ann_g_rux_2w, 1),
            tubes_needed=tubes_rux_2w_us,
            cost_usd=round(cost_rux_2w_us, 2),
            cost_gbp=round(cost_rux_2w_uk, 2),
            usd_savings_vs_cont_rux=round(cost_rux_cont_us - cost_rux_2w_us, 2),
            pct_savings_vs_cont_rux=round(
                (cost_rux_cont_us - cost_rux_2w_us) / cost_rux_cont_us * 100, 1
            ),
            cost_per_relapse_prevented_usd=round(rux_2w_icer_us, 2),
            cost_per_relapse_prevented_gbp=round(rux_2w_icer_uk, 2),
        ),
        RegimenCost(
            profile=profile_name,
            regimen="Twice-Weekly Tacrolimus 0.1% Ointment",
            frequency="Twice weekly (104 days)",
            annual_grams=round(ann_g_tac_2w, 1),
            tubes_needed=tubes_tac_2w_us,
            cost_usd=round(cost_tac_2w_us, 2),
            cost_gbp=round(cost_tac_2w_uk, 2),
            usd_savings_vs_cont_rux=round(cost_rux_cont_us - cost_tac_2w_us, 2),
            pct_savings_vs_cont_rux=round(
                (cost_rux_cont_us - cost_tac_2w_us) / cost_rux_cont_us * 100, 1
            ),
            cost_per_relapse_prevented_usd=round(tac_2w_icer_us, 2),
            cost_per_relapse_prevented_gbp=round(tac_2w_icer_uk, 2),
        ),
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
            cost_per_relapse_prevented_usd=0.0,
            cost_per_relapse_prevented_gbp=0.0,
        ),
    ]


def main() -> None:
    # Profile 1: Facial-only repigmentation (~1.0 g cream/day daily, 0.5 g/app twice weekly)
    facial = compute_costs("Facial-only responder", daily_rux_grams=1.0, twice_weekly_grams_per_application=0.5)

    # Profile 2: Face + limited neck/hand patches (~2.0 g/day daily, 1.0 g/app twice weekly)
    face_body = compute_costs("Face + limited body responder", daily_rux_grams=2.0, twice_weekly_grams_per_application=1.0)

    # Profile 3: Moderate body responder (~4.0 g/day daily, 2.0 g/app twice weekly)
    extensive = compute_costs("Moderate body responder", daily_rux_grams=4.0, twice_weekly_grams_per_application=2.0)

    all_results = {
        "title": "Vitiligo Maintenance Therapy Pharmacoeconomic Model",
        "assumptions": {
            "us_rux_60g_wac_usd": US_RUX_TUBE_COST,
            "us_tac_60g_retail_usd": US_TAC_TUBE_COST,
            "uk_rux_100g_nice_gbp": UK_RUX_TUBE_COST,
            "uk_tac_60g_tariff_gbp": UK_TAC_TUBE_COST,
            "one_year_relapse_rate_stopped": P_RELAPSE_STOP,
            "one_year_relapse_rate_maintained": P_RELAPSE_CONTINUE,
            "nnt_per_relapse_prevented": round(NNT_CONTINUE, 2),
        },
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
