"""Refit each sealed model with the committed code and compare with its sealed draws.

    python scripts/model/reproduce_sealed.py forecasts/reproducibility-2026-10-21.json

The 2026-10-14 forecasts were sealed before their code was committed. Same
data, seed and settings; quantiles (10/50/90%) of the active and control
draws, sealed vs now, in percent.
"""

import json
import sys
from dataclasses import fields as dc_fields
from pathlib import Path

import numpy as np

from vitiligo.cli import _model_inputs, model_inputs_v03
from vitiligo.discovery.forecasts import ForecastTarget, forecast_target
from vitiligo.discovery.ledger import verify_seal
from vitiligo.models.jak_mbma import FitSettings, build_dataset, fit

MODELS = {
    "v0.2": (Path("forecasts/2026-10-14-auto"), FitSettings()),
    "v0.4": (Path("forecasts/v0.4/forecasts"), FitSettings(version="v0.3", target_accept=0.995)),
    "v0.5": (Path("forecasts/v0.5/forecasts"), FitSettings(version="v0.5", target_accept=0.995)),
}
names = {f.name for f in dc_fields(ForecastTarget)}


def q(x):
    return [round(100 * float(v), 1) for v in np.quantile(x, [0.1, 0.5, 0.9])]


out = {}
for model, (directory, settings) in MODELS.items():
    if model == "v0.2":
        rows, routes = _model_inputs()
        phase3 = None
    else:
        rows, routes, phase3 = model_inputs_v03(with_toplines=True)
    for instrument in ("F-VASI", "T-VASI"):
        data = (
            build_dataset(rows, instrument, agent_routes=routes)
            if phase3 is None
            else build_dataset(rows, instrument, agent_routes=routes, trial_phase3=phase3)
        )
        posterior = fit(data, settings)
        print(model, instrument, posterior.diagnostics, flush=True)
        for path in sorted(directory.glob("*.json")):
            record = json.loads(path.read_text())
            t = record.get("target")
            if not t or t["instrument"] != instrument or not verify_seal(record):
                continue
            kwargs = {k: v for k, v in t.items() if k in names}
            kwargs["assumptions"] = tuple(kwargs.get("assumptions") or ())
            _, p_a, p_c = forecast_target(posterior, ForecastTarget(**kwargs), routes=routes)
            with np.load(path.parent / record["draws_file"]) as d:
                s_a, s_c = d["p_active"], d["p_control"]
            key = f"{model} {path.stem}"
            out[key] = {
                "sealed_active": q(s_a), "now_active": q(p_a),
                "sealed_control": q(s_c), "now_control": q(p_c),
            }  # fmt: skip
            print(key[:70], out[key], flush=True)
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
