"""Relations read out of papers, as the graph receives them.

Each test is one of the failures measured across the corpus that
``graph.literature_seed`` is written around. Documents are built the way
PubTator exports them and read by the real parser.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from sqlmodel import select

from vitiligo.graph.literature_seed import LiteratureReader, gene_symbols, load_literature
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.sources.mesh import MeshRecord, normalise
from vitiligo.sources.pubtator import parse_export
from vitiligo.storage import session_scope
from vitiligo.storage.models import EntityKind, GraphEdge, GraphEntity, RelationKind

TITLE = "A study."
VITILIGO = ("vitiligo", "Disease", "MESH:D014820", "Vitiligo")
TACROLIMUS = ("Tacrolimus", "Chemical", "MESH:D016559", "Tacrolimus")


def _record(ui: str, name: str, *terms: str, actions: tuple[str, ...] = ()) -> MeshRecord:
    return MeshRecord(
        ui=ui,
        name=name,
        terms=frozenset(normalise(t) for t in (name, *terms)),
        pharmacological_actions=actions,
    )


MESH = {
    r.ui: r
    for r in (
        _record("D016559", "Tacrolimus", actions=("Immunosuppressive Agents",)),
        _record("D000077271", "Imiquimod", actions=("Adjuvants, Immunologic",)),
        _record("C000613732", "upadacitinib", actions=("Janus Kinase Inhibitors",)),
        _record("C540383", "ruxolitinib"),  # a supplementary record: no actions in 2026
        _record("D008543", "Melanins", "melanin"),
        _record("D002245", "Carbon Dioxide", "CO2"),
        _record("D016112", "Ichthyosis Vulgaris"),
        _record(
            "D009358",
            "Congenital, Hereditary, and Neonatal Diseases and Abnormalities",
            "congenital disorder",
        ),
    )
}


def _doc(
    pmid: str,
    abstract: str,
    mentions: list[tuple[str, str, str, str]],
    relations: list[tuple[str, float, str, str]],
) -> dict[str, Any]:
    """A document as PubTator exports it, its title first.

    ``mentions`` are (written, type, identifier, name), found in the abstract
    in order; ``relations`` are (type, score, identifier, identifier).
    """
    start = len(TITLE) + 1
    concepts: dict[str, dict[str, str]] = {}
    annotations = []
    searched: dict[str, int] = {}
    for written, kind, identifier, name in mentions:
        infons = {"type": kind, "identifier": identifier, "name": name}
        if kind == "Gene":
            infons["accession"] = f"@GENE_{name.upper()}"
        concepts[identifier] = infons
        at = abstract.index(written, searched.get(written, 0))
        searched[written] = at + 1
        annotations.append(
            {
                "text": written,
                "infons": infons,
                "locations": [{"offset": start + at, "length": len(written)}],
            }
        )
    return {
        "pmid": pmid,
        "passages": [
            {"infons": {"type": "title"}, "offset": 0, "text": TITLE, "annotations": []},
            {
                "infons": {"type": "abstract"},
                "offset": start,
                "text": abstract,
                "annotations": annotations,
            },
        ],
        "relations": [
            {"infons": {"type": kind, "score": score, "role1": concepts[a], "role2": concepts[b]}}
            for kind, score, a, b in relations
        ],
    }


def _load(*docs: dict[str, Any], given: tuple[str, ...] = ()) -> None:
    documents = list(parse_export(json.dumps({"PubTator3": list(docs)}).encode()))
    reader = LiteratureReader(MESH, given, gene_symbols(documents))
    with session_scope() as session:
        load_literature(session, documents, reader)


def _edges() -> set[tuple[str, RelationKind, str]]:
    with session_scope() as session:
        names = {e.id: e.name for e in session.exec(select(GraphEntity)).all()}
        return {
            (names[e.subject_id], e.predicate, names[e.object_id])
            for e in session.exec(select(GraphEdge)).all()
        }


def test_a_description_of_vitiligo_is_vitiligo_and_an_unnamed_disease_is_dropped(
    test_db_path: Path,
) -> None:
    """PubTator files "vitiligo vulgaris" under Ichthyosis Vulgaris, and
    "depigmentation disorder" under congenital diseases."""
    _load(
        _doc(
            "1",
            "Tacrolimus repigmented vitiligo vulgaris, a depigmentation disorder.",
            [
                TACROLIMUS,
                ("vitiligo vulgaris", "Disease", "MESH:D016112", "Ichthyosis Vulgaris"),
                ("depigmentation disorder", "Disease", "MESH:D009358", "Congenital"),
            ],
            [
                ("Negative_Correlation", 0.99, "MESH:D016559", "MESH:D016112"),
                ("Negative_Correlation", 0.99, "MESH:D016559", "MESH:D009358"),
            ],
        )
    )
    assert _edges() == {("Tacrolimus", RelationKind.TREATS, "Vitiligo")}


def test_lower_in_a_disease_is_not_treating_it(test_db_path: Path) -> None:
    """PubTator's "treat" is Negative_Correlation, which also means "found
    lower in". Only a drug treats; a trial giving it makes a molecule a drug
    when MeSH records no action for it."""
    _load(
        _doc(
            "1",
            "Tacrolimus and ruxolitinib repigment vitiligo, where melanin is low; "
            "imiquimod induced it.",
            [
                TACROLIMUS,
                ("ruxolitinib", "Chemical", "MESH:C540383", "ruxolitinib"),
                VITILIGO,
                ("melanin", "Chemical", "MESH:D008543", "Melanins"),
                ("imiquimod", "Chemical", "MESH:D000077271", "Imiquimod"),
            ],
            [
                ("Negative_Correlation", 1.0, "MESH:D016559", "MESH:D014820"),
                ("Negative_Correlation", 1.0, "MESH:C540383", "MESH:D014820"),
                ("Negative_Correlation", 1.0, "MESH:D008543", "MESH:D014820"),
                ("Positive_Correlation", 1.0, "MESH:D000077271", "MESH:D014820"),
                # Below the model's own decision boundary.
                ("Positive_Correlation", 0.3, "MESH:D016559", "MESH:D014820"),
            ],
        ),
        given=("Ruxolitinib cream",),
    )
    assert _edges() == {
        ("Tacrolimus", RelationKind.TREATS, "Vitiligo"),
        ("ruxolitinib", RelationKind.TREATS, "Vitiligo"),
        ("Melanins", RelationKind.ASSOCIATED_WITH, "Vitiligo"),
        ("Imiquimod", RelationKind.CAUSES, "Vitiligo"),
    }


def test_a_chemical_written_before_laser_is_the_laser(test_db_path: Path) -> None:
    """ "Fractional CO2 laser" is annotated as the chemical Carbon Dioxide."""
    _load(
        _doc(
            "1",
            "Fractional CO2 laser repigmented vitiligo.",
            [("CO2", "Chemical", "MESH:D002245", "Carbon Dioxide"), VITILIGO],
            [("Negative_Correlation", 1.0, "MESH:D002245", "MESH:D014820")],
        )
    )
    assert _edges() == {("Carbon Dioxide laser", RelationKind.TREATS, "Vitiligo")}


def test_a_gene_is_one_node_across_species_spelled_the_human_way(test_db_path: Path) -> None:
    """Mouse Nr3c1 (Gene 14815) and human NR3C1 (Gene 2908) share PubTator's
    accession; the mouse id once overwrote the human node's."""
    human = _doc(
        "1",
        "NR3C1 is raised in vitiligo.",
        [("NR3C1", "Gene", "2908", "NR3C1"), VITILIGO],
        [("Association", 1.0, "2908", "MESH:D014820")],
    )
    mouse = _doc(
        "2",
        "Nr3c1 knockout, Nr3c1 and Nr3c1 again, in vitiligo.",
        [("Nr3c1", "Gene", "14815", "Nr3c1")] * 3 + [VITILIGO],
        [("Association", 1.0, "14815", "MESH:D014820")],
    )
    _load(human, mouse)
    with session_scope() as session:
        [target] = session.exec(
            select(GraphEntity).where(GraphEntity.kind == EntityKind.TARGET)
        ).all()
        [edge] = session.exec(select(GraphEdge)).all()
    assert target.name == "NR3C1"
    assert "14815" not in (target.external_ids or {}).values()
    assert [e["ncbi_gene"] for e in edge.evidence] == [["2908"], ["14815"]]


