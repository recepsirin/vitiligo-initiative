"""Tests for deterministic graph seeding from priors and trials."""

from __future__ import annotations

import json

from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.graph.query import get_neighbors, summarize_graph
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
    assert any(
        "ruxolitinib" in e.subject_name.lower() or "ruxolitinib" in e.object_name.lower()
        for e in vitiligo_neighbors
    )

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


def test_seed_keeps_only_vitiligo_trials(tmp_path, monkeypatch) -> None:
    """A trial held for its drug is not a vitiligo trial, and its drug is not a vitiligo treatment.

    The graph starts as an earlier seed left it, with a myelofibrosis trial
    investigating vitiligo and ruxolitinib treating vitiligo on its word alone.
    """
    _reset_db(tmp_path, monkeypatch)
    from vitiligo.graph.store import upsert_edge, upsert_entity

    with session_scope() as session:
        session.add(
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT01423604",
                brief_title="Ruxolitinib in myelofibrosis",
                conditions=["Myelofibrosis"],
                interventions=[{"type": "DRUG", "name": "Ruxolitinib", "other_names": []}],
            )
        )
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="vitiligo")
        trial = upsert_entity(session, kind=EntityKind.TRIAL, name="NCT01423604")
        drug = upsert_entity(session, kind=EntityKind.DRUG, name="Ruxolitinib")
        cited = {"source_type": "trial", "source_id": "ctgov:NCT01423604"}
        upsert_edge(
            session,
            subject=trial,
            predicate=RelationKind.INVESTIGATES,
            obj=vitiligo,
            confidence=0.78,
            extraction_method="structured",
            evidence=cited,
        )
        upsert_edge(
            session,
            subject=drug,
            predicate=RelationKind.TREATS,
            obj=vitiligo,
            confidence=0.68,
            extraction_method="structured",
            evidence=cited,
        )

    stats = seed_graph_from_structured_sources()

    with session_scope() as session:
        trials = session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.TRIAL)).all()
        cited_anywhere = [
            e
            for edge in session.exec(select(GraphEdge)).all()
            for e in edge.evidence or []
            if e.get("source_id") == "ctgov:NCT01423604"
        ]
    assert trials == []
    assert cited_anywhere == []
    assert stats.edges_removed == 2


def test_seed_reads_a_paper_trials_arms_from_the_curation(tmp_path, monkeypatch) -> None:
    """A trial known only from its paper gets its arms from the curation; its placebo treats nothing.

    The graph starts with placebo treating vitiligo, as an earlier seed left it.
    """
    _reset_db(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "curation").mkdir()
    arms = [
        {
            "id": "A",
            "role": "active",
            "components": [{"agent": "5-fluorouracil"}],
            "procedure": "microneedling",
            "phototherapy": "NBUVB twice weekly",
        },
        {"id": "B", "role": "control", "components": [{"agent": "placebo"}]},
    ]
    record = {"trial": "pmid:41781839", "arms": arms}
    (tmp_path / "curation" / "trial-results.jsonl").write_text(json.dumps(record) + "\n")
    from vitiligo.graph.store import upsert_edge, upsert_entity

    with session_scope() as session:
        session.add(
            Trial(
                source=TrialSourceKind.PUBLICATION,
                source_id="41781839",
                brief_title="Topical 5-fluorouracil with microneedling in stable vitiligo",
                conditions=["Vitiligo"],
            )
        )
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="vitiligo")
        placebo = upsert_entity(session, kind=EntityKind.DRUG, name="placebo")
        upsert_edge(
            session,
            subject=placebo,
            predicate=RelationKind.TREATS,
            obj=vitiligo,
            confidence=0.68,
            extraction_method="structured",
            evidence={"source_type": "trial", "source_id": "publication:41781839"},
        )

    seed_graph_from_structured_sources()
    rerun = seed_graph_from_structured_sources()

    with session_scope() as session:
        names = {e.id: e.name for e in session.exec(select(GraphEntity)).all()}
        edges = session.exec(select(GraphEdge)).all()
        tested = {names[e.subject_id] for e in edges if e.predicate == RelationKind.TESTED_IN}
        treats = {names[e.subject_id] for e in edges if e.predicate == RelationKind.TREATS}
    assert tested == {"5-fluorouracil", "microneedling", "NB-UVB", "placebo"}
    assert treats == {"5-fluorouracil", "microneedling", "NB-UVB"}
    assert (rerun.edges_inserted, rerun.edges_removed) == (0, 0)  # a rerun changes nothing
