"""Durability forecast 1: stopping ritlecitinib in Tranquillo LTE (NCT06163326).

    python scripts/durability/forecast_withdrawal.py

Computes the forecast exactly as fixed in docs/durability-forecast-preregistration.md,
from TRuE-V's posted results only (docs/durability/data/truev-reference.json),
and seals it: draws in a hashed .npz, summary in a SHA-256-sealed JSON record
carrying the git commit. Scoring, once results are public, uses
vitiligo.discovery.durability.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from vitiligo.discovery.forecasts import committed_code
from vitiligo.models.jak_mbma import freeze

REFERENCE = Path("docs/durability/data/truev-reference.json")
OUT = Path("forecasts/durability")
STEM = "tranquillo-lte-withdrawal"
SEED = 20261023
DRAWS = 20_000
Z80 = 1.2815516  # 90th percentile of the standard normal
TRANSFER_SD_LOGIT = 0.5
TRANSFER_SD_LOG_HR = 0.4


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def parameters(reference: dict) -> dict[str, float]:
    """The pre-registered distributions, from the reference numbers."""
    a = reference["loss_of_f_vasi90"]
    b = reference["relapse_below_f_vasi75"]
    s_a = a["one_year_retention_stopped_constant_hazard"]["point"]
    s_b = 1 - b["events_schoenfeld"]["share_stopped"]
    centre = (2 * _logit(s_a) + _logit(s_b)) / 3
    spread = max(abs(_logit(s_a) - centre), abs(_logit(s_b) - centre)) / Z80
    log_hr = (2 * math.log(a["hr"]) + math.log(b["hr"])) / 3
    se = (2 * a["se_log_hr"] + b["se_log_hr"]) / 3
    return {
        "analog_a_retention": s_a,
        "analog_b_retention": s_b,
        "logit_s_w_mean": centre,
        "logit_s_w_sd": math.sqrt(spread**2 + TRANSFER_SD_LOGIT**2),
        "log_hr_mean": log_hr,
        "log_hr_sd": math.sqrt(se**2 + TRANSFER_SD_LOG_HR**2),
    }


def _quantiles(x: np.ndarray) -> dict[str, float]:
    q = np.quantile(x, [0.1, 0.5, 0.9])
    return {"q10": float(q[0]), "median": float(q[1]), "q90": float(q[2])}


def main() -> None:
    code = committed_code()
    reference = json.loads(REFERENCE.read_text())
    params = parameters(reference)
    rng = np.random.default_rng(SEED)
    logit_s_w = rng.normal(params["logit_s_w_mean"], params["logit_s_w_sd"], DRAWS)
    log_hr = rng.normal(params["log_hr_mean"], params["log_hr_sd"], DRAWS)
    s_w = 1 / (1 + np.exp(-logit_s_w))
    s_c = s_w ** np.exp(log_hr)
    OUT.mkdir(parents=True, exist_ok=True)
    draws_path = OUT / f"{STEM}.npz"
    np.savez_compressed(draws_path, s_w=s_w, s_c=s_c, log_hr=log_hr)
    record = freeze(
        {
            "label": "Tranquillo LTE (NCT06163326): randomized withdrawal of ritlecitinib 50 mg, "
            "loss of response (< F-VASI75 and < T-VASI50) within 52 weeks",
            "trial": "NCT06163326",
            "preregistration": "docs/durability-forecast-preregistration.md",
            "reference": str(REFERENCE),
            "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
            "parameters": params,
            "forecast": {
                "retention_stopped_s_w": _quantiles(s_w),
                "retention_continued_s_c": _quantiles(s_c),
                "hazard_ratio_continue_vs_stop": _quantiles(np.exp(log_hr)),
                "p_most_lose_response_after_stopping": float(np.mean(s_w < 0.5)),
            },
            "draws_file": draws_path.name,
            "draws_sha256": hashlib.sha256(draws_path.read_bytes()).hexdigest(),
            "seed": SEED,
            "code": code,
            "public_results_check": (
                "Searched 2026-10-23: ClinicalTrials.gov (NCT06163326 active, not "
                "recruiting; no results), Europe PMC (titles and abstracts on ritlecitinib, "
                "vitiligo and withdrawal or relapse), and the Tranquillo protocol description "
                "(PMC13280265), and the web (Tranquillo LTE withdrawal, relapse, loss of "
                "response). No Tranquillo LTE results found; a 2024 'long-term trial' report on "
                "ritlecitinib concerns alopecia areata (ALLEGRO-LT)."
            ),
            "disclaimer": "Research forecast; not medical advice.",
        }
    )
    path = OUT / f"{STEM}.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record["forecast"], indent=1))


if __name__ == "__main__":
    main()