def test_a_node_another_source_named_keeps_its_name(test_db_path: Path) -> None:
    """MeSH writes "upadacitinib"; a registry wrote "Upadacitinib" first."""
    with session_scope() as session:
        upsert_entity(session, kind=EntityKind.DRUG, name="Upadacitinib")
    _load(
        _doc(
            "1",
            "upadacitinib repigmented vitiligo.",
            [("upadacitinib", "Chemical", "MESH:C000613732", "upadacitinib"), VITILIGO],
            [("Negative_Correlation", 1.0, "MESH:C000613732", "MESH:D014820")],
        )
    )
    with session_scope() as session:
        [drug] = session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.DRUG)).all()
    assert drug.name == "Upadacitinib"
    assert "upadacitinib" in drug.aliases


def test_papers_repeating_an_edge_do_not_push_out_the_source_that_made_it(
    test_db_path: Path,
) -> None:
    """Evidence was capped at 20 entries, dropping the oldest: the registry's."""
    with session_scope() as session:
        upsert_edge(
            session,
            subject=upsert_entity(session, kind=EntityKind.DRUG, name="Tacrolimus"),
            predicate=RelationKind.TREATS,
            obj=upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo"),
            confidence=0.88,
            extraction_method="structured",
            evidence={"source_type": "prior", "source_id": "opentargets:CHEMBL269"},
        )
    _load(
        *(
            _doc(
                str(pmid),
                "Tacrolimus repigmented vitiligo.",
                [TACROLIMUS, VITILIGO],
                [("Negative_Correlation", 1.0, "MESH:D016559", "MESH:D014820")],
            )
            for pmid in range(1, 26)
        )
    )
    with session_scope() as session:
        [edge] = session.exec(select(GraphEdge)).all()
    assert edge.evidence[0]["source_type"] == "prior"
    assert len(edge.evidence) == 26


