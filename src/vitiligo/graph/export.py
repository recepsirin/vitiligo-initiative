"""Export the knowledge graph for expert review and archival snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc
from sqlmodel import Session, col, select

from vitiligo import __version__
from vitiligo.graph.query import GraphEdgeView, _edge_to_view, summarize_graph
from vitiligo.storage import get_engine
from vitiligo.storage.models import GraphEdge, GraphEntity


def export_graph_snapshot(*, edge_limit: int | None = None) -> dict[str, Any]:
    """Return the full graph (entities + edges) as a JSON-serializable dict."""
    summary = summarize_graph()
    stats = {row.label: row.count for group in summary.values() for row in group}

    with Session(get_engine(), expire_on_commit=False) as session:
        entities = list(
            session.exec(select(GraphEntity).order_by(GraphEntity.kind, GraphEntity.name)).all()
        )
        stmt = select(GraphEdge).order_by(desc(GraphEdge.confidence), GraphEdge.id)
        if edge_limit is not None:
            stmt = stmt.limit(edge_limit)
        edges = list(session.exec(stmt).all())

        entity_rows = [_entity_to_dict(e) for e in entities]
        edge_rows: list[dict[str, Any]] = []
        for edge in edges:
            view = _edge_to_view(session, edge)
            if view is None:
                continue
            edge_rows.append(_edge_view_to_dict(view, edge))

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "engine_version": __version__,
        "stats": stats,
        "entities": entity_rows,
        "edges": edge_rows,
    }


def _entity_to_dict(entity: GraphEntity) -> dict[str, Any]:
    kind = entity.kind.value if hasattr(entity.kind, "value") else str(entity.kind)
    return {
        "id": entity.id,
        "kind": kind,
        "key": entity.key,
        "name": entity.name,
        "aliases": list(entity.aliases or []),
        "external_ids": dict(entity.external_ids or {}),
    }


def _edge_view_to_dict(view: GraphEdgeView, edge: GraphEdge) -> dict[str, Any]:
    return {
        "id": view.id,
        "subject_kind": view.subject_kind,
        "subject_name": view.subject_name,
        "subject_key": view.subject_key,
        "predicate": view.predicate,
        "object_kind": view.object_kind,
        "object_name": view.object_name,
        "object_key": view.object_key,
        "confidence": view.confidence,
        "extraction_method": view.extraction_method,
        # A reviewer cannot weigh an edge without knowing whether it was
        # measured or merely listed, so both travel with the snapshot.
        "claim": view.claim,
        "causal_level": view.causal_level,
        "evidence_count": view.evidence_count,
        "evidence": list(edge.evidence or [])[:5],
    }


# A sentence is published verbatim only where its source allows it under CC BY
# 4.0: an open-access paper licensed CC BY or CC0, or a US government record.
# Any other sentence is published as a pointer to its paper and section.
_OPEN_LICENCES = frozenset({"cc by", "cc0"})
_GOVERNMENT_TEXT = {
    "reporter": "NIH RePORTER (US government)",
    "ctgov": "ClinicalTrials.gov",
    "geo": "NCBI Gene Expression Omnibus (US government)",
    "wikipathways": "WikiPathways (CC0 1.0)",
    "go": "Gene Ontology Consortium (CC BY 4.0)",
    "reactome": "Reactome Pathway Knowledgebase (CC BY 4.0)",
    "cell_ontology": "Cell Ontology (CC BY 4.0)",
}
# ChEMBL (CC BY-SA 3.0) and DrugCentral (CC BY-SA 4.0) ask that what is made from
# them be shared alike, so their rows go to share-alike/ under CC BY-SA 4.0 and
# the rest of the release stays CC BY 4.0. Both arrive as "chembl" rows; the
# section tells them apart. Until 2026-11-21 they sat in the CC BY files under
# one label that called DrugCentral CC0.
_SHARE_ALIKE = {
    "curated_mechanism_of_action": "ChEMBL (CC BY-SA 3.0)",
    "human_bioactivity_assay": "DrugCentral (CC BY-SA 4.0)",
}
_MODEL = "biored-BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext"
_COLUMNS = ("source_id", "source_type", "relation", "score", "section", "snippet")


@dataclass(frozen=True)
class ReleaseStats:
    entities: int
    relations: int
    evidence: int
    quoted: int
    ictrp_relations: int
    ictrp_evidence: int
    share_alike_relations: int
    share_alike_evidence: int
    dropped: int


def export_release(out: Path, licences: dict[str, str | None]) -> ReleaseStats:
    """Write the graph as a dataset others may reuse: entities, relations, evidence.

    ``licences`` maps a PMID to its full text's licence. Four sources set
    terms of their own. WHO's ICTRP forbids commercial use, so what rests on it
    goes to ``ictrp/`` under WHO's terms. ChEMBL and DrugCentral require
    share-alike, so their rows go to ``share-alike/`` under CC BY-SA 4.0; the
    rest is CC BY 4.0. DrugBank does not allow redistribution, so its entries
    are left out. And a sentence quoted from a paper is the paper's, so it is
    published only where the paper's licence allows; otherwise its pointer
    still is.

    A relation goes where its own rows are: with the CC BY files if any row is
    theirs, else with the share-alike ones, else with ICTRP's. Its other rows sit
    in their own folders and point at it by id.
    """
    with Session(get_engine(), expire_on_commit=False) as session:
        entities = {e.id: e for e in session.exec(select(GraphEntity)).all()}
        edges = list(session.exec(select(GraphEdge).order_by(col(GraphEdge.id))).all())

    folders: dict[str, dict[str, list[dict[str, Any]]]] = {
        terms: {"relations": [], "evidence": []} for terms in ("main", "share_alike", "ictrp")
    }
    dropped = quoted = 0
    for edge in edges:
        kept = [
            e
            for e in edge.evidence or []
            if not str(e.get("source_id", "")).startswith("drugbank:")
        ]
        dropped += len(edge.evidence or []) - len(kept)
        rows: dict[str, list[dict[str, Any]]] = {terms: [] for terms in folders}
        for item in kept:
            row = _evidence_row(edge.id, item, licences)
            quoted += row["text"] is not None
            rows[_terms(item)].append(row)
        home = next((terms for terms in folders if rows[terms]), None)
        if home is None:
            continue
        folders[home]["relations"].append(_relation_row(edge, len(rows[home])))
        for terms, part in rows.items():
            folders[terms]["evidence"] += part

    def ends(terms: str) -> set[int]:
        return {i for r in folders[terms]["relations"] for i in (r["subject_id"], r["object_id"])}

    in_main = ends("main")
    folders["main"]["entities"] = [
        _release_entity(entities[i], strip_ictrp=True) for i in sorted(in_main)
    ]
    folders["share_alike"]["entities"] = [
        _release_entity(entities[i], strip_ictrp=True)
        for i in sorted(ends("share_alike") - in_main)
    ]
    folders["ictrp"]["entities"] = [
        _release_entity(entities[i]) for i in sorted(ends("ictrp") - in_main)
    ]
    for folder, tables in (
        (out, folders["main"]),
        (out / "share-alike", folders["share_alike"]),
        (out / "ictrp", folders["ictrp"]),
    ):
        folder.mkdir(parents=True, exist_ok=True)
        for name, table in tables.items():
            path = folder / f"{name}.jsonl"
            if not table:
                # Every entity the share-alike relations name is also in the
                # main file, so that table is empty: leave it out, never stale.
                path.unlink(missing_ok=True)
                continue
            with path.open("w", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in table)
    return ReleaseStats(
        entities=len(folders["main"]["entities"]),
        relations=len(folders["main"]["relations"]),
        evidence=len(folders["main"]["evidence"]),
        quoted=quoted,
        ictrp_relations=len(folders["ictrp"]["relations"]),
        ictrp_evidence=len(folders["ictrp"]["evidence"]),
        share_alike_relations=len(folders["share_alike"]["relations"]),
        share_alike_evidence=len(folders["share_alike"]["evidence"]),
        dropped=dropped,
    )


def _terms(item: dict[str, Any]) -> str:
    """Whose terms an evidence row is published under: main, share_alike or ictrp."""
    if str(item.get("source_id", "")).startswith("ictrp:"):
        return "ictrp"
    if item.get("source_type") == "chembl":
        return "share_alike"
    return "main"


def _evidence_row(
    relation_id: int | None, item: dict[str, Any], licences: dict[str, str | None]
) -> dict[str, Any]:
    source = str(item.get("source_id", ""))
    scheme, _, ident = source.partition(":")
    snippet = item.get("snippet")
    if scheme == "pmid":
        licence = licences.get(ident)
        if licence not in _OPEN_LICENCES:
            licence = None
    elif item.get("source_type") == "chembl":
        licence = _SHARE_ALIKE.get(str(item.get("section")))
    else:
        licence = _GOVERNMENT_TEXT.get(scheme)
    kind = str(item.get("source_type", ""))
    return {
        "relation_id": relation_id,
        "source": source,
        "source_kind": "relation_extractor" if kind == _MODEL else kind,
        "relation_label": item.get("relation"),
        "score": item.get("score"),
        "section": item.get("section"),
        "text": snippet if snippet and licence else None,
        "text_licence": licence if snippet and licence else None,
        "details": json.dumps(
            {k: v for k, v in item.items() if k not in _COLUMNS}, ensure_ascii=False
        ),
    }


def _relation_row(edge: GraphEdge, evidence: int) -> dict[str, Any]:
    method = "relation_extractor" if edge.extraction_method == _MODEL else edge.extraction_method
    return {
        "id": edge.id,
        "subject_id": edge.subject_id,
        "predicate": str(
            edge.predicate.value if hasattr(edge.predicate, "value") else edge.predicate
        ),
        "object_id": edge.object_id,
        "confidence": edge.confidence,
        "claim": str(edge.claim.value if hasattr(edge.claim, "value") else edge.claim),
        "causal_level": edge.causal_level,
        "extraction_method": method,
        "evidence_count": evidence,
    }


def _release_entity(entity: GraphEntity, *, strip_ictrp: bool = False) -> dict[str, Any]:
    row = _entity_to_dict(entity)
    # A trial registered only with ICTRP is named by WHO's record; its titles stay in ictrp/.
    if strip_ictrp and set(row["external_ids"]) == {"ictrp"}:
        row["aliases"] = []
    return row
