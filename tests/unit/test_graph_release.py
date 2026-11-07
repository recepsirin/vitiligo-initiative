"""The graph as a released dataset: each source's terms decide what ships, and how."""

from __future__ import annotations

import json

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.graph.export import export_release
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.storage import init_db, session_scope
from vitiligo.storage.models import EntityKind, RelationKind

MODEL = "biored-BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext"


def _read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_release_follows_each_sources_terms(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VITILIGO_DB_PATH", str(tmp_path / "graph.db"))
    cfg._settings = None
    dbmod._engine = None
    init_db()
    with session_scope() as session:
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="vitiligo")
        drug = upsert_entity(session, kind=EntityKind.DRUG, name="tacrolimus")
        gene = upsert_entity(session, kind=EntityKind.TARGET, name="JAK1")
        trial = upsert_entity(
            session,
            kind=EntityKind.TRIAL,
            name="CTRI/2019/07/020345",
            aliases=["A title as WHO records it"],
            external_ids={"ictrp": "CTRI/2019/07/020345"},
        )

        def edge(subject, predicate, obj, *evidence):
            first, *rest = evidence
            made, _ = upsert_edge(
                session,
                subject=subject,
                predicate=predicate,
                obj=obj,
                confidence=0.5,
                extraction_method="structured",
                evidence=first,
            )
            for item in rest:
                upsert_edge(
                    session,
                    subject=subject,
                    predicate=predicate,
                    obj=obj,
                    confidence=0.5,
                    extraction_method="structured",
                    evidence=item,
                )
            return made.id

        quoted = {"source_type": MODEL, "source_id": "pmid:1", "snippet": "Open sentence."}
        closed = {
            "source_type": MODEL,
            "source_id": "pmid:2",
            "snippet": "Non-commercial sentence.",
        }
        drugbank = {"source_type": "prior", "source_id": "drugbank:DB00864"}
        who = {"source_type": "trial", "source_id": "ictrp:CTRI/2019/07/020345"}
        pubtator = {"source_type": "pubtator3", "source_id": "pmid:3"}
        treats = edge(drug, RelationKind.TREATS, vitiligo, quoted, closed, drugbank)
        investigates = edge(trial, RelationKind.INVESTIGATES, vitiligo, who)
        edge(gene, RelationKind.ASSOCIATED_WITH, vitiligo, drugbank)
        tested = edge(drug, RelationKind.TESTED_IN, trial, who, pubtator)

    stats = export_release(tmp_path / "out", {"1": "cc by", "2": "cc by-nc", "3": "cc by"})

    out = tmp_path / "out"
    relations = {r["id"] for r in _read(out / "relations.jsonl")}
    evidence = _read(out / "evidence.jsonl")
    texts = {r["source"]: r["text"] for r in evidence}
    assert relations == {treats, tested}
    assert {r["id"] for r in _read(out / "ictrp" / "relations.jsonl")} == {investigates}
    assert texts == {"pmid:1": "Open sentence.", "pmid:2": None, "pmid:3": None}
    assert {r["source"] for r in _read(out / "ictrp" / "evidence.jsonl")} == {
        "ictrp:CTRI/2019/07/020345"
    }
    trial_row = next(
        e for e in _read(out / "entities.jsonl") if e["kind"] == EntityKind.TRIAL.value
    )
    assert trial_row["aliases"] == []
    assert stats.dropped == 2
