"""Tests for knowledge graph JSON export."""

from __future__ import annotations

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.graph.export import export_graph_snapshot
from vitiligo.graph.seed import seed_graph_from_structured_sources
from vitiligo.storage import Prior, PriorKind, PriorSourceKind, init_db, session_scope


def _reset_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "export_test.db"
    monkeypatch.setenv("VITILIGO_DB_PATH", str(db_path))
    cfg._settings = None
    dbmod._engine = None
    init_db()


def test_export_graph_snapshot(tmp_path, monkeypatch) -> None:
    _reset_db(tmp_path, monkeypatch)
    with session_scope() as session:
        session.add(
            Prior(
                source=PriorSourceKind.OPENTARGETS,
                kind=PriorKind.DRUG,
                source_id="CHEMBL1",
                disease_id="EFO_0004208",
                name="RUXOLITINIB",
                clinical_stage="APPROVAL",
            )
        )
    seed_graph_from_structured_sources()

    snapshot = export_graph_snapshot()
    assert snapshot["entities"]
    assert snapshot["edges"]
    assert "engine_version" in snapshot
    assert snapshot["stats"]["entities"] >= 2
    assert snapshot["edges"][0]["subject_name"]
    assert snapshot["edges"][0]["predicate"]
    assert "evidence" in snapshot["edges"][0]

    limited = export_graph_snapshot(edge_limit=1)
    assert len(limited["edges"]) == 1
    assert len(limited["entities"]) >= len(snapshot["entities"])
