"""Write the Space's trial explorer data from the corpus.

    python scripts/export_space_trials.py
    python scripts/export_space_trials.py --out exports/hf_space/trials.json

Reads the ``trials`` table and writes one row per vitiligo trial, registered or
only published, as ``vitiligo.trials.explorer`` defines them. The file opens
with the counts and the per-registry and per-group tallies the page quotes, so
the page computes none of them; the rows follow, one per line.

Beside it goes ``trials.json.gz``, the same bytes gzipped. The Space's host
serves files uncompressed, so the page reads the 1.3 MB of trials through the
gzip copy (about a fifth of the size) and falls back to the plain file. The gzip
header carries no timestamp, so an unchanged corpus writes identical bytes.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from vitiligo.storage import Trial, get_engine
from vitiligo.trials.explorer import (
    OBSERVATIONAL,
    PUBLISHED,
    TREATMENT_GROUPS,
    explorer_rows,
    in_explorer,
)
from vitiligo.trials.relevance import in_vitiligo_corpus

DEFAULT_OUT = Path("exports/hf_space/trials.json")


def build() -> dict[str, Any]:
    with Session(get_engine(), expire_on_commit=False) as session:
        trials = list(session.exec(select(Trial)))
    corpus = [t for t in trials if in_vitiligo_corpus(t)]
    rows, merged = explorer_rows(trials)

    registries = Counter(r["registry"] for r in rows)
    groups = Counter(g for r in rows for g in r.get("groups", []))
    registered = sum(n for name, n in registries.items() if name != PUBLISHED)
    newest = max(t.retrieved_at for t in corpus if in_explorer(t))
    return {
        "title": "Vitiligo trials",
        "description": (
            "One row per vitiligo trial in the corpus: registered trials, one row per trial "
            "across registries, and trials known only from a paper. Treatment groups are read "
            "from intervention names and titles."
        ),
        "produced_by": "scripts/export_space_trials.py (vitiligo.trials.explorer)",
        "corpus_retrieved_through": newest.date().isoformat(),
        "counts": {
            "trials": len(rows),
            "registered": registered,
            "published_only": registries.get(PUBLISHED, 0),
            "registries": len([name for name in registries if name != PUBLISHED]),
            "merged_copies": merged,
            "excluded_not_naming_vitiligo": sum(1 for t in corpus if not in_explorer(t)),
        },
        "registries": [{"name": n, "trials": c} for n, c in registries.most_common()],
        "groups": [
            {"name": g, "trials": groups[g]}
            for g in [*TREATMENT_GROUPS, OBSERVATIONAL]
            if groups[g]
        ],
        "trials": rows,
    }


def serialize(payload: dict[str, Any]) -> bytes:
    """Compact JSON with one trial per line, so a change shows as a changed line."""
    head = {k: v for k, v in payload.items() if k != "trials"}
    lines = [
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in payload["trials"]
    ]
    body = json.dumps(head, ensure_ascii=False, indent=1)[:-2]
    text = body + ',\n "trials": [\n' + ",\n".join(lines) + "\n ]\n}\n"
    if json.loads(text) != payload:  # the hand-assembled file must say exactly the payload
        raise SystemExit("serialized trials do not round-trip; not writing")
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

    counts = payload["counts"]
    print(
        f"{counts['trials']:,} trials ({counts['registered']:,} registered in "
        f"{counts['registries']} registries, {counts['published_only']:,} published only); "
        f"{counts['merged_copies']} copies merged, {counts['excluded_not_naming_vitiligo']} "
        f"records excluded"
    )
    print(f"wrote {out} ({len(data):,} bytes) and {twin} ({twin.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
