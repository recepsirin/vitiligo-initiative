"""In-sample reference for the T_RM relapse score, from the sealed implementation.

    python scripts/durability/trm_reference.py

Reads the six GSE203262 patient archives (data/geo/GSE203262). For each patient's
non-lesional and lesional epidermis it takes the mean expression of every
signature gene across cells (a pseudobulk) and scores it with
`vitiligo.models.trm_score.compute_trm_score`.

Two checks run before anything is written, and either one failing stops the script:

- **Each score equals `score_patient_archive`'s** for the same archive, so the
  expression values recorded here reproduce the implementation's own numbers.
- **The seal of `trm-il15-relapse` still verifies** (curation/mechanisms.json), so
  the test copied into the file is the sealed one.

Writes docs/durability/data/trm-signature-reference.json: the gene panels, the
sealed test, and per sample the cell count, the expression of each panel gene and
the score. A reader can recompute every score from the expression values.
"""

from __future__ import annotations

import inspect
import json
import tarfile
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import mmread

from vitiligo.mechanisms import load, seal_hash, to_dict
from vitiligo.models.trm_score import (
    CIRCULATING_EGRESS_GENES,
    HOUSEKEEPING_GENES,
    TRM_CORE_GENES,
    compute_trm_score,
    score_patient_archive,
)

ARCHIVES = Path("data/geo/GSE203262")
OUT = Path("docs/durability/data/trm-signature-reference.json")
HYPOTHESIS = "trm-il15-relapse"
PANEL = TRM_CORE_GENES + CIRCULATING_EGRESS_GENES + HOUSEKEEPING_GENES
# Barcode suffixes, from the series' !Sample_description (see the pre-registration, section 2).
TISSUES = {"nonlesional": "-1", "lesional": "-2"}


def _pseudobulks(tar_path: Path) -> dict[str, dict[str, Any]]:
    """Mean expression of each panel gene per tissue, read as `score_patient_archive` reads it."""
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()

        def text(name: str) -> list[str]:
            member = next(m for m in members if name in m.name)
            return tar.extractfile(member).read().decode("utf-8").strip().split("\n")  # type: ignore[union-attr]

        barcodes = text("barcodes.tsv")
        symbols = [
            (row[1] if len(row) > 1 else row[0])
            for row in (g.split("\t") for g in text("genes.tsv"))
        ]
        matrix = mmread(tar.extractfile(next(m for m in members if "matrix.mtx" in m.name))).tocsr()
    if matrix.shape[0] != len(symbols):
        matrix = matrix.T
    index = {s.upper(): i for i, s in enumerate(symbols)}

    out: dict[str, dict[str, Any]] = {}
    for tissue, suffix in TISSUES.items():
        mask = np.array([b.endswith(suffix) for b in barcodes])
        expression = {
            g: float(matrix[index[g], :].toarray().flatten()[mask].mean())
            if mask.sum() > 0
            else 0.0
            for g in PANEL
            if g in index
        }
        out[tissue] = {"cells": int(mask.sum()), "expression": expression}
    return out


def _sealed_test() -> dict[str, Any]:
    mechanism = next(m for m in load() if m.id == HYPOTHESIS)
    if not mechanism.seal or seal_hash(mechanism) != mechanism.seal["sha256"]:
        raise SystemExit(f"{HYPOTHESIS}: the seal no longer matches the record; not writing {OUT}")
    record = to_dict(mechanism)
    return {key: record[key] for key in ("id", "title", "status", "test", "seal")}


def main() -> None:
    archives = sorted(ARCHIVES.glob("GSE203262_Pt*_processed.tar.gz"))
    if not archives:
        raise SystemExit(f"no patient archives under {ARCHIVES}")

    samples: list[dict[str, Any]] = []
    lesional_higher = 0
    for tar_path in archives:
        patient = tar_path.name.split("_")[1]
        implementation = score_patient_archive(tar_path)
        scores: dict[str, float] = {}
        for tissue, bulk in _pseudobulks(tar_path).items():
            result = compute_trm_score(bulk["expression"])
            expected = implementation["nl_score" if tissue == "nonlesional" else "ls_score"]
            if abs(result.normalized_score - expected) > 1e-12:
                raise SystemExit(
                    f"{patient} {tissue}: {result.normalized_score} here, "
                    f"{expected} from score_patient_archive; not writing {OUT}"
                )
            scores[tissue] = result.normalized_score
            samples.append(
                {
                    "patient": patient,
                    "tissue": tissue,
                    "cells": bulk["cells"],
                    "expression": bulk["expression"],
                    "raw_score": result.raw_score,
                    "score": result.normalized_score,
                }
            )
        lesional_higher += scores["lesional"] > scores["nonlesional"]

    out = {
        "hypothesis": _sealed_test(),
        "specification": "docs/durability/trm-signature-preregistration.md",
        "implementation": "src/vitiligo/models/trm_score.py",
        "panels": {
            "core": list(TRM_CORE_GENES),
            "circulating": list(CIRCULATING_EGRESS_GENES),
            "housekeeping": list(HOUSEKEEPING_GENES),
        },
        "epsilon": inspect.signature(compute_trm_score).parameters["epsilon"].default,
        "reference": {
            "dataset": "GSE203262",
            "unit": "mean expression per cell, by patient and tissue (pseudobulk)",
            "patients": len(archives),
            "cells": sum(s["cells"] for s in samples),
            "lesional_higher": lesional_higher,
            "samples": samples,
        },
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    for s in samples:
        print(f"{s['patient']} {s['tissue']:<11} cells={s['cells']:<5} score={s['score']:.4f}")
    print(f"lesional higher in {lesional_higher} of {len(archives)} patients; wrote {OUT}")


if __name__ == "__main__":
    main()
