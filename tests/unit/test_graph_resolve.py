"""One drug, one entity: the drug entities a MeSH concept names are merged."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import select

from vitiligo.graph.resolve import merge_entity, merge_mesh_synonyms, mesh_synonym_groups
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.sources.mesh import MeshRecord, normalise
from vitiligo.storage import session_scope
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity, RelationKind


def _record(ui: str, name: str, *terms: str) -> MeshRecord:
    return MeshRecord(ui=ui, name=name, terms=frozenset(normalise(t) for t in (name, *terms)))


RITLECITINIB = _record("C000614924", "PF-06651600", "ritlecitinib", "ritlecitinib tosylate")
PSORALEN = _record("D005363", "Ficusin", "psoralen")


def _edge(session, subject, predicate, obj, row, **kwargs):  # type: ignore[no-untyped-def]
    edge, _ = upsert_edge(
        session,
        subject=subject,
        predicate=predicate,
        obj=obj,
        confidence=kwargs.get("confidence", 0.5),
        extraction_method=str(row["source_type"]),
        evidence=row,
        claim=kwargs.get("claim", ClaimKind.ASSERTED),
        causal_level=kwargs.get("level"),
    )
    return edge


def _drugs() -> list[GraphEntity]:
    with session_scope() as session:
        return list(session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.DRUG)))


def test_the_names_one_mesh_concept_covers_are_one_drug(test_db_path: Path) -> None:
    with session_scope() as session:
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        trial = upsert_entity(session, kind=EntityKind.TRIAL, name="NCT03715829")
        named = upsert_entity(session, kind=EntityKind.DRUG, name="ritlecitinib")
        salt = upsert_entity(session, kind=EntityKind.DRUG, name="RITLECITINIB TOSYLATE")
        paper = upsert_entity(
            session,
            kind=EntityKind.DRUG,
            name="PF-06651600",
            external_ids={"mesh": "C000614924"},
        )
        trial_row = {"source_type": "trial", "source_id": "ctgov:NCT03715829"}
        _edge(session, named, RelationKind.TREATS, vitiligo, trial_row, confidence=0.68)
        _edge(session, named, RelationKind.TESTED_IN, trial, trial_row)
        prior_row = {"source_type": "prior", "source_id": "opentargets:CHEMBL4594420"}
        _edge(session, salt, RelationKind.TREATS, vitiligo, prior_row, confidence=0.88)
        paper_row = {"source_type": "pubtator3", "source_id": "pmid:1"}
        _edge(session, paper, RelationKind.TREATS, vitiligo, paper_row)
        _edge(session, paper, RelationKind.ASSOCIATED_WITH, named, paper_row)  # one drug, two names
        assert merge_mesh_synonyms(session, {RITLECITINIB.ui: RITLECITINIB}) == 2
    [drug] = _drugs()
    assert drug.name == "ritlecitinib"
    assert {"PF-06651600", "RITLECITINIB TOSYLATE"} <= set(drug.aliases)
    assert drug.external_ids["mesh"] == "C000614924"
    with session_scope() as session:
        edges = list(session.exec(select(GraphEdge)))
        treats = [e for e in edges if e.predicate == RelationKind.TREATS]
    assert len(treats) == 1
    assert {row["source_type"] for row in treats[0].evidence} == {"trial", "prior", "pubtator3"}
    assert treats[0].confidence == 0.88
    assert all(e.subject_id != e.object_id for e in edges)


def test_a_drug_another_source_named_keeps_its_name(test_db_path: Path) -> None:
    """MeSH heads psoralen "Ficusin"; a paper is the weakest source in the graph."""
    with session_scope() as session:
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        named = upsert_entity(session, kind=EntityKind.DRUG, name="psoralen")
        paper = upsert_entity(
            session, kind=EntityKind.DRUG, name="Ficusin", external_ids={"mesh": "D005363"}
        )
        _edge(
            session,
            named,
            RelationKind.TREATS,
            vitiligo,
            {"source_type": "trial", "source_id": "ctgov:NCT1"},
        )
        for pmid in range(1, 4):
            target = upsert_entity(session, kind=EntityKind.TARGET, name=f"GENE{pmid}")
            _edge(
                session,
                paper,
                RelationKind.TARGETS,
                target,
                {"source_type": "pubtator3", "source_id": f"pmid:{pmid}"},
            )
        merge_mesh_synonyms(session, {PSORALEN.ui: PSORALEN})
    assert [drug.name for drug in _drugs()] == ["psoralen"]


def test_what_is_not_surely_one_concept_is_not_merged(test_db_path: Path) -> None:
    other = _record("C999999", "Psoralen derivative", "psoralen")
    fluticasone = _record("D000068298", "Fluticasone", "fluticasone propionate", "FP")
    with session_scope() as session:
        upsert_entity(
            session, kind=EntityKind.DRUG, name="Ficusin", external_ids={"mesh": "D005363"}
        )
        upsert_entity(
            session,
            kind=EntityKind.DRUG,
            name="Psoralen derivative",
            external_ids={"mesh": "C999999"},
        )
        upsert_entity(session, kind=EntityKind.DRUG, name="psoralen")  # two concepts claim it
        upsert_entity(
            session, kind=EntityKind.DRUG, name="Fluticasone", external_ids={"mesh": "D000068298"}
        )
        upsert_entity(  # another concept's identifier
            session,
            kind=EntityKind.DRUG,
            name="fluticasone propionate",
            external_ids={"mesh": "D000068299"},
        )
        upsert_entity(session, kind=EntityKind.DRUG, name="FP")  # an abbreviation
    mesh = {r.ui: r for r in (PSORALEN, other, fluticasone)}
    assert mesh_synonym_groups(_drugs(), mesh) == []


def test_a_merged_relation_keeps_an_observation_and_a_moved_one_its_id(test_db_path: Path) -> None:
    with session_scope() as session:
        gene = upsert_entity(session, kind=EntityKind.TARGET, name="JAK1")
        cell = upsert_entity(session, kind=EntityKind.CELL_TYPE, name="CD8+ T cell")
        named = upsert_entity(session, kind=EntityKind.DRUG, name="ritlecitinib")
        paper = upsert_entity(
            session, kind=EntityKind.DRUG, name="PF-06651600", external_ids={"mesh": "C000614924"}
        )
        _edge(
            session,
            named,
            RelationKind.INHIBITS,
            gene,
            {"source_type": "trial", "source_id": "ctgov:NCT1"},
        )
        _edge(
            session,
            paper,
            RelationKind.INHIBITS,
            gene,
            {"source_type": "assay", "source_id": "doi:10.1/x", "value": 0.1},
            claim=ClaimKind.OBSERVED,
            level="mechanism_assertion",
        )
        moved = _edge(
            session,
            paper,
            RelationKind.ASSOCIATED_WITH,
            cell,
            {"source_type": "pubtator3", "source_id": "pmid:2"},
        )
        merge_entity(session, named, paper)
        inhibits = session.exec(
            select(GraphEdge).where(GraphEdge.predicate == RelationKind.INHIBITS)
        ).one()
        assert inhibits.claim == ClaimKind.OBSERVED
        assert inhibits.causal_level == "mechanism_assertion"
        assert session.get(GraphEdge, moved.id).subject_id == named.id
