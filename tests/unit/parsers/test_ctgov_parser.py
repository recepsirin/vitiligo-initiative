"""Offline tests for the ClinicalTrials.gov parser.

Uses a real captured response from the v2 API as a fixture so that the
parser is validated against the actual JSON shape, not what we hope it
looks like.
"""

from __future__ import annotations

import json

from tests.helpers.paths import FIXTURES_DIR

from vitiligo.sources.ctgov import parse_ctgov_study
from vitiligo.storage.models import TrialSourceKind

FIXTURE = FIXTURES_DIR / "ctgov_sample.json"


def _load_studies() -> list[dict]:
    return json.loads(FIXTURE.read_text())["studies"]


def test_parse_first_study_basic_fields() -> None:
    studies = _load_studies()
    trial = parse_ctgov_study(studies[0])
    assert trial is not None

    assert trial.source == TrialSourceKind.CTGOV
    assert trial.source_id.startswith("NCT")
    assert trial.brief_title and "vitiligo" in trial.brief_title.lower()
    assert trial.status, "overallStatus should always be present"
    assert isinstance(trial.phases, list)
    assert isinstance(trial.conditions, list)
    assert any("vitiligo" in c.lower() for c in trial.conditions)


def test_parse_normalizes_nested_modules() -> None:
    studies = _load_studies()
    for study in studies:
        trial = parse_ctgov_study(study)
        assert trial is not None

        for iv in trial.interventions:
            assert set(iv.keys()) >= {"type", "name", "description", "other_names"}

        for arm in trial.arm_groups:
            assert set(arm.keys()) >= {"label", "type", "description", "intervention_names"}

        for sponsor in trial.sponsors:
            assert sponsor["role"] in {"lead", "collaborator"}
            assert "name" in sponsor

        for loc in trial.locations:
            assert set(loc.keys()) >= {"facility", "status", "city", "state", "country"}

        for outcome in trial.primary_outcomes + trial.secondary_outcomes:
            assert set(outcome.keys()) == {"measure", "description", "time_frame"}


def test_parse_returns_none_when_nct_missing() -> None:
    assert parse_ctgov_study({"protocolSection": {}}) is None
    assert parse_ctgov_study({"protocolSection": {"identificationModule": {"nctId": ""}}}) is None


def test_parse_handles_partial_data() -> None:
    minimal = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT99999999", "briefTitle": "Test"},
            "statusModule": {"overallStatus": "RECRUITING"},
        },
        "hasResults": False,
    }
    trial = parse_ctgov_study(minimal)
    assert trial is not None
    assert trial.source_id == "NCT99999999"
    assert trial.status == "RECRUITING"
    assert trial.phases == []
    assert trial.interventions == []
    assert trial.locations == []
    assert trial.has_results is False
    assert trial.raw_metadata["nct_id"] == "NCT99999999"


def test_country_aggregation() -> None:
    studies = _load_studies()
    for study in studies:
        trial = parse_ctgov_study(study)
        assert trial is not None
        for c in trial.countries:
            assert c == c.strip()
            assert c
        assert sorted(trial.countries) == list(trial.countries)
