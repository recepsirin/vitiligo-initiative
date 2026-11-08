"""Unit tests for knowledge graph enrichment and canonical pathway hierarchies."""

from __future__ import annotations

from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from vitiligo.graph.enrich_release import (
    CANONICAL_CELL_TYPES,
    CANONICAL_PATHWAYS,
    seed_canonical_pathways_and_cell_types,
)
from vitiligo.storage.models import EntityKind, GraphEntity, SQLModel


def test_canonical_pathway_definitions() -> None:
    assert len(CANONICAL_PATHWAYS) >= 9
    for p in CANONICAL_PATHWAYS:
        assert "name" in p
        assert len(p["genes"]) > 0
        assert "external_ids" in p

    assert len(CANONICAL_CELL_TYPES) >= 4
    for c in CANONICAL_CELL_TYPES:
        assert "name" in c
        assert len(c["markers"]) > 0


def test_seed_canonical_pathways_in_session() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Pre-seed a few targets
        t1 = GraphEntity(kind=EntityKind.TARGET, key="ifng", name="IFNG", aliases=["IFNG"])
        t2 = GraphEntity(kind=EntityKind.TARGET, key="jak1", name="JAK1", aliases=["JAK1"])
        t3 = GraphEntity(kind=EntityKind.TARGET, key="tyr", name="TYR", aliases=["TYR"])
        session.add(t1)
        session.add(t2)
        session.add(t3)
        session.commit()

        stats = seed_canonical_pathways_and_cell_types(session)
        assert stats["pathways"] >= 9
        assert stats["cell_types"] >= 4
        assert stats["hierarchy_edges"] >= 3
