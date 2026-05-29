"""Shared assertions for manifest-driven graph confidence cases."""

from __future__ import annotations

from typing import Any


def _entity_keys(entities: list[dict[str, Any]]) -> set[str]:
    return {str(row["key"]).lower() for row in entities}


def _neighbor_identifiers(results: list[dict[str, Any]]) -> set[str]:
    """Normalize neighbor rows to lowercase keys/names for manifest matching."""
    ids: set[str] = set()
    for row in results:
        for field in ("subject_key", "object_key", "subject_name", "object_name"):
            value = row.get(field) or ""
            if value:
                ids.add(str(value).strip().lower())
    return ids


def assert_graph_search_expectations(case: dict[str, Any], results: list[dict[str, Any]]) -> None:
    case_id = case["id"]
    assert results, f"{case_id}: no graph search results for {case['search_q']!r}"
    returned = _entity_keys(results)
    missing = {k.lower() for k in case["must_include_keys"]} - returned
    assert not missing, (
        f"{case_id} ({case['scenario']}): missing entity keys {sorted(missing)}. "
        f"Got: {sorted(returned)[:10]}"
    )


def assert_graph_neighbors_expectations(
    case: dict[str, Any], results: list[dict[str, Any]]
) -> None:
    case_id = case["id"]
    min_count = int(case.get("min_neighbor_count", 1))
    assert len(results) >= min_count, (
        f"{case_id}: expected >= {min_count} neighbors, got {len(results)}"
    )
    found = _neighbor_identifiers(results)
    missing = {k.lower() for k in case["must_include_neighbor_keys"]} - found
    assert not missing, (
        f"{case_id} ({case['scenario']}): missing neighbor ids {sorted(missing)}. "
        f"Sample: {sorted(found)[:12]}"
    )


def assert_graph_export_expectations(case: dict[str, Any], payload: dict[str, Any]) -> None:
    case_id = case["id"]
    entities = payload.get("entities") or []
    edges = payload.get("edges") or []
    assert len(entities) >= int(case["min_entities"]), (
        f"{case_id}: expected >= {case['min_entities']} entities, got {len(entities)}"
    )
    assert len(edges) >= int(case["min_edges"]), (
        f"{case_id}: expected >= {case['min_edges']} edges, got {len(edges)}"
    )
    keys = _entity_keys(entities)
    missing = {k.lower() for k in case["must_include_entity_keys"]} - keys
    assert not missing, f"{case_id}: export missing entity keys {sorted(missing)}"
