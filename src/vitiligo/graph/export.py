"""Export the knowledge graph for expert review and archival snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc
from sqlmodel import Session, select

from vitiligo import __version__
from vitiligo.graph.query import GraphEdgeView, _edge_to_view, summarize_graph
from vitiligo.storage import get_engine
from vitiligo.storage.models import GraphEdge, GraphEntity


def export_graph_snapshot(*, edge_limit: int | None = None) -> dict[str, Any]:
    """Return the full graph (entities + edges) as a JSON-serializable dict."""
    summary = summarize_graph()
    stats = {
        row.label: row.count
        for group in summary.values()
        for row in group
    }

    with Session(get_engine(), expire_on_commit=False) as session:
        entities = list(
            session.exec(
                select(GraphEntity).order_by(GraphEntity.kind, GraphEntity.name)
            ).all()
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
        "evidence_count": view.evidence_count,
        "evidence": list(edge.evidence or [])[:5],
    }
