"""Posted results of one ClinicalTrials.gov study, as compact JSON (for durability evidence).

    python scripts/durability/registry_results.py NCT04530344 docs/durability/data/nct04530344-results.json

Keeps every outcome measure as posted: title, definition, time frame, analysis
population, groups, denominators, values with their dispersion, and statistical
analyses. Nothing is recomputed.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vitiligo.sources.ctgov import CTGovClient


def compact(study: dict[str, Any]) -> dict[str, Any]:
    protocol = study["protocolSection"]
    results = study["resultsSection"]
    status = protocol["statusModule"]
    measures = []
    for o in results["outcomeMeasuresModule"]["outcomeMeasures"]:
        measures.append(
            {
                "type": o.get("type"),
                "title": o.get("title"),
                "description": o.get("description"),
                "time_frame": o.get("timeFrame"),
                "population": o.get("populationDescription"),
                "param_type": o.get("paramType"),
                "dispersion": o.get("dispersionType"),
                "unit": o.get("unitOfMeasure"),
                "groups": {g["id"]: g["title"] for g in o.get("groups", [])},
                "denominators": {
                    c["groupId"]: c["value"]
                    for d in o.get("denoms", [])
                    for c in d.get("counts", [])
                },
                "values": [
                    {
                        "class": c.get("title"),
                        "category": cat.get("title"),
                        "by_group": {
                            m["groupId"]: {
                                k: m.get(k)
                                for k in ("value", "lowerLimit", "upperLimit", "spread", "comment")
                                if m.get(k) is not None
                            }
                            for m in cat.get("measurements", [])
                        },
                    }
                    for c in o.get("classes", [])
                    for cat in c.get("categories", [])
                ],
                "analyses": [
                    {
                        k: a.get(k)
                        for k in (
                            "groupIds",
                            "statisticalMethod",
                            "pValue",
                            "paramType",
                            "paramValue",
                            "ciPctValue",
                            "ciLowerLimit",
                            "ciUpperLimit",
                        )
                        if a.get(k) is not None
                    }
                    for a in o.get("analyses", [])
                ],
            }
        )
    return {
        "nct_id": protocol["identificationModule"]["nctId"],
        "title": protocol["identificationModule"].get("officialTitle"),
        "results_first_posted": (status.get("resultsFirstPostDateStruct") or {}).get("date"),
        "last_update_posted": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
        "retrieved": datetime.now(UTC).date().isoformat(),
        "source": f"https://clinicaltrials.gov/study/{protocol['identificationModule']['nctId']}?tab=results",
        "arms": [
            {"label": a.get("label"), "description": a.get("description")}
            for a in protocol["armsInterventionsModule"]["armGroups"]
        ],
        "outcome_measures": measures,
    }


def main() -> None:
    nct_id, out = sys.argv[1], Path(sys.argv[2])
    with CTGovClient() as client:
        study = client.fetch_study(nct_id)
    if study is None or "resultsSection" not in study:
        raise SystemExit(f"{nct_id}: no posted results")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(compact(study), indent=1, ensure_ascii=False) + "\n")
    print(f"{nct_id}: {len(compact(study)['outcome_measures'])} outcome measures -> {out}")


if __name__ == "__main__":
    main()
