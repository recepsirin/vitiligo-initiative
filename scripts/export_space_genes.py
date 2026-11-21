"""Write the genes measured in vitiligo skin for the Space's gene explorer.

    python scripts/export_space_genes.py
    python scripts/export_space_genes.py --out exports/hf_space/genes.json

Reads the knowledge-graph release in ``data/release/knowledge-graph`` (the files
published as re-cep/vitiligo-knowledge-graph), the GWAS associations of the Space's
``data_pipeline.json`` and the relapse panel of its ``trm_signature.json``, and writes
the rows ``vitiligo.reports.space_genes`` defines, one gene per line. Run it after
``export_space_pipeline.py``.

Beside it goes ``genes.json.gz``, the same bytes gzipped, which the page reads.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

from vitiligo.reports.space_genes import gene_table

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "data" / "release" / "knowledge-graph"
SPACE = ROOT / "exports" / "hf_space"
DEFAULT_OUT = Path("exports/hf_space/genes.json")


def _lines(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def build() -> dict[str, Any]:
    gwas = json.loads((SPACE / "data_pipeline.json").read_text(encoding="utf-8"))["gwas"]
    panels = json.loads((SPACE / "trm_signature.json").read_text(encoding="utf-8"))["panels"]
    with (RELEASE / "evidence.jsonl").open(encoding="utf-8") as evidence:
        table = gene_table(
            _lines(RELEASE / "entities.jsonl"),
            _lines(RELEASE / "relations.jsonl"),
            (json.loads(line) for line in evidence),
            gwas,
            panels,
        )
    genes = table["genes"]
    cohorts = Counter(r["source"] for g in genes for r in g.get("expression", []))
    cells = Counter(c["cell"] for g in genes for c in g.get("cells", []))
    return {
        "title": "Genes measured in vitiligo skin",
        "description": (
            "Differential expression in lesional skin from public GEO cohorts, co-expression across "
            "105 skin biopsies, single-cell expression by skin cell type, GWAS associations, and the "
            "relapse signature's panel. This project's analysis of public data; an expression "
            "difference is an association, not a cause."
        ),
        "produced_by": "scripts/export_space_genes.py (vitiligo.reports.space_genes)",
        "source": "https://huggingface.co/datasets/re-cep/vitiligo-knowledge-graph",
        "counts": {
            "genes": len(genes),
            "expressed_differently": sum(1 for g in genes if g.get("expression")),
            "replicated": sum(1 for g in genes if g.get("agreeing", 0) >= 2),
            "with_cells": sum(1 for g in genes if g.get("cells")),
            "with_gwas": sum(1 for g in genes if g.get("gwas")),
            "panel": sum(1 for g in genes if g.get("panel")),
            "pairs": len(table["pairs"]),
            "paired_genes": len({i for a, b, _ in table["pairs"] for i in (a, b)}),
        },
        "cohorts": [{"source": s, "genes": n} for s, n in cohorts.most_common()],
        "cell_types": [{"cell": c, "genes": n} for c, n in cells.most_common()],
        "genes": genes,
        "pairs": table["pairs"],
    }


def serialize(payload: dict[str, Any]) -> bytes:
    """Compact JSON, one gene per line, so a change shows as a changed line."""
    head = {k: v for k, v in payload.items() if k not in ("genes", "pairs")}
    lines = [json.dumps(g, ensure_ascii=False, separators=(",", ":")) for g in payload["genes"]]
    pairs = json.dumps(payload["pairs"], separators=(",", ":"))
    text = (
        json.dumps(head, ensure_ascii=False, indent=1)[:-2]
        + ',\n "genes": [\n'
        + ",\n".join(lines)
        + '\n ],\n "pairs": '
        + pairs
        + "\n}\n"
    )
    if json.loads(text) != payload:  # the hand-assembled file must say exactly the payload
        raise SystemExit("serialized genes do not round-trip; not writing")
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
        f"{c['genes']:,} genes: {c['expressed_differently']:,} expressed differently "
        f"({c['replicated']} in two or more cohorts), {c['with_cells']} with cell types, "
        f"{c['with_gwas']} with GWAS hits, {c['panel']} in the relapse panel; "
        f"{c['pairs']:,} co-expression pairs"
    )
    print(f"wrote {out} ({len(data):,} bytes) and {twin} ({twin.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
