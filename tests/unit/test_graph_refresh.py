"""The graph's re-runnable refreshes: each brings one source's layer to what it says now."""

from __future__ import annotations

import pytest
from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.graph.enrich_release as enrich
import vitiligo.storage.db as dbmod
from vitiligo.graph.seed import prune_trial_interventions, refresh_trial_records
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.storage import Trial, TrialSourceKind, init_db, session_scope
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity, RelationKind


@pytest.fixture
def graph_db(tmp_path, monkeypatch):
    monkeypatch.setenv("VITILIGO_DB_PATH", str(tmp_path / "graph.db"))
    cfg._settings = None
    dbmod._engine = None
    init_db()


def _edge(session, subject, predicate, obj, evidence, *, method, claim, level):
    made, _ = upsert_edge(
        session,
        subject=subject,
        predicate=predicate,
        obj=obj,
        confidence=0.9,
        extraction_method=method,
        evidence=evidence,
        claim=claim,
        causal_level=level,
    )
    return made.id


def test_a_trials_row_takes_its_records_current_status_and_phases(graph_db) -> None:
    with session_scope() as session:
        session.add(
            Trial(
                source=TrialSourceKind.ICTRP,
                source_id="CTIS2025-524709-34-00",
                brief_title="HBO and NB-UVB",
                status="NOT_RECRUITING",
                phases=["PHASE2"],
            )
        )
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="vitiligo")
        trial = upsert_entity(session, kind=EntityKind.TRIAL, name="CTIS2025-524709-34-00")
        row = {
            "source_type": "trial",
            "source_id": "ictrp:CTIS2025-524709-34-00",
            "status": "RECRUITING",
            "phases": ["PHASE4"],
        }
        _edge(
            session,
            trial,
            RelationKind.INVESTIGATES,
            vitiligo,
            row,
            method="structured",
            claim=ClaimKind.ASSERTED,
            level=None,
        )
        assert refresh_trial_records(session) == 1
        held = session.exec(select(GraphEdge)).one().evidence
    assert held == [{**row, "status": "NOT_RECRUITING", "phases": ["PHASE2"]}]


def test_only_curated_annotations_nothing_measured_become_asserted(graph_db) -> None:
    with session_scope() as session:
        gene = upsert_entity(session, kind=EntityKind.TARGET, name="TYR")
        pathway = upsert_entity(session, kind=EntityKind.PATHWAY, name="Melanin biosynthesis")
        cell = upsert_entity(session, kind=EntityKind.CELL_TYPE, name="Epidermal Melanocyte")
        go = {"source_type": "go", "source_id": "go:GO:0042438", "section": "experimental_go_bp"}
        marker = {
            "source_type": "cell_ontology",
            "source_id": "cl:1",
            "section": "canonical_marker",
        }
        measured = {"source_type": "geo_scrnaseq", "source_id": "geo:GSE298871"}
        curated = _edge(
            session,
            gene,
            RelationKind.PARTICIPATES_IN,
            pathway,
            go,
            method="gene_ontology_experimental",
            claim=ClaimKind.OBSERVED,
            level="knowledge_base",
        )
        both = _edge(
            session,
            gene,
            RelationKind.EXPRESSED_IN,
            cell,
            marker,
            method="cell_ontology",
            claim=ClaimKind.OBSERVED,
            level="knowledge_base",
        )
        upsert_edge(
            session,
            subject=gene,
            predicate=RelationKind.EXPRESSED_IN,
            obj=cell,
            confidence=0.9,
            extraction_method="sc_rnaseq_gse298871",
            evidence=measured,
            claim=ClaimKind.OBSERVED,
            causal_level="correlation_in_human",
        )
        assert enrich.assert_curated_annotations(session) == 1
        claims = {e.id: e.claim for e in session.exec(select(GraphEdge)).all()}
    assert claims == {curated: ClaimKind.ASSERTED, both: ClaimKind.OBSERVED}


def test_coexpression_pairs_keep_the_sign_of_r_and_their_ids(graph_db, tmp_path) -> None:
    torch = pytest.importorskip("torch")
    with session_scope() as session:
        a = upsert_entity(session, kind=EntityKind.TARGET, name="AFDN")
        b = upsert_entity(session, kind=EntityKind.TARGET, name="EIF3E")
        stale = {
            "source_type": "geo",
            "source_id": "geo:GSE311770",
            "pearson_r": 0.71,
            "score": 0.71,
            "relation": "co_expressed_with",
        }
        held = _edge(
            session,
            a,
            RelationKind.CO_EXPRESSED_WITH,
            b,
            stale,
            method="geo_punch_biopsies_gse311770",
            claim=ClaimKind.OBSERVED,
            level="correlation_in_human",
        )
        cache = tmp_path / "coexpression.pt"
        torch.save(
            {
                "edge_index": torch.tensor([[0, 1], [1, 0]]),
                "edge_weight": torch.tensor([0.71, 0.71]),
                "edge_r": torch.tensor([-0.71, -0.71]),
                "entity_ids": torch.tensor([[a.id, b.id], [b.id, a.id]]),
            },
            cache,
        )
        assert enrich.seed_patient_coexpression_edges(session, cache_path=cache) == 0
        (edge,) = session.exec(select(GraphEdge)).all()
    assert edge.id == held
    assert [(r["pearson_r"], r["score"]) for r in edge.evidence] == [(-0.71, 0.71)]


