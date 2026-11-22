"""One drug, one entity: merge the drug entities one MeSH concept names.

A paper's chemical is named by its MeSH heading, and a prior or a trial by the
name its source gives, so one drug could hold several entities. Ritlecitinib's
papers sat on "PF-06651600", MeSH's heading for it, apart from the
"ritlecitinib" the trials name, and the candidate report found no paper for it;
32 MeSH concepts were split so. MeSH lists every name a concept goes by, so a
drug entity whose name is one of a concept's terms is that concept.

The merged entity keeps the name another source gave it (a paper is the
weakest source in the graph), and the other names become its aliases.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlmodel import Session, col, or_, select

from vitiligo.graph.normalize import normalize_entity_key
from vitiligo.graph.store import _evidence_seen, _stronger_level
from vitiligo.sources.mesh import MeshRecord
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity

# A term this short ("MTX", "CsA") is an abbreviation more than a name.
_MIN_TERM = 4


def _from_papers(row: dict[str, Any]) -> bool:
    method = str(row.get("source_type") or "")
    return method in {"pubtator3", "relation_extractor"} or method.startswith("biored-")


def mesh_synonym_groups(
    drugs: list[GraphEntity], mesh: dict[str, MeshRecord]
) -> list[list[GraphEntity]]:
    """Drug entities that are one MeSH concept, each group of two or more.

    An entity joins a concept's group when its name is one of the concept's
    terms, or when it holds the concept's identifier. One that two concepts
    would claim, or that holds another concept's identifier, joins neither.
    """
    by_key = {entity.key: entity for entity in drugs}
    claims: dict[int, set[str]] = defaultdict(set)
    members: dict[str, set[int]] = defaultdict(set)
    for entity in drugs:
        ui = (entity.external_ids or {}).get("mesh")
        if not ui:
            continue
        assert entity.id is not None
        members[ui].add(entity.id)
        record = mesh.get(ui)
        for term in record.terms if record else ():
            other = by_key.get(normalize_entity_key(term))
            if other is None or other.id == entity.id or len(term) < _MIN_TERM:
                continue
            assert other.id is not None
            claims[other.id].add(ui)
    for entity_id, uis in claims.items():
        if len(uis) != 1:
            continue  # two concepts name it
        held = (next(e for e in drugs if e.id == entity_id).external_ids or {}).get("mesh")
        if held and held not in uis:
            continue  # it is another concept
        members[next(iter(uis))].add(entity_id)
    by_id = {entity.id: entity for entity in drugs}
    return [
        sorted((by_id[i] for i in ids), key=lambda e: e.id or 0)
        for _, ids in sorted(members.items())
        if len(ids) > 1
    ]


def _keeper(session: Session, group: list[GraphEntity]) -> GraphEntity:
    """The entity another source named; then the one with the most relations."""

    def rank(entity: GraphEntity) -> tuple[bool, int, int]:
        edges = _edges_of(session, entity)
        named_elsewhere = any(
            not _from_papers(row) for edge in edges for row in edge.evidence or []
        )
        return (named_elsewhere, len(edges), -(entity.id or 0))

    return max(group, key=rank)


def _edges_of(session: Session, entity: GraphEntity) -> list[GraphEdge]:
    touching = or_(col(GraphEdge.subject_id) == entity.id, col(GraphEdge.object_id) == entity.id)
    return list(session.exec(select(GraphEdge).where(touching)).all())


def merge_entity(session: Session, keep: GraphEntity, drop: GraphEntity) -> None:
    """Fold ``drop`` into ``keep``: its relations, evidence, names and identifiers."""
    for edge in _edges_of(session, drop):
        subject = keep.id if edge.subject_id == drop.id else edge.subject_id
        obj = keep.id if edge.object_id == drop.id else edge.object_id
        if subject == obj:
            session.delete(edge)  # a relation between two names of one drug
            continue
        held = session.exec(
            select(GraphEdge).where(
                GraphEdge.subject_id == subject,
                GraphEdge.predicate == edge.predicate,
                GraphEdge.object_id == obj,
            )
        ).first()
        if held is None:
            edge.subject_id, edge.object_id = subject, obj  # type: ignore[assignment]
            session.add(edge)
            continue
        merged = list(held.evidence or [])
        for row in edge.evidence or []:
            if not _evidence_seen(merged, row):
                merged.append(row)
        held.evidence = merged
        held.confidence = max(held.confidence, edge.confidence)
        if edge.claim == ClaimKind.OBSERVED and held.claim != ClaimKind.OBSERVED:
            held.claim, held.causal_level = ClaimKind.OBSERVED, edge.causal_level
        elif edge.claim == ClaimKind.OBSERVED and edge.causal_level is not None:
            held.causal_level = _stronger_level(held.causal_level, edge.causal_level)
        session.add(held)
        session.delete(edge)
    session.flush()
    names = [keep.name, *(keep.aliases or []), drop.name, *(drop.aliases or [])]
    keep.aliases = list(dict.fromkeys(name for name in names if name))[:30]
    keep.external_ids = {**(drop.external_ids or {}), **(keep.external_ids or {})}
    session.add(keep)
    session.delete(drop)
    session.flush()


def merge_mesh_synonyms(session: Session, mesh: dict[str, MeshRecord]) -> int:
    """Merge every group of drug entities one MeSH concept names; return how many went."""
    drugs = list(session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.DRUG)))
    merged = 0
    for group in mesh_synonym_groups(drugs, mesh):
        keep = _keeper(session, group)
        for entity in group:
            if entity.id != keep.id:
                merge_entity(session, keep, entity)
                merged += 1
    return merged
