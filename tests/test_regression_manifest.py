"""Validate regression manifest structure and eval-query linkage."""

from __future__ import annotations

import json
from pathlib import Path

EVAL_QUERIES = Path(__file__).resolve().parents[1] / "docs" / "eval-queries.json"
MANIFEST = Path(__file__).resolve().parent / "fixtures" / "regression_expectations.json"


def test_regression_manifest_structure() -> None:
    spec = json.loads(MANIFEST.read_text())
    assert spec["version"] == 1

    for case in spec["retrieval"]:
        assert case["id"]
        assert case["query"].strip()
        assert case["must_include_source_ids"]
        assert case["min_top_score"] > 0
        if expected_top := case.get("expected_top_source_id"):
            assert expected_top in case["must_include_source_ids"]

    for case in spec.get("retrieval_negative", []):
        assert case["query"].strip()
        assert int(case["top_k"]) >= int(case.get("top_n", 1))

    for case in spec["trials"]:
        assert case["must_include_source_ids"]
        assert int(case["limit"]) >= len(case["must_include_source_ids"])

    candidates = spec["candidates"]
    assert candidates["must_include_tokens"]
    assert candidates["rank1_token"] in candidates["must_include_tokens"]


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


def test_confidence_retrieval_cases_map_to_eval_queries() -> None:
    """Every automated retrieval case should trace to an expert eval query."""
    eval_ids = {q["id"] for q in json.loads(EVAL_QUERIES.read_text())["queries"]}
    manifest = json.loads(MANIFEST.read_text())
    missing: list[str] = []
    for case in manifest["retrieval"]:
        eval_id = case.get("eval_query_id", case["id"])
        if eval_id not in eval_ids:
            missing.append(f"{case['id']} -> {eval_id}")
    assert not missing, f"retrieval cases without eval-queries.json entry: {missing}"
