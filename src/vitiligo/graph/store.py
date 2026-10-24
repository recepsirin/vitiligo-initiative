"""Upsert helpers for graph entities and edges."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from vitiligo.graph.normalize import normalize_entity_key
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity, RelationKind


def upsert_entity(
    session: Session,
    *,
    kind: EntityKind,
    name: str,
    aliases: list[str] | None = None,
    external_ids: dict[str, str] | None = None,
) -> GraphEntity:
    """Insert or update a canonical graph entity."""
    key = normalize_entity_key(name)
    display = name.strip() or key
    stmt = select(GraphEntity).where(GraphEntity.kind == kind, GraphEntity.key == key)
    existing = session.exec(stmt).first()

    merged_aliases = list(dict.fromkeys([display, *(aliases or [])]))[:30]
    merged_external = dict(external_ids or {})

    if existing is None:
        entity = GraphEntity(
            kind=kind,
            key=key,
            name=display,
            aliases=merged_aliases,
            external_ids=merged_external,
        )
        session.add(entity)
        session.flush()
        return entity

    alias_set = list(dict.fromkeys([*(existing.aliases or []), *merged_aliases]))[:30]
    existing.aliases = alias_set
    existing.name = display if len(display) >= len(existing.name) else existing.name
    existing.external_ids = {**(existing.external_ids or {}), **merged_external}
    existing.updated_at = datetime.now(UTC)
    session.add(existing)
    session.flush()
    return existing


def upsert_edge(
    session: Session,
    *,
    subject: GraphEntity,
    predicate: RelationKind,
    obj: GraphEntity,
    confidence: float,
    extraction_method: str,
    evidence: dict[str, Any],
    claim: ClaimKind = ClaimKind.ASSERTED,
    causal_level: str | None = None,
) -> tuple[GraphEdge, bool]:
    """Insert or merge an edge. Returns (edge, inserted).

    ``claim`` says whether the relation was measured or is asserted by a
    source, and ``causal_level`` places an observed one on the causal ladder.
    The default is ``asserted``, because a relation read out of a database is
    that database's statement until evidence is attached to it.
    """
    stmt = select(GraphEdge).where(
        GraphEdge.subject_id == subject.id,
        GraphEdge.predicate == predicate,
        GraphEdge.object_id == obj.id,
    )
    existing = session.exec(stmt).first()
    if existing is None:
        edge = GraphEdge(
            subject_id=subject.id,  # type: ignore[arg-type]
            predicate=predicate,
            object_id=obj.id,  # type: ignore[arg-type]
            confidence=confidence,
            extraction_method=extraction_method,
            evidence=[evidence],
            claim=claim,
            causal_level=causal_level,
        )
        session.add(edge)
        session.flush()
        return edge, True

    existing.confidence = max(existing.confidence, confidence)
    # An edge that was only asserted becomes observed once a measurement
    # arrives; evidence never downgrades it back.
    if claim == ClaimKind.OBSERVED and existing.claim != ClaimKind.OBSERVED:
        existing.claim = ClaimKind.OBSERVED
        existing.causal_level = causal_level
    elif claim == ClaimKind.OBSERVED and causal_level is not None:
        existing.causal_level = _stronger_level(existing.causal_level, causal_level)
    merged = list(existing.evidence or [])
    if not _evidence_seen(merged, evidence):
        merged.append(evidence)
    existing.evidence = merged[-20:]
    existing.updated_at = datetime.now(UTC)
    session.add(existing)
    session.flush()
    return existing, False


def _stronger_level(current: str | None, incoming: str) -> str:
    """The higher rung of the two, so better evidence raises an edge."""
    from vitiligo.mechanisms.schema import causal_rank

    if current is None:
        return incoming
    return incoming if causal_rank(incoming) > causal_rank(current) else current


def get_entity_by_kind_key(
    session: Session,
    kind: EntityKind,
    key: str,
) -> GraphEntity | None:
    return session.exec(
        select(GraphEntity).where(GraphEntity.kind == kind, GraphEntity.key == key)
    ).first()


def _evidence_seen(existing: list[dict[str, Any]], item: dict[str, Any]) -> bool:
    sig = (item.get("source_type"), item.get("source_id"), item.get("snippet"))
    for row in existing:
        if (row.get("source_type"), row.get("source_id"), row.get("snippet")) == sig:
            return True
    return False
