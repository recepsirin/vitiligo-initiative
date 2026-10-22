"""Seal forecasts for trials found by the weekly watch, under v0.2, v0.4 and v0.5.

    python scripts/model/seal_new_trials.py

Targets come from the live ClinicalTrials.gov record through ``registry_targets``
(the primary endpoint), plus the registered T-VASI50 at the same week, as for
STOP-V1/V2. Each model is fitted exactly as in ``povorcitinib_check.py``, on the
data of its earlier sealed records. Leads that were not sealed, and why, are in
forecasts/watch-triage.md.

Writes forecasts/2026-10-22-new-trials/<model>/.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from povorcitinib_check import MODEL_LABELS, _fit

from vitiligo import __version__
from vitiligo.discovery.forecasts import (
    committed_code,
    forecast_target,
    registry_targets,
    write_forecast,
)
from vitiligo.models.jak_mbma import converged
from vitiligo.sources.ctgov import CTGovClient

OUT = Path("forecasts/2026-10-22-new-trials")
TRIALS = {
    "NCT07865312": (
        "Searched 2026-10-22: ClinicalTrials.gov (not yet recruiting; estimated start "
        "2026-11, primary completion 2028-05), and the web for the sponsor (Dermavon, CMS) "
        "and the trial: only the registry record and licensing news (CMS-Incyte agreement, "
        "2024-04-01). No results can exist yet. Disclosed: povorcitinib's global phase 3 "
        "F-VASI75 at week 52 (STOP-V1/V2, 18.9% vs 6.8% and 3.1%) is public and was read, "
        "but no model has it (curation/topline-pending.json); each model is fitted on the "
        "data hash of its earlier sealed records."
    ),
}


def main() -> None:
    code = committed_code()
    with CTGovClient() as client:
        studies = {trial: client.fetch_study(trial) for trial in TRIALS}
    targets = []
    for trial, study in studies.items():
        assert study is not None, trial
        protocol = study["protocolSection"]
        found, skips = registry_targets(
            [(trial, protocol["statusModule"]["overallStatus"], protocol)]
        )
        if skips or len(found) != 1:
            raise SystemExit(f"{trial}: expected one registry target, got {found} {skips}")
        primary = found[0]
        secondary = next(
            o["measure"]
            for o in protocol["outcomesModule"].get("secondaryOutcomes", [])
            if "T-VASI 50" in o["measure"] and f"Week {primary.week}" in o["measure"]
        )
        targets += [
            primary,
            replace(primary, instrument="T-VASI", threshold=50, registry_measure=secondary),
        ]
    for model, (label, prereg) in MODEL_LABELS.items():
        fitted = {instrument: _fit(model, instrument) for instrument in ("F-VASI", "T-VASI")}
        for target in targets:
            f = fitted[target.instrument]
            posterior = f["posterior"]
            if not converged(posterior):
                raise SystemExit(f"{model} {target.instrument} did not converge; nothing sealed")
            summary, p_active, p_control = forecast_target(posterior, target, routes=f["routes"])
            last_update = studies[target.trial]["protocolSection"]["statusModule"][
                "lastUpdatePostDateStruct"
            ]["date"]
            write_forecast(
                target, summary, p_active, p_control, OUT / model,
                context={
                    "engine_version": __version__,
                    "model": label,
                    "fit_settings": asdict(f["settings"]),
                    "first_try_diagnostics": f["first_try"],
                    "dataset": f["data"].summary(),
                    "data_sha256": f["data_sha256"],
                    "diagnostics": posterior.diagnostics,
                    "preregistration": prereg,
                    "registry_last_update": last_update,
                    "public_results_check": TRIALS[target.trial],
                    "code": code,
                    "disclaimer": "Research forecast; not medical advice. No results for this "
                    "trial existed when it was sealed.",
                },
            )  # fmt: skip
            a, c = summary["p_active"], summary["p_control"]
            print(f"sealed {model} {target.key}: active {100 * a['median']:.1f}% "
                  f"(80%: {100 * a['lo80']:.1f}-{100 * a['hi80']:.1f}) "
                  f"vs control {100 * c['median']:.1f}%", flush=True)  # fmt: skip


if __name__ == "__main__":
    main()
