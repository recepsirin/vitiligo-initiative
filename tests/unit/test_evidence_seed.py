"""Tests for graph edges built from measurements.

Written around the two failures this code actually had: a gene splitter that
invented genes, and an enum column whose stored form could not be read back.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.graph.evidence_seed import (
    seed_genetics,
    seed_mechanisms,
    seed_trial_outcomes,
    split_genes,
)
from vitiligo.graph.store import upsert_entity
from vitiligo.mechanisms.schema import from_dict
from vitiligo.reports.jak_arms import ArmEndpointRow
from vitiligo.storage import GeneticAssociation, GeneticSourceKind, init_db, session_scope
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity, RelationKind


@pytest.fixture
def graph_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("VITILIGO_DB_PATH", str(tmp_path / "graph.db"))
    cfg._settings = None
    dbmod._engine = None
    init_db()
    yield
    cfg._settings = None
    dbmod._engine = None


# ------------------------------------------------------------- gene splitting
# A hyphen inside a symbol is part of the name. Splitting on it invented
# "HLA", "DRB1", "AS1" and "2HG", and lost the strongest vitiligo association.


@pytest.mark.parametrize(
    ("mapped", "expected"),
    [
        ("HLA-DRB1 - HLA-DQA1", ["HLA-DRB1", "HLA-DQA1"]),  # intergenic: spaced hyphen
        ("HLA-DRB9", ["HLA-DRB9"]),  # one gene whose name contains a hyphen
        ("MIR4435-2HG", ["MIR4435-2HG"]),
        ("TSBP1-AS1, BTNL2", ["TSBP1-AS1", "BTNL2"]),  # comma: two genes
        ("GZMB, GZMH-AS1", ["GZMB", "GZMH-AS1"]),
        ("CTLA4 - ICOS", ["CTLA4", "ICOS"]),
        ("PTPN22", ["PTPN22"]),
    ],
)
def test_gene_symbols_survive_splitting(mapped: str, expected: list[str]) -> None:
    assert split_genes(mapped) == expected


def test_no_gene_from_an_absent_or_unusable_mapping() -> None:
    assert split_genes(None) == []
    assert split_genes("") == []
    assert split_genes(" - ") == []


# --------------------------------------------------------------- genetic edges


def _association(**over: Any) -> GeneticAssociation:
    fields: dict[str, Any] = {
        "source": GeneticSourceKind.GWAS_CATALOG,
        "source_id": "GCST004785:rs9271597",
        "trait": "Vitiligo",
        "variant": "rs9271597",
        "mapped_gene": "HLA-DRB1 - HLA-DQA1",
        "p_value": 3e-89,
        "p_value_text": "3E-89",
        "odds_ratio_or_beta": 1.772,
        "study_accession": "GCST004785",
        "pubmed_id": "27723757",
        "initial_sample": "2,853 European ancestry cases",
    }
    fields.update(over)
    return GeneticAssociation(**fields)


def test_a_genetic_edge_is_observed_and_carries_its_cohort(graph_db: None) -> None:
    with session_scope() as session:
        session.add(_association())
        session.commit()
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        edges, _ = seed_genetics(session, disease)
        session.commit()
        assert edges == 2  # one per flanking gene
        stored = session.exec(select(GraphEdge)).all()
        genes = {
            session.get(GraphEntity, e.subject_id).name  # type: ignore[union-attr]
            for e in stored
        }
    assert genes == {"HLA-DRB1", "HLA-DQA1"}
    edge = stored[0]
    assert edge.claim == ClaimKind.OBSERVED
    assert edge.causal_level == "human_genetics"
    assert edge.predicate == RelationKind.ASSOCIATED_WITH
    assert edge.evidence[0]["p_value"] == "3E-89"
    assert edge.evidence[0]["cohort"].startswith("2,853")


def test_an_association_below_genome_wide_significance_is_left_out(graph_db: None) -> None:
    """A suggestive hit is not distinguishable from noise; it must not become an edge."""
    with session_scope() as session:
        session.add(_association(p_value=1e-5, p_value_text="1E-5"))
        session.commit()
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        edges, _ = seed_genetics(session, disease)
        assert edges == 0


def test_a_gene_keeps_its_strongest_association(graph_db: None) -> None:
    with session_scope() as session:
        session.add(_association(mapped_gene="PTPN22", p_value=1e-20, p_value_text="1E-20"))
        session.add(
            _association(
                source_id="GCST9:rs2", mapped_gene="PTPN22", variant="rs2",
                p_value=1e-9, p_value_text="1E-9", study_accession="GCST9",
            )
        )  # fmt: skip
        session.commit()
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        seed_genetics(session, disease)
        session.commit()
        [edge] = session.exec(select(GraphEdge)).all()
    assert edge.evidence[0]["p_value"] == "1E-20"


# --------------------------------------------------------------- outcome edges


def _arm(**over: Any) -> ArmEndpointRow:
    fields: dict[str, Any] = {
        "study_id": "NCT04052425", "source_id": "NCT04052425", "trial_agents": "ruxolitinib",
        "arm_label": "Ruxolitinib Cream", "period": None, "arm_role": "active",
        "arm_agent": "ruxolitinib", "dose_value": 1.5, "dose_unit": "%",
        "loading_dose_value": None, "frequency": "BID", "route": "topical",
        "phototherapy": False, "endpoint": "F-VASI75", "instrument": "F-VASI",
        "threshold": 75, "body_region": "face", "assessor": "central", "week": 24,
        "week_source": "registry", "outcome_type": "PRIMARY", "n_analyzed": 221,
        "percent": 29.8, "responders": 66, "responders_derived": False,
        "value_raw": "29.8", "outcome_title": "F-VASI75 at week 24", "row_label": None,
        "flags": [],
    }  # fmt: skip
    fields.update(over)
    return ArmEndpointRow(**fields)


def test_a_posted_result_becomes_an_observed_human_perturbation(graph_db: None) -> None:
    with session_scope() as session:
        edges, _ = seed_trial_outcomes(session, [_arm()])
        session.commit()
        assert edges == 1
        [edge] = session.exec(select(GraphEdge)).all()
        subject = session.get(GraphEntity, edge.subject_id)
        obj = session.get(GraphEntity, edge.object_id)
    assert (subject.name, obj.name) == ("ruxolitinib", "F-VASI75")  # type: ignore[union-attr]
    assert obj.kind == EntityKind.OUTCOME  # type: ignore[union-attr]
    assert edge.predicate == RelationKind.CHANGES
    assert edge.claim == ClaimKind.OBSERVED
    assert edge.causal_level == "perturbation_in_human"
    assert edge.evidence[0]["responders"] == 66


def test_a_control_arm_is_not_an_intervention_effect(graph_db: None) -> None:
    with session_scope() as session:
        edges, _ = seed_trial_outcomes(session, [_arm(arm_role="placebo", arm_agent=None)])
        assert edges == 0


def test_an_arm_with_no_reported_responders_is_not_an_observation(graph_db: None) -> None:
    with session_scope() as session:
        edges, _ = seed_trial_outcomes(session, [_arm(responders=None)])
        assert edges == 0


def test_the_largest_arm_is_kept_for_a_drug_and_endpoint(graph_db: None) -> None:
    """Several trials report the same endpoint; the firmest number should win."""
    with session_scope() as session:
        seed_trial_outcomes(
            session,
            [_arm(n_analyzed=50, responders=10, percent=20.0), _arm(source_id="NCT2")],
        )
        session.commit()
        [edge] = session.exec(select(GraphEdge)).all()
    assert edge.evidence[0]["n_analyzed"] == 221


# ------------------------------------------------------------ mechanism edges


def _mechanism(**over: Any) -> Any:
    record: dict[str, Any] = {
        "id": "trm-il15-relapse",
        "title": "Resident memory T cells bring vitiligo back",
        "status": "draft",
        "outcome": 3,
        "biological_state": "Cells persist in repigmented skin.",
        "mechanistic_claim": "Their survival is necessary for relapse.",
        "intervention": "Block IL-15 signalling.",
        "experimental_outcome": "Cells fall in treated skin.",
        "clinical_outcome": "Longer time to loss of response.",
        "context": {
            "subtype": "non-segmental",
            "tissue": "lesional skin that has repigmented",
            "cell_type": "CD8 tissue-resident memory T cells",
            "disease_stage": "after withdrawal",
        },
        "upstream": ["IL-15 presented by keratinocytes"],
        "downstream": ["loss of response"],
        "evidence": [
            {
                "ref": "pubmed:30021889",
                "stance": "supports",
                "causal_level": "perturbation_in_animal",
                "shows": "Blocking it reversed disease in mice.",
            }
        ],
        "competing": [{"explanation": "A marker, not a cause.", "distinguished_by": "Density."}],
        "test": {
            "question": "Does the score predict relapse?",
            "data": "Biopsies at stopping.",
            "if_correct": "Hazard ratio above 1.",
            "if_incorrect": "No association.",
            "decides": "An association leaves the claim standing.",
        },
        "uncertainty": "Small samples.",
        "last_reviewed": "2026-10-24",
    }
    record.update(over)
    return from_dict(record)


def test_a_hypothesis_joins_the_disease_at_the_rung_its_evidence_reaches(graph_db: None) -> None:
    """The level is computed from the record's evidence, never asserted here."""
    with session_scope() as session:
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        seed_mechanisms(session, disease, [_mechanism()])
        session.commit()
        edges = session.exec(select(GraphEdge)).all()
        to_disease = [e for e in edges if e.object_id == disease.id]
    assert len(to_disease) == 1
    assert to_disease[0].claim == ClaimKind.OBSERVED
    assert to_disease[0].causal_level == "perturbation_in_animal"


