"""LLM-assisted entity and relation extraction from document abstracts."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session, select

from vitiligo.graph.normalize import coerce_entity_kind, coerce_relation_kind, normalize_entity_key
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.logging import get_logger
from vitiligo.reasoning.llm import LLMClient, LLMUnavailable
from vitiligo.storage import Document, session_scope
from vitiligo.storage.models import EntityKind, GraphExtraction

logger = get_logger(__name__)

_EXTRACT_SYSTEM = """You extract biomedical entities and relations from vitiligo research abstracts.

Output ONLY valid JSON with this schema:
{
  "entities": [
    {"kind": "drug|target|disease|pathway|mechanism|biomarker", "name": "string"}
  ],
  "relations": [
    {
      "subject": "entity name exactly as in entities",
      "predicate": "treats|targets|inhibits|activates|associated_with",
      "object": "entity name exactly as in entities",
      "confidence": 0.0-1.0
    }
  ]
}

Rules:
- Include only statements explicitly supported by the abstract text.
- Do not invent drugs, targets, or mechanisms.
- Prefer precise entity names from the text.
- confidence reflects how directly the abstract states the relation."""


@dataclass(frozen=True)
class GraphExtractStats:
    documents_processed: int
    documents_failed: int
    documents_skipped: int
    entities_added: int
    edges_inserted: int
    edges_merged: int


def parse_llm_extraction(text: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Parse LLM JSON output into entity and relation lists."""
    payload = _parse_json(text)
    if not isinstance(payload, dict):
        return [], []
    entities = payload.get("entities", [])
    relations = payload.get("relations", [])
    entity_rows = [e for e in entities if isinstance(e, dict) and e.get("name")]
    relation_rows = [r for r in relations if isinstance(r, dict) and r.get("subject") and r.get("object")]
    return entity_rows, relation_rows


def extract_graph_from_documents(
    *,
    limit: int = 50,
    llm: LLMClient | None = None,
) -> GraphExtractStats:
    """Run LLM extraction over documents not yet processed."""
    processed = failed = skipped = 0
    entities_added = 0
    inserted = merged = 0

    with session_scope() as session:
        pending = _pending_documents(session, limit=limit)

    client: LLMClient | None = None
    for doc in pending:
        if not (doc.abstract or "").strip():
            _record_extraction(doc.id, status="skipped", error="no abstract")  # type: ignore[arg-type]
            skipped += 1
            continue

        try:
            if client is None:
                client = llm or LLMClient()
            entity_rows, relation_rows = _extract_one(client, doc)
        except LLMUnavailable:
            raise
        except Exception as exc:
            logger.warning("Graph extraction failed for doc %s: %s", doc.id, exc)
            _record_extraction(doc.id, status="failed", error=str(exc)[:500])  # type: ignore[arg-type]
            failed += 1
            continue

        ent_n, ins_n, mer_n = _apply_extraction(doc, entity_rows, relation_rows)
        entities_added += ent_n
        inserted += ins_n
        merged += mer_n
        _record_extraction(
            doc.id,  # type: ignore[arg-type]
            status="completed",
            entity_count=ent_n,
            edge_count=ins_n + mer_n,
        )
        processed += 1

    return GraphExtractStats(
        documents_processed=processed,
        documents_failed=failed,
        documents_skipped=skipped,
        entities_added=entities_added,
        edges_inserted=inserted,
        edges_merged=merged,
    )


def _pending_documents(session: Session, *, limit: int) -> list[Document]:
    done_ids = select(GraphExtraction.document_id).where(GraphExtraction.status == "completed")
    stmt = (
        select(Document)
        .where(Document.abstract.isnot(None))  # type: ignore[union-attr]
        .where(Document.abstract != "")
        .where(Document.id.notin_(done_ids))  # type: ignore[union-attr]
        .order_by(Document.year.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def _extract_one(client: LLMClient, doc: Document) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    src = doc.source.value if hasattr(doc.source, "value") else str(doc.source)
    user = (
        f"SOURCE: {src}:{doc.source_id}\n"
        f"TITLE: {doc.title or '(no title)'}\n\n"
        f"ABSTRACT:\n{(doc.abstract or '').strip()}"
    )
    response = client.complete(
        system=_EXTRACT_SYSTEM,
        user=user,
        max_tokens=2000,
        temperature=0.1,
    )
    return parse_llm_extraction(response.text)


def _apply_extraction(
    doc: Document,
    entity_rows: list[dict[str, object]],
    relation_rows: list[dict[str, object]],
) -> tuple[int, int, int]:
    entities_added = 0
    inserted = 0
    merged = 0
    name_to_entity: dict[str, object] = {}
    src = doc.source.value if hasattr(doc.source, "value") else str(doc.source)
    doc_ref = f"{src}:{doc.source_id}"

    with session_scope() as session:
        for row in entity_rows:
            kind = coerce_entity_kind(str(row.get("kind", "")))
            name = str(row.get("name", "")).strip()
            if not kind or not name:
                continue
            entity = upsert_entity(session, kind=kind, name=name)
            key = normalize_entity_key(name)
            if key not in name_to_entity:
                entities_added += 1
            name_to_entity[key] = entity
            name_to_entity[name.lower()] = entity

        for row in relation_rows:
            predicate = coerce_relation_kind(str(row.get("predicate", "")))
            if predicate is None:
                continue
            subject_name = str(row.get("subject", "")).strip()
            object_name = str(row.get("object", "")).strip()
            if not subject_name or not object_name:
                continue

            subject = _resolve_entity(session, name_to_entity, subject_name)
            obj = _resolve_entity(session, name_to_entity, object_name)
            if subject is None or obj is None:
                continue

            try:
                conf = float(row.get("confidence", 0.55))
            except (TypeError, ValueError):
                conf = 0.55
            conf = max(0.0, min(1.0, conf))

            _, ins = upsert_edge(
                session,
                subject=subject,
                predicate=predicate,
                obj=obj,
                confidence=conf,
                extraction_method="llm",
                evidence={
                    "source_type": "document",
                    "source_id": doc_ref,
                    "document_id": doc.id,
                    "title": doc.title,
                },
            )
            inserted += int(ins)
            merged += int(not ins)

    return entities_added, inserted, merged


def _resolve_entity(
    session: Session,
    cache: dict[str, object],
    name: str,
) -> object | None:
    key = normalize_entity_key(name)
    if key in cache:
        return cache[key]
    if name.lower() in cache:
        return cache[name.lower()]
    kind = EntityKind.BIOMARKER
    entity = upsert_entity(session, kind=kind, name=name)
    cache[key] = entity
    cache[name.lower()] = entity
    return entity


def _record_extraction(
    document_id: int,
    *,
    status: str,
    entity_count: int = 0,
    edge_count: int = 0,
    error: str | None = None,
) -> None:
    with session_scope() as session:
        existing = session.exec(
            select(GraphExtraction).where(GraphExtraction.document_id == document_id)
        ).first()
        if existing is None:
            session.add(
                GraphExtraction(
                    document_id=document_id,
                    status=status,
                    entity_count=entity_count,
                    edge_count=edge_count,
                    error=error,
                )
            )
        else:
            existing.status = status
            existing.entity_count = entity_count
            existing.edge_count = edge_count
            existing.error = error


def _parse_json(text: str) -> object:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
