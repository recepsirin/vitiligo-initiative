"""Tests for graph entity normalization and coercion."""

from __future__ import annotations

from vitiligo.graph.normalize import (
    VITILIGO_ENTITY_KEY,
    coerce_entity_kind,
    coerce_relation_kind,
    normalize_entity_key,
)
from vitiligo.storage.models import EntityKind, RelationKind


def test_normalize_entity_key() -> None:
    assert normalize_entity_key("Ruxolitinib") == "ruxolitinib"
    assert normalize_entity_key("  JAK-1  ") == "jak_1"
    assert VITILIGO_ENTITY_KEY == "vitiligo"


def test_coerce_entity_kind() -> None:
    assert coerce_entity_kind("drug") == EntityKind.DRUG
    assert coerce_entity_kind("gene") == EntityKind.TARGET
    assert coerce_entity_kind("unknown") is None


def test_coerce_relation_kind() -> None:
    assert coerce_relation_kind("treats") == RelationKind.TREATS
    assert coerce_relation_kind("associated-with") == RelationKind.ASSOCIATED_WITH
    assert coerce_relation_kind("nonsense") is None
