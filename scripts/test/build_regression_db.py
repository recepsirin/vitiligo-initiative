#!/usr/bin/env python3
"""Build a minimal SQLite corpus for CI confidence regression tests.

Reads ``tests/fixtures/regression/*.json`` (documents, trials, priors, graph),
creates a fresh database, and embeds all documents. Small enough to build on
every CI run (~24 papers + 5 trials + priors/graph seed + embeddings).

Usage:
    python scripts/test/build_regression_db.py
    python scripts/test/build_regression_db.py --output /tmp/vitiligo-regression.db
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "regression"
DEFAULT_OUTPUT = FIXTURE_DIR / "vitiligo-regression.db"


def _load_json(name: str) -> list[dict]:
    path = FIXTURE_DIR / name
    if not path.is_file():
        raise SystemExit(f"fixture missing: {path}")
    return json.loads(path.read_text())


def _load_object(name: str) -> dict:
    path = FIXTURE_DIR / name
    if not path.is_file():
        raise SystemExit(f"fixture missing: {path}")
    return json.loads(path.read_text())


def build_regression_db(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file():
        output.unlink()

    os.environ["VITILIGO_DB_PATH"] = str(output)
    os.environ["VITILIGO_PREWARM_EMBEDDINGS"] = "false"

    import vitiligo.config as cfg
    import vitiligo.storage.db as dbmod

    cfg._settings = None
    dbmod._engine = None

    from sqlmodel import Session

    from vitiligo.embed import embed_documents
    from vitiligo.storage import Document, Trial, TrialSourceKind, get_engine, init_db
    from vitiligo.storage.models import (
        EntityKind,
        GraphEdge,
        GraphEntity,
        Prior,
        PriorKind,
        PriorSourceKind,
        RelationKind,
        SourceKind,
    )

    init_db()

    doc_rows = _load_json("documents.json")
    trial_rows = _load_json("trials.json")
    prior_rows = _load_json("priors.json") if (FIXTURE_DIR / "priors.json").is_file() else []
    graph_spec = _load_object("graph.json") if (FIXTURE_DIR / "graph.json").is_file() else {}

    with Session(get_engine(), expire_on_commit=False) as session:
        for row in doc_rows:
            session.add(
                Document(
                    source=SourceKind(row["source"]),
                    source_id=row["source_id"],
                    title=row.get("title"),
                    abstract=row.get("abstract"),
                    journal=row.get("journal"),
                    year=row.get("year"),
                    doi=row.get("doi"),
                    publication_types=row.get("publication_types") or [],
                    mesh_terms=row.get("mesh_terms") or [],
                    keywords=row.get("keywords") or [],
                )
            )
        for row in trial_rows:
            session.add(
                Trial(
                    source=TrialSourceKind(row["source"]),
                    source_id=row["source_id"],
                    brief_title=row.get("brief_title"),
                    official_title=row.get("official_title"),
                    summary=row.get("summary"),
                    status=row.get("status"),
                    phases=row.get("phases") or [],
                    conditions=row.get("conditions") or [],
                    keywords=row.get("keywords") or [],
                    interventions=row.get("interventions") or [],
                    countries=row.get("countries") or [],
                    has_results=bool(row.get("has_results", False)),
                    last_update_date=row.get("last_update_date"),
                    study_type=row.get("study_type"),
                )
            )
        for row in prior_rows:
            session.add(
                Prior(
                    source=PriorSourceKind(row["source"]),
                    kind=PriorKind(row["kind"]),
                    source_id=row["source_id"],
                    disease_id=row["disease_id"],
                    disease_name=row.get("disease_name"),
                    name=row["name"],
                    description=row.get("description"),
                    score=row.get("score"),
                    clinical_stage=row.get("clinical_stage"),
                    synonyms=row.get("synonyms") or [],
                    mechanisms=row.get("mechanisms") or [],
                    linked_trial_ids=row.get("linked_trial_ids") or [],
                    linked_target_ids=row.get("linked_target_ids") or [],
                    raw_metadata=row.get("raw_metadata") or {},
                )
            )

        entity_ids: dict[tuple[str, str], int] = {}
        for row in graph_spec.get("entities", []):
            entity = GraphEntity(
                kind=EntityKind(row["kind"]),
                key=row["key"],
                name=row["name"],
                aliases=row.get("aliases") or [],
                external_ids=row.get("external_ids") or {},
            )
            session.add(entity)
            session.flush()
            entity_ids[(row["kind"], row["key"])] = entity.id or 0

        for row in graph_spec.get("edges", []):
            subject_id = entity_ids[(row["subject_kind"], row["subject_key"])]
            object_id = entity_ids[(row["object_kind"], row["object_key"])]
            session.add(
                GraphEdge(
                    subject_id=subject_id,
                    predicate=RelationKind(row["predicate"]),
                    object_id=object_id,
                    confidence=float(row.get("confidence", 0.5)),
                    extraction_method=row.get("extraction_method") or "structured",
                )
            )
        session.commit()

    stats = embed_documents()
    graph_entities = len(graph_spec.get("entities", []))
    graph_edges = len(graph_spec.get("edges", []))
    print(
        f"Built {output} — {len(doc_rows)} documents, {len(trial_rows)} trials, "
        f"{len(prior_rows)} priors, {graph_entities} graph entities, {graph_edges} edges, "
        f"{stats.embedded} embeddings",
        file=sys.stderr,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"SQLite output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    build_regression_db(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
