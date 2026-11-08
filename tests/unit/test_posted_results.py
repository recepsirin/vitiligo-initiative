"""Posted registry results: each group read as the regimen it received, and what was measured."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.graph.posted_results import Group, Vocabulary, resolve_groups, seed_posted_results
from vitiligo.graph.store import upsert_entity
from vitiligo.sources.mesh import MeshRecord
from vitiligo.storage import Trial, init_db, session_scope
from vitiligo.storage.models import EntityKind, GraphEdge, GraphEntity, TrialSourceKind


@pytest.fixture
def graph_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("VITILIGO_DB_PATH", str(tmp_path / "graph.db"))
    cfg._settings = None
    dbmod._engine = None
    init_db()
    yield
    cfg._settings = None
    dbmod._engine = None


def test_a_results_group_is_what_it_received_or_is_left_out() -> None:
    """A development code is its drug, a drug's vehicle is the vehicle, a description
    that names a placebo decides nothing, a drug withheld is not given, and a group
    switched from placebo to drug, or from one drug to another, is neither.
    """
    study = {
        "protocolSection": {
            "armsInterventionsModule": {
                "interventions": [
                    {"type": "DRUG", "name": "CP-690,550"},
                    {"type": "DRUG", "name": "Placebo"},
                    {"type": "DRUG", "name": "Withhold MTX", "otherNames": ["methotrexate"]},
                    {"type": "DRUG", "name": "Methotrexate"},
                ]
            }
        }
    }
    groups = [
        {"id": "A", "title": "Tofacitinib 10 mg BID"},
        {"id": "B", "title": "CP-690,550 Vehicle"},
        {"id": "C", "title": "Placebo / CP-690,550 5 mg"},
        {"id": "D", "title": "Group D", "description": "Placebo matching CP-690,550"},
        {"id": "E", "title": "Withhold MTX"},
        {"id": "F", "title": "Methotrexate -> Tofacitinib 5 mg"},
    ]
    vocabulary = Vocabulary({"tofacitinib": {"CP-690,550"}, "methotrexate": {"MTX"}})

    got = resolve_groups(study, groups, vocabulary)

    assert got["A"].regimen == (EntityKind.DRUG, "tofacitinib")
    assert got["B"] == Group("CP-690,550 Vehicle", control=True)
    assert "C" not in got
    assert got["D"] == Group("Group D")
    assert got["E"].control
    assert "F" not in got


def test_mesh_names_a_substance_once_and_never_a_class_or_an_alternative(graph_db: None) -> None:
    """MeSH's entry terms join a development code to its drug, but a class's terms
    ("acid" for Acids) name nothing, and "etanercept or adalimumab" is neither.
    """
    with session_scope() as session:
        for name, mesh in (("secukinumab", "C555450"), ("Acids", "D000143"), ("Esters", "D004952")):
            upsert_entity(session, kind=EntityKind.DRUG, name=name, external_ids={"mesh": mesh})
        records = {
            "C555450": MeshRecord("C555450", "secukinumab", frozenset({"ain 457", "cosentyx"})),
            "D000143": MeshRecord("D000143", "Acids", frozenset({"acid", "acids"})),
            "D004952": MeshRecord("D004952", "Esters", frozenset({"ester", "esters"})),
        }
        vocabulary = Vocabulary.load(session, lambda ids: {i: records[i] for i in ids})

    assert vocabulary.read("AIN457 150 mg") == ["secukinumab"]
    assert vocabulary.read("Fumaric Acid Esters") == []
    assert vocabulary.read("Cosentyx or AIN457") == []


def _trial(source_id: str, condition: str, outcome: str) -> Trial:
    groups = [{"id": "G0", "title": "Ruxolitinib 1.5% Cream BID"}, {"id": "G1", "title": "Vehicle"}]

    def stats(drug: int, vehicle: int) -> list[dict[str, Any]]:
        return [
            {"groupId": "G0", "numAffected": drug, "numAtRisk": 100},
            {"groupId": "G1", "numAffected": vehicle, "numAtRisk": 50},
        ]

    study = {
        "protocolSection": {
            "armsInterventionsModule": {
                "interventions": [
                    {"type": "DRUG", "name": "Ruxolitinib cream"},
                    {"type": "DRUG", "name": "Vehicle cream"},
                ]
            }
        },
        "resultsSection": {
            "adverseEventsModule": {
                "eventGroups": groups,
                "otherEvents": [
                    {"term": "Acne", "stats": stats(5, 1)},
                    {"term": "Vitiligo", "stats": stats(0, 2)},
                ],
            },
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "title": outcome,
                        "groups": groups,
                        "classes": [
                            {
                                "categories": [
                                    {
                                        "measurements": [
                                            {"groupId": "G0", "value": "30.1"},
                                            {"groupId": "G1", "value": "10.3"},
                                        ]
                                    }
                                ]
                            }
                        ],
                        "analyses": [{"groupIds": ["G0", "G1"], "pValue": "<0.001"}],
                    }
                ]
            },
        },
    }
    return Trial(
        source=TrialSourceKind.CTGOV,
        source_id=source_id,
        brief_title=f"Ruxolitinib cream in {condition}",
        conditions=[condition],
        has_results=True,
        raw_metadata={"study": study},
    )


def test_posted_results_join_a_regimen_to_what_was_measured_beside_its_comparator(
    graph_db: None,
) -> None:
    """Adverse events come from every trial, outcomes only from vitiligo trials; a row
    carries its comparator; an event no one on the drug had is no edge; a rerun is a no-op.
    """
    trials = [
        _trial("NCT00000001", "Vitiligo", "Proportion achieving F-VASI75 at week 24"),
        _trial("NCT00000002", "Atopic dermatitis", "Proportion achieving EASI-75 response"),
    ]

    def edges() -> dict[tuple[str, str], list[dict[str, Any]]]:
        with session_scope() as session:
            names = {e.id: e.name for e in session.exec(select(GraphEntity)).all()}
            return {
                (names[e.subject_id], names[e.object_id]): list(e.evidence or [])
                for e in session.exec(select(GraphEdge)).all()
            }

    with session_scope() as session:
        seed_posted_results(session, trials)
    got = edges()

    assert set(got) == {("ruxolitinib", "Acne"), ("ruxolitinib", "Repigmentation")}
    acne = got[("ruxolitinib", "Acne")]
    assert [(r["source_id"], r["affected"], r["at_risk"]) for r in acne] == [
        ("ctgov:NCT00000001", 5, 100),
        ("ctgov:NCT00000002", 5, 100),
    ]
    assert acne[0]["versus"] == [{"group": "Vehicle", "affected": 1, "at_risk": 50}]
    measured = got[("ruxolitinib", "Repigmentation")]
    assert {r["source_id"] for r in measured} == {"ctgov:NCT00000001"}
    assert [(r["result_type"], r.get("value"), r.get("p")) for r in measured] == [
        ("outcome", "30.1", None),
        ("comparison", None, "<0.001"),
    ]
    assert measured[0]["versus"] == [{"group": "Vehicle", "value": "10.3", "n": None}]

    with session_scope() as session:
        assert seed_posted_results(session, trials)[0] == 0
    assert edges() == got
