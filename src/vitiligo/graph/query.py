"""Query helpers for the vitiligo knowledge graph."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import desc, func, or_
from sqlmodel import Session, select

from vitiligo.graph.normalize import VITILIGO_ENTITY_KEY, normalize_entity_key
from vitiligo.storage import get_engine
from vitiligo.storage.models import EntityKind, GraphEdge, GraphEntity


@dataclass(frozen=True)
class GraphStatsRow:
    label: str
    count: int


@dataclass(frozen=True)
class GraphEdgeView:
    id: int
    subject_kind: str
    subject_name: str
    subject_key: str
    predicate: str
    object_kind: str
    object_name: str
    object_key: str
    confidence: float
    extraction_method: str
    evidence_count: int


def summarize_graph() -> dict[str, list[GraphStatsRow]]:
    with Session(get_engine(), expire_on_commit=False) as session:
        entities = int(session.exec(select(func.count()).select_from(GraphEntity)).one() or 0)
        edges = int(session.exec(select(func.count()).select_from(GraphEdge)).one() or 0)
        kind_rows = session.exec(
            select(GraphEntity.kind, func.count())
            .group_by(GraphEntity.kind)
            .order_by(desc(func.count()))
        ).all()
        predicate_rows = session.exec(
            select(GraphEdge.predicate, func.count())
            .group_by(GraphEdge.predicate)
            .order_by(desc(func.count()))
        ).all()
        method_rows = session.exec(
            select(GraphEdge.extraction_method, func.count())
            .group_by(GraphEdge.extraction_method)
            .order_by(desc(func.count()))
        ).all()

    return {
        "total": [
            GraphStatsRow(label="entities", count=entities),
            GraphStatsRow(label="edges", count=edges),
        ],
        "by_kind": [
            GraphStatsRow(label=str(kind.value if hasattr(kind, "value") else kind), count=int(count))
            for kind, count in kind_rows
        ],
        "by_predicate": [
            GraphStatsRow(
                label=str(pred.value if hasattr(pred, "value") else pred),
                count=int(count),
            )
            for pred, count in predicate_rows
        ],
        "by_method": [
            GraphStatsRow(label=str(method or "unknown"), count=int(count))
            for method, count in method_rows
        ],
    }


def search_entities(query: str, *, limit: int = 25) -> list[GraphEntity]:
    needle = query.strip()
    if not needle:
        return []
    key = normalize_entity_key(needle)
    pattern = f"%{needle.lower()}%"
    with Session(get_engine(), expire_on_commit=False) as session:
        stmt = (
            select(GraphEntity)
            .where(
                or_(
                    GraphEntity.key == key,
                    GraphEntity.name.ilike(pattern),  # type: ignore[union-attr]
                )
            )
            .order_by(GraphEntity.name)
            .limit(limit)
        )
        return list(session.exec(stmt).all())


def get_neighbors(
    name_or_key: str,
    *,
    hops: int = 1,
    limit: int = 50,
) -> list[GraphEdgeView]:
    hops = max(1, min(hops, 2))
    key = normalize_entity_key(name_or_key)
    with Session(get_engine(), expire_on_commit=False) as session:
        entity = session.exec(
            select(GraphEntity).where(
                or_(GraphEntity.key == key, GraphEntity.name.ilike(name_or_key))  # type: ignore[union-attr]
            )
        ).first()
        if entity is None or entity.id is None:
            return []

        frontier = {entity.id}
        seen_edges: set[int] = set()
        views: list[GraphEdgeView] = []

        for _ in range(hops):
            if not frontier:
                break
            stmt = (
                select(GraphEdge)
                .where(
                    or_(
                        GraphEdge.subject_id.in_(frontier),  # type: ignore[union-attr]
                        GraphEdge.object_id.in_(frontier),  # type: ignore[union-attr]
                    )
                )
                .order_by(desc(GraphEdge.confidence))
                .limit(limit * 2)
            )
            batch = list(session.exec(stmt).all())
            next_frontier: set[int] = set()
            for edge in batch:
                if edge.id in seen_edges:
                    continue
                seen_edges.add(edge.id)  # type: ignore[arg-type]
                view = _edge_to_view(session, edge)
                if view:
                    views.append(view)
                next_frontier.add(edge.subject_id)
                next_frontier.add(edge.object_id)
            frontier = next_frontier - {entity.id}

        views.sort(key=lambda v: v.confidence, reverse=True)
        return views[:limit]


def retrieve_graph_for_hypothesize(intent: str, *, limit: int = 12) -> list[GraphEdgeView]:
    """Return high-confidence vitiligo-connected edges for the Hypothesize prompt."""
    tokens = _intent_tokens(intent)
    with Session(get_engine(), expire_on_commit=False) as session:
        vitiligo = session.exec(
            select(GraphEntity).where(
                GraphEntity.kind == EntityKind.DISEASE,
                GraphEntity.key == VITILIGO_ENTITY_KEY,
            )
        ).first()
        if vitiligo is None or vitiligo.id is None:
            return []

        stmt = (
            select(GraphEdge)
            .where(
                or_(
                    GraphEdge.subject_id == vitiligo.id,
                    GraphEdge.object_id == vitiligo.id,
                )
            )
            .order_by(desc(GraphEdge.confidence))
            .limit(limit * 4)
        )
        edges = list(session.exec(stmt).all())
        views = [_edge_to_view(session, e) for e in edges]
        views = [v for v in views if v is not None]

    def _score(view: GraphEdgeView) -> float:
        text = f"{view.subject_name} {view.object_name} {view.predicate}".lower()
        overlap = sum(1 for t in tokens if t in text)
        return view.confidence + 0.05 * overlap

    views.sort(key=_score, reverse=True)
    return views[:limit]


def _edge_to_view(session: Session, edge: GraphEdge) -> GraphEdgeView | None:
    if edge.id is None:
        return None
    subject = session.get(GraphEntity, edge.subject_id)
    obj = session.get(GraphEntity, edge.object_id)
    if subject is None or obj is None:
        return None
    pred = edge.predicate.value if hasattr(edge.predicate, "value") else str(edge.predicate)
    subj_kind = subject.kind.value if hasattr(subject.kind, "value") else str(subject.kind)
    obj_kind = obj.kind.value if hasattr(obj.kind, "value") else str(obj.kind)
    return GraphEdgeView(
        id=edge.id,
        subject_kind=subj_kind,
        subject_name=subject.name,
        subject_key=subject.key,
        predicate=pred,
        object_kind=obj_kind,
        object_name=obj.name,
        object_key=obj.key,
        confidence=edge.confidence,
        extraction_method=edge.extraction_method,
        evidence_count=len(edge.evidence or []),
    )


def _intent_tokens(intent: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", intent.lower()) if t not in _STOPWORDS}


_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "vitiligo",
        "stop",
        "drive",
        "active",
        "non",
        "segmental",
        "repigmentation",
    }
)