def test_single_cell_rows_follow_the_current_profile(graph_db, monkeypatch) -> None:
    profile = {
        "lineage_cells": {"Epidermal Melanocyte": 500, "Basal Keratinocyte": 9000},
        "genes": {
            "DCT": {
                "top_lineages": [
                    {
                        "lineage": "Epidermal Melanocyte",
                        "mean_cp10k": 61.2,
                        "pct_detect": 0.8,
                        "fold_enrichment": 4.0,
                    }
                ]
            },
        },
    }
    monkeypatch.setattr(enrich, "compute_or_load_single_cell_lineage_profiles", lambda: profile)
    with session_scope() as session:
        dct = upsert_entity(session, kind=EntityKind.TARGET, name="DCT")
        mel = upsert_entity(session, kind=EntityKind.CELL_TYPE, name="Epidermal Melanocyte")
        ker = upsert_entity(session, kind=EntityKind.CELL_TYPE, name="Basal Keratinocyte")
        old = {
            "source_type": "geo_scrnaseq",
            "source_id": "geo:GSE298871",
            "score": 0.92,
            "fold_enrichment": 12.0,
        }
        kept = _edge(
            session,
            dct,
            RelationKind.EXPRESSED_IN,
            mel,
            old,
            method="sc_rnaseq_gse298871",
            claim=ClaimKind.OBSERVED,
            level="correlation_in_human",
        )
        _edge(
            session,
            dct,
            RelationKind.EXPRESSED_IN,
            ker,
            old,
            method="sc_rnaseq_gse298871",
            claim=ClaimKind.OBSERVED,
            level="correlation_in_human",
        )
        result = enrich.seed_single_cell_lineage_expression(session)
        edges = session.exec(select(GraphEdge)).all()
    assert result == {"sc_expressed_in_added": 0, "sc_expressed_in_removed": 1}
    assert [(e.id, e.confidence, [r["fold_enrichment"] for r in e.evidence]) for e in edges] == [
        (kept, 0.82, [4.0])
    ]


def test_an_intervention_its_trial_no_longer_names_leaves_the_graph(graph_db) -> None:
    with session_scope() as session:
        session.add(
            Trial(
                source=TrialSourceKind.ICTRP,
                source_id="CTRI/2012/11/003157",
                brief_title="Apamargaksharyoga in vitiligo",
                interventions=[{"type": "DRUG", "name": "Ointment of Apamargaksharyoga"}],
            )
        )
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="vitiligo")
        trial = upsert_entity(session, kind=EntityKind.TRIAL, name="CTRI/2012/11/003157")
        row = {"source_type": "trial", "source_id": "ictrp:CTRI/2012/11/003157"}
        old = upsert_entity(
            session, kind=EntityKind.DRUG, name="Ointment of Apamargaksharyoga: Dose: QS daily"
        )
        new = upsert_entity(session, kind=EntityKind.DRUG, name="Ointment of Apamargaksharyoga")
        for drug in (old, new):
            _edge(
                session,
                drug,
                RelationKind.TESTED_IN,
                trial,
                row,
                method="structured",
                claim=ClaimKind.ASSERTED,
                level=None,
            )
        investigates = _edge(
            session,
            trial,
            RelationKind.INVESTIGATES,
            vitiligo,
            row,
            method="structured",
            claim=ClaimKind.ASSERTED,
            level=None,
        )
        assert prune_trial_interventions(session, curated={}) == 1
        edges = {e.id for e in session.exec(select(GraphEdge)).all()}
        names = {e.name for e in session.exec(select(GraphEntity)).all()}
    assert investigates in edges and len(edges) == 2
    assert "Ointment of Apamargaksharyoga" in names
    assert "Ointment of Apamargaksharyoga: Dose: QS daily" not in names


def test_a_clean_name_replaces_one_broken_across_lines(graph_db) -> None:
    broken = "Women planning conception within 3 months.\nÃ¢â?"
    with session_scope() as session:
        first = upsert_entity(session, kind=EntityKind.DRUG, name=broken)
        again = upsert_entity(
            session, kind=EntityKind.DRUG, name="Women planning conception within 3 months"
        )
        assert again.id == first.id
        assert again.name == "Women planning conception within 3 months"
        assert broken not in again.aliases


def test_a_registrys_capitals_do_not_rename_an_entity(graph_db) -> None:
    with session_scope() as session:
        upsert_entity(session, kind=EntityKind.DRUG, name="Zasocitinib")
        again = upsert_entity(session, kind=EntityKind.DRUG, name="ZASOCITINIB")
        assert again.name == "Zasocitinib"
        assert upsert_entity(session, kind=EntityKind.DRUG, name="Zasocitinib tablets").name == (
            "Zasocitinib tablets"
        )
