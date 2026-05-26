"""Sanity checks for the retrieval evaluation query set."""

from __future__ import annotations

import json
from pathlib import Path

EVAL_QUERIES = Path(__file__).resolve().parents[1] / "docs" / "eval-queries.json"


def test_eval_queries_file_is_valid() -> None:
    spec = json.loads(EVAL_QUERIES.read_text())
    assert spec["version"] == 1
    queries = spec["queries"]
    assert len(queries) >= 15
    ids = [q["id"] for q in queries]
    assert len(ids) == len(set(ids))
    for q in queries:
        assert q["query"].strip()
        assert q.get("category")
        assert q.get("review_notes")
