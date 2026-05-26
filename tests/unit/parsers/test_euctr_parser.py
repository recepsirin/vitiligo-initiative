"""Offline tests for the EU CTR / CTIS parser.

Validates the parser against real captured payloads from the live CTIS
public JSON API. Both the search shape and the retrieve shape are tested.
"""

from __future__ import annotations

import json

from tests.helpers.paths import FIXTURES_DIR

from vitiligo.sources.euctr import (
    _normalize_phase,
    _parse_eu_date,
    _parse_trial_countries,
    parse_euctr,
)
from vitiligo.storage.models import TrialSourceKind

FIXTURE_DIR = FIXTURES_DIR
SEARCH = FIXTURE_DIR / "euctr_search_sample.json"
RETRIEVE = FIXTURE_DIR / "euctr_retrieve_sample.json"


def _search_records() -> list[dict]:
    return json.loads(SEARCH.read_text())["data"]


def _retrieve_record() -> dict:
    return json.loads(RETRIEVE.read_text())


# ---------------------------------------------------------------- helpers


def test_normalize_phase_maps_to_canonical_set() -> None:
    assert _normalize_phase("Therapeutic exploratory (Phase II)") == ["PHASE2"]
    assert _normalize_phase("Therapeutic confirmatory  (Phase III)") == ["PHASE3"]
    assert _normalize_phase("Phase II and Phase III (Integrated)") == ["PHASE2", "PHASE3"]
    assert _normalize_phase("Phase I") == ["PHASE1"]
    assert _normalize_phase("Phase IV") == ["PHASE4"]
    assert _normalize_phase("") == []
    assert _normalize_phase(None) == []
    # Unknown phase strings degrade silently rather than raising.
    assert _normalize_phase("something else entirely") == []


def test_parse_eu_date_iso_normalization() -> None:
    assert _parse_eu_date("23/04/2024") == "2024-04-23"
    assert _parse_eu_date("2024-04-23") == "2024-04-23"
    assert _parse_eu_date("") is None
    assert _parse_eu_date(None) is None
    # Unknown shapes are surfaced as-is rather than dropped silently.
    assert _parse_eu_date("April 2024") == "April 2024"


def test_parse_trial_countries_strips_count_suffix() -> None:
    out = _parse_trial_countries(["Netherlands:5", "Germany:5", "Poland:5"])
    assert out == ["Germany", "Netherlands", "Poland"]
    assert _parse_trial_countries(None) == []
    assert _parse_trial_countries([]) == []


# ---------------------------------------------------------------- parser


def test_parse_euctr_search_record_basic() -> None:
    record = _search_records()[0]
    trial = parse_euctr(record, detail=None)
    assert trial is not None

    assert trial.source == TrialSourceKind.EUCTR
    assert trial.source_id and "-" in trial.source_id
    assert trial.brief_title or trial.official_title
    assert trial.study_type == "INTERVENTIONAL"
    assert trial.countries  # CTIS records always carry country participation
    assert all(":" not in c for c in trial.countries)
    # Search-only record has no detail-derived fields.
    assert trial.eligibility_criteria is None
    assert trial.interventions == []
    # Phase is normalized into the canonical set we use across registries.
    if trial.phases:
        for p in trial.phases:
            assert p.startswith("PHASE") or p in {"EARLY_PHASE1", "BIOEQUIVALENCE"}


def test_parse_euctr_with_detail_extracts_eligibility_and_interventions() -> None:
    detail = _retrieve_record()
    target = detail["ctNumber"]
    # Search results are sorted by decisionDate so the first row may not be
    # the same trial we have a detail capture for. Look up the matching one;
    # if unavailable (older fixture, newer trials at the top), fall back to
    # the detail's own ctNumber for a minimal stub record.
    record = next(
        (r for r in _search_records() if r["ctNumber"] == target),
        {"ctNumber": target, "ctTitle": "fallback", "trialCountries": []},
    )

    trial = parse_euctr(record, detail=detail)
    assert trial is not None

    # Detail-derived fields must be populated.
    assert trial.summary, "trialObjective.mainObjective should populate summary"
    assert trial.eligibility_criteria, "principalInclusionCriteria must yield eligibility text"
    assert "Inclusion Criteria:" in (trial.eligibility_criteria or "")

    assert trial.interventions, "products list should yield at least one intervention"
    for iv in trial.interventions:
        assert iv["type"] == "DRUG"
        assert iv["name"]


def test_parse_euctr_returns_none_on_missing_ct_number() -> None:
    assert parse_euctr({}, None) is None
    assert parse_euctr({"ctNumber": ""}, None) is None


def test_parse_euctr_handles_partial_search_record() -> None:
    minimal = {
        "ctNumber": "2099-000001-00-00",
        "ctTitle": "Imaginary vitiligo trial",
        "trialPhase": "Phase III",
        "ctStatus": "Authorised",
        "trialCountries": ["Netherlands:1"],
    }
    trial = parse_euctr(minimal, detail=None)
    assert trial is not None
    assert trial.source_id == "2099-000001-00-00"
    assert trial.phases == ["PHASE3"]
    assert trial.status == "AUTHORISED"
    assert trial.countries == ["Netherlands"]
    assert trial.has_results is False