def test_a_model_relation_keeps_its_extractor_and_its_quote(test_db_path: Path) -> None:
    """A full-text model's relation names its model and cites its passage; the
    model's own tuned threshold decided it, so PubTator's floor does not apply."""
    [doc] = parse_export(
        json.dumps(
            {
                "PubTator3": [
                    _doc(
                        "1",
                        "Tacrolimus repigmented vitiligo.",
                        [TACROLIMUS, VITILIGO],
                        [("Negative_Correlation", 1.0, "MESH:D016559", "MESH:D014820")],
                    )
                ]
            }
        ).encode()
    )
    quote = "Tacrolimus repigmented vitiligo."
    read = replace(
        doc,
        relations=tuple(
            replace(r, score=0.3, section="RESULTS", snippet=quote) for r in doc.relations
        ),
    )
    # A paper outside PubMed is cited by its own scheme, not as a PMID.
    crossref = replace(read, pmid="doi:10.1159/000252179")
    with session_scope() as session:
        load_literature(
            session,
            [read, crossref],
            LiteratureReader(MESH, (), gene_symbols([read])),
            method="biored-test",
            min_score=0.0,
        )
    with session_scope() as session:
        [edge] = session.exec(select(GraphEdge)).all()
    assert edge.extraction_method == "biored-test"
    assert edge.evidence[0] == {
        "source_type": "biored-test",
        "source_id": "pmid:1",
        "relation": "Negative_Correlation",
        "score": 0.3,
        "section": "RESULTS",
        "snippet": quote,
    }
    assert [e["source_id"] for e in edge.evidence] == ["pmid:1", "doi:10.1159/000252179"]