def test_a_hypothesis_brings_the_node_types_the_structured_seed_could_not(graph_db: None) -> None:
    with session_scope() as session:
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        seed_mechanisms(session, disease, [_mechanism()])
        session.commit()
        kinds = {e.kind for e in session.exec(select(GraphEntity)).all()}
    assert EntityKind.CELL_TYPE in kinds
    assert EntityKind.PHENOTYPE in kinds
    assert EntityKind.PATHWAY in kinds


def test_context_edges_are_asserted_not_observed(graph_db: None) -> None:
    """Where a claim is said to apply is the curator's framing, not a measurement."""
    with session_scope() as session:
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        seed_mechanisms(session, disease, [_mechanism()])
        session.commit()
        context = session.exec(
            select(GraphEdge).where(GraphEdge.predicate == RelationKind.OCCURS_IN)
        ).all()
    assert context
    assert all(e.claim == ClaimKind.ASSERTED and e.causal_level is None for e in context)


def test_a_hypothesis_with_no_supporting_evidence_is_not_observed(graph_db: None) -> None:
    with session_scope() as session:
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        seed_mechanisms(session, disease, [_mechanism(evidence=[])])
        session.commit()
        to_disease = session.exec(select(GraphEdge).where(GraphEdge.object_id == disease.id)).all()
    assert to_disease[0].claim == ClaimKind.ASSERTED
    assert to_disease[0].causal_level is None


