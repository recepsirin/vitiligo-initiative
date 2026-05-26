"""Tests for GEO DataSets metadata parsing."""

from __future__ import annotations

import json

from tests.helpers.paths import FIXTURES_DIR

from vitiligo.sources.geo import parse_geo_summary
from vitiligo.storage.models import SourceKind

FIXTURE = FIXTURES_DIR / "geo_summary_sample.json"


def test_parse_geo_summary_maps_fields() -> None:
    record = json.loads(FIXTURE.read_text())
    doc = parse_geo_summary(record)
    assert doc is not None
    assert doc.source == SourceKind.GEO
    assert doc.source_id == "GSE326094"
    assert doc.title is not None
    assert "laminin" in doc.title.lower()
    assert doc.abstract is not None
    assert "melanocytes" in doc.abstract
    assert doc.year == 2026
    assert doc.journal == "NCBI GEO"
    assert "Homo sapiens" in doc.keywords
    assert "GEO GSE" in doc.publication_types
    assert doc.raw_metadata["geo_uid"] == "200326094"
    assert doc.raw_metadata["sample_count"] == 1


def test_parse_geo_summary_rejects_empty_record() -> None:
    assert parse_geo_summary({}) is None
