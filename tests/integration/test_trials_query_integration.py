"""Integration tests for trial query logic (seeded temp DB)."""

from __future__ import annotations

import pytest

from vitiligo.storage import TrialSourceKind
from vitiligo.trials import TrialFilter, list_trials, retrieve_relevant_trials
from vitiligo.trials.query import count_trials, summarize_trials

pytestmark = pytest.mark.integration


def _ids(trials: list) -> set[str]:
    return {t.source_id for t in trials}


def test_list_trials_matches_intervention_name_only(seeded_trial_db) -> None:
    """Drugs listed only under interventions JSON must be findable."""
    found = list_trials(TrialFilter(query="tacrolimus", limit=50))
    assert "NCT00000001" in _ids(found)

    baricitinib = list_trials(TrialFilter(query="baricitinib", limit=50))
    assert "NCT00000002" in _ids(baricitinib)

    pimecrolimus = list_trials(TrialFilter(query="pimecrolimus", limit=50))
    assert "EUCTR-2020-001" in _ids(pimecrolimus)


def test_list_trials_filters_by_source(seeded_trial_db) -> None:
    ictrp = list_trials(TrialFilter(query=None, sources=(TrialSourceKind.ICTRP,), limit=50))
    assert _ids(ictrp) == {"ICTRP-001"}

    ctgov = list_trials(TrialFilter(query="vitiligo", sources=(TrialSourceKind.CTGOV,), limit=50))
    assert _ids(ctgov) == {"NCT00000001", "NCT00000002"}


def test_list_trials_filters_by_status_and_has_results(seeded_trial_db) -> None:
    recruiting = list_trials(TrialFilter(status="recruiting", limit=50))
    assert _ids(recruiting) == {"NCT00000001"}

    with_results = list_trials(TrialFilter(has_results=True, limit=50))
    assert _ids(with_results) == {"NCT00000002"}


def test_list_trials_filters_by_phase_and_country(seeded_trial_db) -> None:
    phase2 = list_trials(TrialFilter(phase="PHASE2", limit=50))
    assert _ids(phase2) == {"NCT00000001", "EUCTR-2020-001"}

    france = list_trials(TrialFilter(country="france", limit=50))
    assert _ids(france) == {"EUCTR-2020-001"}


def test_list_trials_no_match_returns_empty(seeded_trial_db) -> None:
    assert list_trials(TrialFilter(query="nonexistent-drug-xyz", limit=50)) == []


def test_count_trials_matches_list_length(seeded_trial_db) -> None:
    filt = TrialFilter(query="vitiligo", limit=1, offset=0)
    assert count_trials(filt) == 4
    assert len(list_trials(filt)) == 1


def test_list_trials_pagination(seeded_trial_db) -> None:
    page1 = list_trials(TrialFilter(limit=2, offset=0))
    page2 = list_trials(TrialFilter(limit=2, offset=2))
    assert len(page1) == 2
    assert len(page2) == 2
    assert _ids(page1).isdisjoint(_ids(page2))


def test_list_trials_orders_by_last_update_desc(seeded_trial_db) -> None:
    trials = list_trials(TrialFilter(limit=10))
    assert [t.source_id for t in trials] == [
        "NCT00000002",
        "NCT00000001",
        "ICTRP-001",
        "EUCTR-2020-001",
    ]


def test_summarize_trials_on_seeded_db(seeded_trial_db) -> None:
    summary = summarize_trials()
    assert summary["total"][0].count == 4
    by_source = {r.label: r.count for r in summary["by_source"]}
    assert by_source["ctgov"] == 2
    assert by_source["ictrp"] == 1
    assert by_source["euctr"] == 1


def test_retrieve_relevant_trials_empty_intent(seeded_trial_db) -> None:
    assert retrieve_relevant_trials("") == []
    assert retrieve_relevant_trials("   ") == []


def test_retrieve_relevant_trials_prefers_high_signal_phases(seeded_trial_db) -> None:
    results = retrieve_relevant_trials("baricitinib", limit=5)
    assert results
    assert results[0].source_id == "NCT00000002"


def test_retrieve_relevant_trials_falls_back_when_high_signal_empty(seeded_trial_db) -> None:
    """When no trial meets the high-signal filter, return unfiltered candidates."""
    results = retrieve_relevant_trials("herbal", limit=5, require_high_signal=True)
    assert _ids(results) == {"ICTRP-001"}


@pytest.mark.parametrize("query", ["TACROLIMUS", "tacrolimus", "Tacrolimus"])
def test_list_trials_query_is_case_insensitive(seeded_trial_db, query: str) -> None:
    assert "NCT00000001" in _ids(list_trials(TrialFilter(query=query, limit=50)))
