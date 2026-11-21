"""Write the Space's outcome arms, GWAS associations and NIH awards.

    python scripts/export_space_pipeline.py
    python scripts/export_space_pipeline.py --out exports/hf_space/data_pipeline.json

Reads ``curation/topline-results.json`` and the corpus's ``genetic_associations``
and ``research_projects`` tables, and writes them as the rows
``vitiligo.reports.space_tables`` defines, one row per line. The file replaces one
that was assembled by hand; that module's docstring says what was wrong with it.

Beside it goes ``data_pipeline.json.gz``, the same bytes gzipped, for the same
reason as the trials: the Space's host serves files uncompressed, and the page
reads this file on its first view. The gzip header carries no timestamp, so an
unchanged corpus writes identical bytes.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from vitiligo.reports.space_tables import association_rows, award_rows, outcome_row
from vitiligo.storage import GeneticAssociation, ResearchProject, get_engine

ROOT = Path(__file__).resolve().parent.parent
TOPLINE = ROOT / "curation" / "topline-results.json"
DEFAULT_OUT = ROOT / "exports" / "hf_space" / "data_pipeline.json"
TABLES = ("curated_outcomes", "gwas", "nih")


def build() -> dict[str, Any]:
    topline = json.loads(TOPLINE.read_text(encoding="utf-8"))
    with Session(get_engine(), expire_on_commit=False) as session:
        associations = list(session.exec(select(GeneticAssociation)))
        projects = list(session.exec(select(ResearchProject)))

    outcomes = [outcome_row(r) for r in topline["results"]]
    gwas = association_rows(associations)
    nih = award_rows(projects)
    return {
        "title": "Outcome arms, GWAS associations and NIH awards",
        "description": (
            "Phase 3 topline response rates from press releases and conference reports "
            "(curation/topline-results.json); every GWAS Catalog association for vitiligo; "
            "and NIH RePORTER award records for projects about vitiligo, one per fiscal year."
        ),
        "produced_by": "scripts/export_space_pipeline.py (vitiligo.reports.space_tables)",
        "counts": {
            "outcome_arms": len(outcomes),
            "outcome_trials": len({o["trial"] for o in outcomes}),
            "associations": len(gwas),
            "association_studies": len({g["study"] for g in gwas}),
            "awards": len(nih),
            "award_projects": len({a.get("project") or a["award"] for a in nih}),
            "awards_left_out_as_passing_mentions": len(projects) - len(nih),
        },
        "curated_outcomes": outcomes,
        "gwas": gwas,
        "nih": nih,
    }


def serialize(payload: dict[str, Any]) -> bytes:
    """Compact JSON with one row per line, so a change shows as a changed line."""
    head = {k: v for k, v in payload.items() if k not in TABLES}
    parts = [json.dumps(head, ensure_ascii=False, indent=1)[:-2]]
    for name in TABLES:
        rows = ",\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in payload[name]
        )
        parts.append(f' "{name}": [\n{rows}\n ]')
    text = ",\n".join(parts) + "\n}\n"
    if json.loads(text) != payload:  # the hand-assembled file must say exactly the payload
        raise SystemExit("serialized tables do not round-trip; not writing")
    return text.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"default: {DEFAULT_OUT}")
    args = parser.parse_args()

    payload = build()
    data = serialize(payload)
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    twin = out.with_name(out.name + ".gz")
    twin.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))

    c = payload["counts"]
    print(
        f"{c['outcome_arms']} outcome arms from {c['outcome_trials']} trials; "
        f"{c['associations']} associations from {c['association_studies']} studies; "
        f"{c['awards']} award records for {c['award_projects']} projects "
        f"({c['awards_left_out_as_passing_mentions']} left out as passing mentions)"
    )
    print(f"wrote {out} ({len(data):,} bytes) and {twin} ({twin.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