def test_a_combination_is_one_undirected_edge_and_a_comparison_is_not_loaded(
    test_db_path: Path,
) -> None:
    """PubTator's Cotreatment was right in 13 of 15 sampled; its Comparison in 6."""
    _load(
        _doc(
            "1",
            "Tacrolimus with imiquimod, against melanin.",
            [
                TACROLIMUS,
                ("imiquimod", "Chemical", "MESH:D000077271", "Imiquimod"),
                ("melanin", "Chemical", "MESH:D008543", "Melanins"),
            ],
            [
                ("Cotreatment", 1.0, "MESH:D016559", "MESH:D000077271"),
                ("Comparison", 1.0, "MESH:D016559", "MESH:D008543"),
            ],
        )
    )
    assert _edges() == {("Imiquimod", RelationKind.COMBINED_WITH, "Tacrolimus")}


def test_the_model_is_trusted_only_with_what_it_was_measured_to_get_right(
    test_db_path: Path,
) -> None:
    """Its "treats" for a disease other than vitiligo was right 7 times in 13, its
    combinations 2 in 6; and its edges sit below PubTator's in confidence."""
    from vitiligo.relations.apply import CONFIDENCE, trusted

    [doc] = parse_export(
        json.dumps(
            {
                "PubTator3": [
                    _doc(
                        "1",
                        "Tacrolimus for vitiligo and ichthyosis vulgaris, with imiquimod.",
                        [
                            TACROLIMUS,
                            VITILIGO,
                            (
                                "ichthyosis vulgaris",
                                "Disease",
                                "MESH:D016112",
                                "Ichthyosis Vulgaris",
                            ),
                            ("imiquimod", "Chemical", "MESH:D000077271", "Imiquimod"),
                        ],
                        [
                            ("Negative_Correlation", 0.9, "MESH:D016559", "MESH:D014820"),
                            ("Negative_Correlation", 0.9, "MESH:D016559", "MESH:D016112"),
                            ("Cotreatment", 0.9, "MESH:D016559", "MESH:D000077271"),
                        ],
                    )
                ]
            }
        ).encode()
    )
    with session_scope() as session:
        load_literature(
            session,
            [doc],
            LiteratureReader(MESH, (), gene_symbols([doc])),
            method="biored-test",
            confidence=CONFIDENCE,
            accept=trusted,
        )
    assert _edges() == {("Tacrolimus", RelationKind.TREATS, "Vitiligo")}
    with session_scope() as session:
        [edge] = session.exec(select(GraphEdge)).all()
    assert edge.confidence == CONFIDENCE < 0.5


def test_active_voice_snippet_resolves_directional_gene_and_drug_mechanisms(
    test_db_path: Path,
) -> None:
    """When a full-text snippet carries an unambiguous active-voice verb between
    two targets or a drug and a target, _predicate resolves ACTIVATES or INHIBITS."""
    quote = "MITF directly upregulates TYR, whereas DKK1 suppresses TYR."
    [doc] = parse_export(
        json.dumps(
            {
                "PubTator3": [
                    _doc(
                        "1",
                        quote,
                        [
                            ("MITF", "Gene", "4286", "MITF"),
                            ("TYR", "Gene", "7299", "TYR"),
                            ("DKK1", "Gene", "22943", "DKK1"),
                        ],
                        [
                            ("Positive_Correlation", 0.92, "4286", "7299"),
                            ("Negative_Correlation", 0.91, "22943", "7299"),
                        ],
                    )
                ]
            }
        ).encode()
    )
    read = replace(
        doc,
        relations=tuple(replace(r, section="RESULTS", snippet=quote) for r in doc.relations),
    )
    with session_scope() as session:
        load_literature(
            session,
            [read],
            LiteratureReader(MESH, (), gene_symbols([read])),
            method="biored-test",
        )
    assert _edges() == {
        ("MITF", RelationKind.ACTIVATES, "TYR"),
        ("DKK1", RelationKind.INHIBITS, "TYR"),
    }
