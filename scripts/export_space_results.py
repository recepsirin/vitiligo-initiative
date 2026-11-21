"""Write the results read from trial papers for the Space's trial explorer.

    python scripts/export_space_results.py
    python scripts/export_space_results.py --out exports/hf_space/trial_results.json

Reads ``curation/trial-results.jsonl`` and files its values under the trial explorer's
rows (``exports/hf_space/trials.json``, so run ``export_space_trials.py`` first), as
``vitiligo.reports.space_results`` defines. Every curated record is checked against
its sources first, as ``vitiligo trials verify-results`` does, and nothing is written
if one fails. Quotes are kept only where Europe PMC records the paper as CC BY or
CC0, read from the licence cache the knowledge-graph release fills.

Beside it goes ``trial_results.json.gz``, the same bytes gzipped, which the page reads.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlmodel import select

from vitiligo.reports.space_results import explorer_index, quote_rule, results_rows
from vitiligo.sources.raw_cache import load_payload
from vitiligo.storage import session_scope
from vitiligo.storage.models import Document
from vitiligo.trials.curated_results import Sources, records, verify

ROOT = Path(__file__).resolve().parent.parent
EXPLORER = ROOT / "exports" / "hf_space" / "trials.json"
DEFAULT_OUT = Path("exports/hf_space/trial_results.json")


def build() -> dict[str, Any]:
    explorer = json.loads(EXPLORER.read_text(encoding="utf-8"))["trials"]
    entries = list(records())
    with session_scope() as session:
        sources = Sources(session)
        failures = [f"{e['trial']}: {p}" for e in entries for p in verify(e, sources)]
        pmcid_of = {
            str(meta["pmid"]): str(meta["pmcid"])
            for meta in (d.raw_metadata or {} for d in session.exec(select(Document)).all())
            if meta.get("pmid") and meta.get("pmcid")
        }
    if failures:
        raise SystemExit(
            f"{len(failures)} curated values fail verification; not writing:\n"
            + "\n".join(failures[:20])
        )
    cached = load_payload("europepmc", "licences.json")
    licences: dict[str, str | None] = json.loads(cached) if cached else {}

    rows = results_rows(entries, explorer_index(explorer), quote_rule(licences, pmcid_of))
    trials = {t for r in rows for t in r["trials"]}
    return {
        "title": "Results read from trial papers",
        "description": (
            "Arm-level results extracted from the papers of vitiligo trials by one AI reader. Every "
            "number is checked by code against the sentence or table cell it was read from; a blind "
            "re-reading of 125 trials found 97% of its numbers in the first reading. Not audited by a "
            "person. Adverse events are left out. Quoted text appears only where the paper is CC BY or CC0."
        ),
        "produced_by": "scripts/export_space_results.py (vitiligo.reports.space_results)",
        "counts": {
            "results": len(rows),
            "trials": len(trials),
            "quoted": sum(1 for r in rows if "quote" in r),
            "pooled": sum(1 for r in rows if r.get("pooled")),
        },
        "types": dict(Counter(r.get("type") for r in rows).most_common()),
        "populations": dict(Counter(r.get("population") for r in rows).most_common()),
        "results": rows,
    }


def serialize(payload: dict[str, Any]) -> bytes:
    """Compact JSON with one result per line, so a change shows as a changed line."""
    head = {k: v for k, v in payload.items() if k != "results"}
    lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in payload["results"]]
    text = (
        json.dumps(head, ensure_ascii=False, indent=1)[:-2]
        + ',\n "results": [\n'
        + ",\n".join(lines)
        + "\n ]\n}\n"
    )
    if json.loads(text) != payload:  # the hand-assembled file must say exactly the payload
        raise SystemExit("serialized results do not round-trip; not writing")
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
        f"{c['results']:,} results for {c['trials']:,} explorer trials; {c['quoted']:,} quoted, {c['pooled']} from pooled analyses"
    )
    print(f"types: {payload['types']}")
    print(f"wrote {out} ({len(data):,} bytes) and {twin} ({twin.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
