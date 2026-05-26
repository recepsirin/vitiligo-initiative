#!/usr/bin/env python3
"""Build a minimal SQLite corpus for CI confidence regression tests.

Reads ``tests/fixtures/regression/documents.json`` and ``trials.json``,
creates a fresh database, and embeds all documents. The result is small
enough to build on every CI run (~8 papers + 3 trials + embeddings).

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
    from vitiligo.storage import Document, Trial, TrialSourceKind, init_db, get_engine
    from vitiligo.storage.models import SourceKind

    init_db()

    doc_rows = _load_json("documents.json")
    trial_rows = _load_json("trials.json")

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
        session.commit()

    stats = embed_documents()
    print(
        f"Built {output} — {len(doc_rows)} documents, {len(trial_rows)} trials, "
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
