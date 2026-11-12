#!/usr/bin/env python3
"""Check the Hugging Face Space folder (exports/hf_space) before it is deployed.

    python scripts/generate_hf_space.py          # check
    python scripts/generate_hf_space.py --sync   # copy pipeline outputs in, then check

The Space is a static page: `index.html`, `style.css` and `app.js` draw every table
from the JSON files beside them. A missing file is a broken view, and a stale file
is a wrong number on a public page. Two checks; either one failing exits non-zero:

- **Every file the page loads is there and parses**: the JSON files `app.js` names,
  and every local file `index.html` links to.
- **No data file has drifted from the pipeline output it is a copy of.** `--sync`
  copies the pipeline outputs over the Space's copies first.

`data_pipeline.json` (exported from the corpus database) and `anatomical_model.json`
(specified by hand) have no pipeline output to compare against.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPACE = ROOT / "exports" / "hf_space"

# Space file -> the pipeline output it is a copy of.
SOURCES = {
    "gnn_pairwise_synergy_matrix.json": "exports/gnn_pairwise_synergy_matrix.json",
    "gnn_reranked_candidates.json": "exports/gnn_reranked_candidates.json",
    "reverse_target_screening.json": "exports/reverse_target_screening.json",
    "gnn_train_results.json": "exports/gnn_train_results.json",
    "maintenance-cost.json": "docs/durability/data/maintenance-cost.json",
    "trm_signature.json": "docs/durability/data/trm-signature-reference.json",
}


def loaded_files() -> list[str]:
    """Files the page needs: the data `app.js` fetches and what `index.html` links to."""
    script = (SPACE / "app.js").read_text(encoding="utf-8")
    table = re.search(r"\bFILES = \{(.*?)\}", script, re.S)
    if not table:
        raise SystemExit(
            "app.js: the FILES table was not found, so the data files cannot be listed"
        )
    data = re.findall(r"'([^']+\.json)'", table.group(1))
    page = (SPACE / "index.html").read_text(encoding="utf-8")
    linked = [
        ref for ref in re.findall(r'(?:href|src)="([^"#]+)"', page) if not re.match(r"[a-z]+:", ref)
    ]
    return sorted({"index.html", *data, *linked})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sync", action="store_true", help="copy pipeline outputs into the Space folder first"
    )
    args = parser.parse_args()

    problems: list[str] = []
    compared = 0
    for name, source in SOURCES.items():
        origin = ROOT / source
        if not origin.is_file():
            continue  # a fresh clone has no pipeline outputs to compare with
        if args.sync:
            shutil.copyfile(origin, SPACE / name)
        compared += 1
        if not (SPACE / name).is_file() or (SPACE / name).read_bytes() != origin.read_bytes():
            problems.append(f"{name} differs from {source} (run with --sync to copy it in)")

    files = loaded_files()
    for name in files:
        path = SPACE / name
        if not path.is_file():
            problems.append(f"{name} is missing")
        elif path.suffix == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except ValueError as error:
                problems.append(f"{name} is not valid JSON: {error}")

    if problems:
        sys.exit("\n".join(f"exports/hf_space: {p}" for p in problems))
    print(f"exports/hf_space: {len(files)} files present, {compared} match their pipeline output")


if __name__ == "__main__":
    main()
