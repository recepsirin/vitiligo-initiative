"""Corpus-only confidence tests: graph invariants on the full local DB."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from vitiligo.graph.query import get_neighbors, search_entities, summarize_graph
from vitiligo.storage import get_engine
from vitiligo.storage.models import EntityKind, GraphEntity

pytestmark = pytest.mark.corpus


class TestGraphConfidence:
    """Knowledge graph seed invariants from graph-spotcheck.sh."""

    def test_vitiligo_anchor_and_neighbor_density(self, require_local_corpus) -> None:
        summary = summarize_graph()
        counts = {r.label: r.count for r in summary["total"]}
        entities = counts.get("entities", 0)
        edges = counts.get("edges", 0)
        assert entities >= 100, f"too few entities ({entities})"
        assert edges >= 100, f"too few edges ({edges})"

        with Session(get_engine(), expire_on_commit=False) as session:
            vitiligo = session.exec(
                select(GraphEntity).where(
                    GraphEntity.kind == EntityKind.DISEASE,
                    GraphEntity.key == "vitiligo",
                )
            ).first()
        assert vitiligo is not None, "missing vitiligo disease anchor node"

        neighbors = get_neighbors("vitiligo", hops=1, limit=50)
        assert len(neighbors) >= 10, f"vitiligo has only {len(neighbors)} neighbor edges"

    def test_core_entities_and_predicates(self, require_local_corpus) -> None:
        assert search_entities("ruxolitinib", limit=5), "no ruxolitinib entity"
        assert search_entities("JAK1", limit=3), "no JAK1 target entity"

        by_predicate = {r.label: r.count for r in summarize_graph().get("by_predicate", [])}
        for predicate, minimum in (("treats", 50), ("associated_with", 50), ("investigates", 50)):
            count = by_predicate.get(predicate, 0)
            assert count >= minimum, f"too few '{predicate}' edges ({count})"
