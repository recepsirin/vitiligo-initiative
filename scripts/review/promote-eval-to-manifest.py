#!/usr/bin/env python3
"""Promote advisor-labeled retrieval eval rows into regression_expectations.json.

Reads a labeled ``exports/retrieval-eval.json`` (from ``run-eval-retrieval.sh``)
and proposes or merges retrieval confidence cases for hits rated highly by
advisors.

Usage:
    python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json
    python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "regression_expectations.json"
MIN_RELEVANCE = 4


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"file not found: {path}")
    return json.loads(path.read_text())


def _high_relevance_hits(run: dict[str, Any]) -> list[dict[str, Any]]:
    hits = [row for row in run.get("results", []) if int(row.get("advisor_relevance") or 0) >= MIN_RELEVANCE]
    if hits:
        return hits
    if int(run.get("advisor_relevance") or 0) >= MIN_RELEVANCE:
        return list(run.get("results", [])[:3])
    return []


def _title_keywords(title: str | None) -> list[str]:
    if not title:
        return ["vitiligo"]
    words = [word.strip(".,:;()[]") for word in title.split() if len(word) >= 4]
    return words[:3] or [title.split()[0]]


def _propose_case(run: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    query_id = str(run["id"])
    top = hits[0]
    must_include = sorted({str(hit["source_id"]) for hit in hits if hit.get("source_id")})
    min_score = max(0.78, round(float(top.get("score", 0.0)) - 0.04, 2))
    case: dict[str, Any] = {
        "id": query_id,
        "eval_query_id": query_id,
        "scenario": run.get("review_notes") or f"Promoted from advisor eval ({query_id})",
        "query": run["query"],
        "top_k": 10,
        "must_include_source_ids": must_include,
        "top_hit_title_must_contain_any": _title_keywords(top.get("title")),
        "min_top_score": min_score,
    }
    if top.get("source_id"):
        case["expected_top_source_id"] = str(top["source_id"])
    return case


def _merge_cases(manifest: dict[str, Any], proposals: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    retrieval = list(manifest.get("retrieval", []))
    existing_ids = {case["id"] for case in retrieval}
    added: list[str] = []
    for case in proposals:
        if case["id"] in existing_ids:
            continue
        retrieval.append(case)
        existing_ids.add(case["id"])
        added.append(case["id"])
    manifest["retrieval"] = retrieval
    return proposals, added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval_export", type=Path, help="Labeled retrieval eval JSON")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Regression manifest to update (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write merged cases to the manifest (default: dry-run only)",
    )
    parser.add_argument(
        "--min-relevance",
        type=int,
        default=MIN_RELEVANCE,
        help="Minimum advisor relevance (1-5) to promote a hit (default: 4)",
    )
    args = parser.parse_args()
    global MIN_RELEVANCE
    MIN_RELEVANCE = args.min_relevance

    export = _load_json(args.eval_export.resolve())
    manifest = _load_json(args.manifest.resolve())

    proposals: list[dict[str, Any]] = []
    skipped: list[str] = []
    for run in export.get("runs", []):
        hits = _high_relevance_hits(run)
        if not hits:
            skipped.append(str(run.get("id", "")))
            continue
        proposals.append(_propose_case(run, hits))

    if not proposals:
        print("No promotable runs found (label advisor_relevance >= threshold on results or runs).")
        return 0

    _, added = _merge_cases(manifest, proposals)
    print(json.dumps({"proposed": proposals, "would_add_ids": added, "skipped_unlabeled": skipped}, indent=2))

    if args.apply:
        if not added:
            print("Nothing new to add; manifest already contains these ids.", file=sys.stderr)
            return 0
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Updated {args.manifest} (+{len(added)} retrieval cases).", file=sys.stderr)
        print("Rebuild: python scripts/test/build_regression_db.py", file=sys.stderr)
        print("Verify:  pytest -m confidence", file=sys.stderr)
    else:
        print("Dry run only. Re-run with --apply to write manifest changes.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