# ------------------------------------------------------------------- upgrading


def test_evidence_upgrades_an_asserted_edge_but_never_downgrades_it(graph_db: None) -> None:
    """Open Targets lists a gene; a GWAS then measures it. The edge should rise."""
    with session_scope() as session:
        session.add(_association(mapped_gene="PTPN22"))
        session.commit()
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        gene = upsert_entity(session, kind=EntityKind.TARGET, name="PTPN22")
        from vitiligo.graph.store import upsert_edge

        upsert_edge(
            session, subject=gene, predicate=RelationKind.ASSOCIATED_WITH, obj=disease,
            confidence=0.5, extraction_method="structured",
            evidence={"source_type": "prior", "source_id": "opentargets:X"},
        )  # fmt: skip
        session.commit()
        seed_genetics(session, disease)
        session.commit()
        [edge] = session.exec(select(GraphEdge)).all()
        assert edge.claim == ClaimKind.OBSERVED
        assert edge.causal_level == "human_genetics"
        assert len(edge.evidence) == 2  # the listing and the measurement both kept

        # A later assertion must not undo the measurement.
        upsert_edge(
            session, subject=gene, predicate=RelationKind.ASSOCIATED_WITH, obj=disease,
            confidence=0.5, extraction_method="structured",
            evidence={"source_type": "prior", "source_id": "opentargets:Y"},
        )  # fmt: skip
        session.commit()
        [edge] = session.exec(select(GraphEdge)).all()
    assert edge.claim == ClaimKind.OBSERVED
    assert edge.causal_level == "human_genetics"
