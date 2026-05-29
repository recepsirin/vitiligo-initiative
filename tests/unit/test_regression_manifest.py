"""Validate regression manifest structure and eval-query linkage."""

from __future__ import annotations

import json

from tests.helpers.paths import FIXTURES_DIR, PROJECT_ROOT

EVAL_QUERIES = PROJECT_ROOT / "docs" / "eval-queries.json"
MANIFEST = FIXTURES_DIR / "regression_expectations.json"


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
        if case.get("must_not_include_source_ids"):
            assert case["top_n"] >= 1

    for intent_case in spec.get("candidate_intents", {}).get("intents", []):
        assert intent_case["id"]
        assert intent_case["must_include_tokens"]
        assert intent_case["rank1_token"] in intent_case["must_include_tokens"]

    for case in spec["trials"]:
        assert case["must_include_source_ids"]
        assert int(case["limit"]) >= len(case["must_include_source_ids"])

    candidates = spec["candidates"]
    assert candidates["must_include_tokens"]
    assert candidates["rank1_token"] in candidates["must_include_tokens"]

    for case in spec.get("ask", []):
        assert case["id"]
        assert case["question"].strip()
        assert case["must_include_citation_source_ids"]
        assert int(case["top_k"]) >= len(case["must_include_citation_source_ids"])

    for case in spec.get("hypothesize", []):
        assert case["id"]
        assert case["intent"].strip()
        assert case["must_include_citation_source_ids"]
        assert case["must_include_candidate_names"]
        assert int(case["top_k"]) >= 1

    graph_cases = spec.get("graph", [])
    assert len(graph_cases) >= 3, "graph confidence section must not be empty"

    for case in graph_cases:
        assert case["id"]
        assert case["scenario"]
        if "search_q" in case:
            assert case["search_q"].strip()
            assert case["must_include_keys"]
        if "neighbors_name" in case:
            assert case["neighbors_name"].strip()
            assert case["must_include_neighbor_keys"]
        if "min_entities" in case:
            assert int(case["min_entities"]) >= 1
            assert int(case["min_edges"]) >= 1
            assert case["must_include_entity_keys"]


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
    """Every eval query must have a matching automated retrieval case."""
    eval_ids = {q["id"] for q in json.loads(EVAL_QUERIES.read_text())["queries"]}
    manifest = json.loads(MANIFEST.read_text())
    covered = {case.get("eval_query_id", case["id"]) for case in manifest["retrieval"]}
    missing = sorted(eval_ids - covered)
    assert not missing, f"eval queries without retrieval confidence case: {missing}"


def test_confidence_retrieval_covers_all_eval_queries() -> None:
    eval_ids = {q["id"] for q in json.loads(EVAL_QUERIES.read_text())["queries"]}
    manifest = json.loads(MANIFEST.read_text())
    assert len(manifest["retrieval"]) == len(eval_ids)
