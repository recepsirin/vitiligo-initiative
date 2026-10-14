"""Ingestion → storage → query round-trip on real parser fixtures.

Proves that parsed registry records are stored in a shape our search layer
can actually find — the full path from raw XML/JSON to clinician query.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session
from tests.helpers.paths import FIXTURES_DIR

from vitiligo.sources.ctgov import parse_ctgov_study
from vitiligo.sources.ictrp import iter_ictrp_trials
from vitiligo.storage import get_engine
from vitiligo.trials import TrialFilter, list_trials

pytestmark = pytest.mark.integration

ICTRP_FIXTURE = FIXTURES_DIR / "ictrp_vitiligo_sample.xml"
CTGOV_FIXTURE = FIXTURES_DIR / "ctgov_sample.json"


def _load_ctgov_studies() -> list[dict]:
    return json.loads(CTGOV_FIXTURE.read_text())["studies"]


@pytest.fixture
def ictrp_trials_db(test_db_path: Path) -> Path:
    trials = list(iter_ictrp_trials(ICTRP_FIXTURE))
    with Session(get_engine(), expire_on_commit=False) as session:
        for trial in trials:
            session.add(trial)
        session.commit()
    return test_db_path


def test_ingested_ictrp_ruxolitinib_findable_by_intervention(ictrp_trials_db) -> None:
    hits = list_trials(TrialFilter(query="ruxolitinib", limit=10))
    ids = {t.source_id for t in hits}
    assert "ChiCTR2300070001" in ids


def test_ingested_ictrp_tacrolimus_findable_by_intervention(ictrp_trials_db) -> None:
    hits = list_trials(TrialFilter(query="tacrolimus", limit=10))
    ids = {t.source_id for t in hits}
    assert "ISRCTN99887766" in ids


def test_ingested_ictrp_filter_by_source(ictrp_trials_db) -> None:
    from vitiligo.storage import TrialSourceKind

    hits = list_trials(TrialFilter(query="vitiligo", sources=(TrialSourceKind.ICTRP,), limit=10))
    assert len(hits) == 3


@pytest.fixture
def ctgov_trials_db(test_db_path: Path) -> Path:
    studies = _load_ctgov_studies()
    with Session(get_engine(), expire_on_commit=False) as session:
        for study in studies:
            trial = parse_ctgov_study(study)
            if trial is not None:
                session.add(trial)
        session.commit()
    return test_db_path


def test_ingested_ctgov_excimer_trial_findable(ctgov_trials_db) -> None:
    hits = list_trials(TrialFilter(query="excimer", limit=10))
    ids = {t.source_id for t in hits}
    assert "NCT03384459" in ids


def test_ingested_ctgov_cxcl9_trial_findable(ctgov_trials_db) -> None:
    hits = list_trials(TrialFilter(query="CXCL9", limit=10))
    ids = {t.source_id for t in hits}
    assert "NCT05569096" in ids


def test_ingested_ctgov_filter_by_source(ctgov_trials_db) -> None:
    from vitiligo.storage import TrialSourceKind

    hits = list_trials(TrialFilter(query="vitiligo", sources=(TrialSourceKind.CTGOV,), limit=10))
    assert len(hits) == len(_load_ctgov_studies())


def _store_document_with_embedding(title: str, abstract: str) -> int:
    from vitiligo.storage import Document, Embedding, SourceKind

    with Session(get_engine(), expire_on_commit=False) as session:
        doc = Document(source=SourceKind.PUBMED, source_id="555", title=title, abstract=abstract)
        session.add(doc)
        session.flush()
        assert doc.id is not None
        session.add(
            Embedding(
                document_id=doc.id, model="m", scope="title_abstract", dim=1, vector=b"\0" * 4
            )
        )
        session.commit()
        return doc.id


def _embedding_count(doc_id: int) -> int:
    from sqlmodel import select

    from vitiligo.storage import Embedding

    with Session(get_engine()) as session:
        return len(session.exec(select(Embedding).where(Embedding.document_id == doc_id)).all())


def test_reingest_with_changed_text_drops_stale_embedding(test_db_path: Path) -> None:
    """A corrected title/abstract must be re-embedded, not keep its old vector."""
    from vitiligo.ingest.pipeline import _upsert_document
    from vitiligo.storage import Document, SourceKind

    doc_id = _store_document_with_embedding("Lactate Enhances CD8", "Old abstract.")

    with Session(get_engine(), expire_on_commit=False) as session:
        same = Document(
            source=SourceKind.PUBMED,
            source_id="555",
            title="Lactate Enhances CD8",
            abstract="Old abstract.",
            journal="J",
        )
        assert _upsert_document(session, same) == (0, 1)
        session.commit()
    assert _embedding_count(doc_id) == 1  # metadata-only change keeps the vector

    with Session(get_engine(), expire_on_commit=False) as session:
        fixed = Document(
            source=SourceKind.PUBMED,
            source_id="555",
            title="Lactate Enhances CD8+ T Cell Cytotoxicity",
            abstract="Old abstract.",
        )
        assert _upsert_document(session, fixed) == (0, 1)
        session.commit()
    assert _embedding_count(doc_id) == 0
