"""Offline tests for the WHO ICTRP XML parser."""

from __future__ import annotations

from pathlib import Path

from tests.helpers.paths import FIXTURES_DIR

from vitiligo.sources.ictrp import (
    count_ictrp_records,
    extract_cross_registry_keys,
    iter_ictrp_trials,
    parse_ictrp_record,
    should_skip_ictrp_record,
)
from vitiligo.storage.models import TrialSourceKind

FIXTURE = FIXTURES_DIR / "ictrp_vitiligo_sample.xml"


def test_count_and_iter_fixture() -> None:
    assert count_ictrp_records(FIXTURE) == 3
    trials = list(iter_ictrp_trials(FIXTURE))
    assert len(trials) == 3
    assert {t.source_id for t in trials} == {
        "ChiCTR2300070001",
        "NCT03099304",
        "ISRCTN99887766",
    }


def test_parse_chictr_record_fields() -> None:
    trials = list(iter_ictrp_trials(FIXTURE))
    chictr = next(t for t in trials if t.source_id == "ChiCTR2300070001")
    assert chictr.source == TrialSourceKind.ICTRP
    assert chictr.status == "RECRUITING"
    assert chictr.phases == ["PHASE2"]
    assert chictr.study_type == "INTERVENTIONAL"
    assert "Vitiligo" in chictr.conditions
    assert chictr.interventions[0]["name"] == "Ruxolitinib cream 1.5%"
    assert chictr.countries == ["China"]
    assert chictr.enrollment_count == 120
    assert chictr.minimum_age == "18 Years"
    assert chictr.has_results is False


def test_extract_cross_registry_keys() -> None:
    keys = extract_cross_registry_keys(
        "ChiCTR2300070001",
        ["NCT03099304", "2024-001234-56-01"],
    )
    assert (TrialSourceKind.CTGOV, "NCT03099304") in keys
    assert (TrialSourceKind.EUCTR, "2024-001234-56-01") in keys


def test_should_skip_ctgov_and_existing_duplicates() -> None:
    trials = list(iter_ictrp_trials(FIXTURE))
    ctgov = next(t for t in trials if t.source_id == "NCT03099304")
    isrctn = next(t for t in trials if t.source_id == "ISRCTN99887766")

    existing = {("ctgov", "NCT03099304")}
    assert should_skip_ictrp_record(ctgov, skip_duplicates=True, existing_keys=existing)
    assert not should_skip_ictrp_record(isrctn, skip_duplicates=True, existing_keys=existing)


def test_parse_single_record_root() -> None:
    from lxml import etree

    trials = list(iter_ictrp_trials(FIXTURE))
    root = etree.fromstring(Path(FIXTURE).read_bytes())
    first_record = root.find(".//trial")
    assert first_record is not None
    reparsed = parse_ictrp_record(first_record)
    assert reparsed is not None
    assert reparsed.source_id == trials[0].source_id
