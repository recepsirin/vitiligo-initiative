"""Tests for deterministic graph seeding from priors and trials."""

from __future__ import annotations

from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.graph.query import get_neighbors, retrieve_graph_for_hypothesize, summarize_graph
from vitiligo.graph.seed import seed_graph_from_structured_sources
from vitiligo.storage import (
    Prior,
    PriorKind,
    PriorSourceKind,
    Trial,
    TrialSourceKind,
    init_db,
    session_scope,
)
from vitiligo.storage.models import EntityKind, GraphEdge, GraphEntity, RelationKind


def _reset_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "graph_test.db"
    monkeypatch.setenv("VITILIGO_DB_PATH", str(db_path))
    cfg._settings = None
    dbmod._engine = None
    init_db()


def test_seed_graph_from_priors_and_trials(tmp_path, monkeypatch) -> None:
    _reset_db(tmp_path, monkeypatch)

    with session_scope() as session:
        session.add(
            Prior(
                source=PriorSourceKind.OPENTARGETS,
                kind=PriorKind.DRUG,
                source_id="CHEMBL1789941",
                disease_id="EFO_0004208",
                name="RUXOLITINIB",
                clinical_stage="APPROVAL",
                mechanisms=[
                    {
                        "mechanism": "JAK1 inhibitor",
                        "action_type": "INHIBITOR",
                        "targets": [{"id": "ENSG00000162434", "symbol": "JAK1"}],
                    }
                ],
            )
        )
        session.add(
            Prior(
                source=PriorSourceKind.OPENTARGETS,
                kind=PriorKind.TARGET,
                source_id="ENSG00000162434",
                disease_id="EFO_0004208",
                name="JAK1",
                score=0.72,
            )
        )
        session.add(
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT07533019",
                brief_title="LY4005130 in vitiligo",
                status="RECRUITING",
                phases=["PHASE2"],
                conditions=["Vitiligo"],
                interventions=[{"type": "DRUG", "name": "LY4005130", "other_names": []}],
            )
        )

    stats = seed_graph_from_structured_sources()
    assert stats.entities >= 5
    assert stats.edges_inserted >= 4

    summary = summarize_graph()
    entity_count = next(r.count for r in summary["total"] if r.label == "entities")
    edge_count = next(r.count for r in summary["total"] if r.label == "edges")
    assert entity_count >= 5
    assert edge_count >= 4

    vitiligo_neighbors = get_neighbors("vitiligo", hops=1, limit=20)
    assert any("ruxolitinib" in e.subject_name.lower() or "ruxolitinib" in e.object_name.lower() for e in vitiligo_neighbors)

    graph_hits = retrieve_graph_for_hypothesize("stop spread vitiligo")
    assert graph_hits
    assert any(e.predicate in {"treats", "associated_with", "investigates"} for e in graph_hits)

    with session_scope() as session:
        vitiligo = session.exec(
            select(GraphEntity).where(
                GraphEntity.kind == EntityKind.DISEASE,
                GraphEntity.key == "vitiligo",
            )
        ).first()
        assert vitiligo is not None
        treats = session.exec(
            select(GraphEdge).where(GraphEdge.predicate == RelationKind.TREATS)
        ).all()
        assert len(treats) >= 2
