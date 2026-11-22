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


def test_retrieve_relevant_trials_matches_multi_word_intent(seeded_trial_db) -> None:
    """A natural-language intent must not be matched as one literal phrase."""
    results = retrieve_relevant_trials("baricitinib JAK inhibitor for non-segmental vitiligo")
    assert results
    assert results[0].source_id == "NCT00000002"


def test_retrieve_relevant_trials_ranks_by_token_overlap(seeded_trial_db) -> None:
    results = retrieve_relevant_trials(
        "tacrolimus ointment versus baricitinib", limit=5, require_high_signal=False
    )
    # Tacrolimus trial matches two tokens; baricitinib trial matches one.
    assert [t.source_id for t in results[:2]] == ["NCT00000001", "NCT00000002"]


def test_retrieve_relevant_trials_generic_intent_falls_back_to_phrase(seeded_trial_db) -> None:
    """'vitiligo' alone carries no discriminating token; the literal match still works."""
    results = retrieve_relevant_trials("vitiligo", limit=10, require_high_signal=False)
    assert _ids(results) == {"NCT00000001", "NCT00000002", "ICTRP-001", "EUCTR-2020-001"}


def test_retrieve_relevant_trials_weights_rare_tokens(test_db_path) -> None:
    """One specific drug match outranks two generic words shared by many trials.

    Unweighted overlap would rank every generic trial (2 tokens) above the
    ruxolitinib trial (1 token).
    """
    from sqlmodel import Session

    from vitiligo.storage import Trial, get_engine

    trials = [
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT10000000",
            brief_title="Ruxolitinib cream in vitiligo",
            phases=["PHASE3"],
        )
    ]
    trials += [
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id=f"NCT2000000{i}",
            brief_title=f"Topical combination regimen {i}",
            conditions=["Vitiligo"],
            phases=["PHASE3"],
        )
        for i in range(10)
    ]
    with Session(get_engine(), expire_on_commit=False) as session:
        session.add_all(trials)
        session.commit()

    results = retrieve_relevant_trials("topical ruxolitinib combination", limit=3)
    assert results[0].source_id == "NCT10000000"


def _seed(trials: list) -> None:
    from sqlmodel import Session

    from vitiligo.storage import get_engine

    with Session(get_engine(), expire_on_commit=False) as session:
        session.add_all(trials)
        session.commit()


def test_retrieve_relevant_trials_matches_word_starts_only(test_db_path) -> None:
    """'active' must not match 'inactive'; 'inhibitor' still matches 'inhibitors'."""
    from vitiligo.storage import Trial

    _seed(
        [
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT30000001",
                brief_title="Inactive vitiligo lesions",
            ),
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT30000002",
                brief_title="JAK inhibitors in vitiligo",
            ),
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT30000003",
                brief_title="Nonsegmental vitiligo cohort",
            ),
        ]
    )
    assert retrieve_relevant_trials("active", require_high_signal=False) == []
    assert _ids(retrieve_relevant_trials("inhibitor", require_high_signal=False)) == {"NCT30000002"}
    assert _ids(retrieve_relevant_trials("non-segmental", require_high_signal=False)) == {
        "NCT30000003"
    }


def test_retrieve_relevant_trials_weights_tested_fields_over_prose(test_db_path) -> None:
    """The same token counts half when it appears only in summary prose.

    The prose trial is inserted last so the id tie-break would favour it if
    both matches were weighted equally.
    """
    from vitiligo.storage import Trial

    _seed(
        [
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT40000002",
                brief_title="Topical study in vitiligo",
                interventions=[{"name": "Ruxolitinib cream"}],
            ),
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT40000001",
                brief_title="Hyperbaric oxygen in vitiligo",
                summary="Unlike ruxolitinib, oxygen therapy is cheap.",
                interventions=[{"name": "Hyperbaric oxygen"}],
            ),
        ]
    )
    results = retrieve_relevant_trials("ruxolitinib", require_high_signal=False)
    assert [t.source_id for t in results] == ["NCT40000002", "NCT40000001"]


def test_retrieval_returns_vitiligo_trials_only(test_db_path) -> None:
    """The store also holds a JAK inhibitor's trials in other diseases (issue #23)."""
    from vitiligo.storage import Trial

    _seed(
        [
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT50000001",
                brief_title="Ruxolitinib in myelofibrosis",
                conditions=["Myelofibrosis"],
                phases=["PHASE3"],
                has_results=True,
            ),
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT50000002",
                brief_title="Ruxolitinib cream",
                conditions=["Vitiligo"],
                phases=["PHASE2"],
            ),
        ]
    )
    assert _ids(retrieve_relevant_trials("ruxolitinib")) == {"NCT50000002"}


def test_retrieval_ranks_every_match_not_only_the_newest(test_db_path) -> None:
    """A cap of 1,000 matches, newest first, left a 2008 acral trial unranked."""
    from vitiligo.storage import Trial

    newer = [
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id=f"NCT6{i:07d}",
            brief_title=f"Repigmentation study {i}",
            conditions=["Vitiligo"],
            last_update_date="2025-01-01",
        )
        for i in range(1000)
    ]
    older = Trial(
        source=TrialSourceKind.CTGOV,
        source_id="NCT00622180",
        brief_title="Acral repigmentation with narrowband UVB",
        conditions=["Vitiligo"],
        last_update_date="2008-01-01",
    )
    _seed([*newer, older])
    results = retrieve_relevant_trials("acral repigmentation", limit=1, require_high_signal=False)
    assert [t.source_id for t in results] == ["NCT00622180"]


def test_a_site_a_trial_excludes_earns_it_no_credit(test_db_path) -> None:
    """Issue #23: "excluding hands and feet" made an anifrolumab trial an acral one."""
    from vitiligo.storage import Trial

    _seed(
        [
            Trial(
                source=TrialSourceKind.EUCTR,
                source_id="2024-512041-17-00",
                brief_title="Anifrolumab and phototherapy",
                conditions=[
                    "Non-segmental vitiligo, body surface area >5% excluding hands and feet"
                ],
            ),
            Trial(
                source=TrialSourceKind.ICTRP,
                source_id="CTRI/2023/06/054258",
                brief_title="Tofacitinib gel for vitiligo on hands and feet",
                conditions=["Vitiligo"],
            ),
            # Only a site is excluded: "exclude the effect of NB-UVB" still names it.
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT70000003",
                brief_title="Control groups to exclude the systemic effect of UVB in vitiligo",
                conditions=["Vitiligo"],
            ),
            # The exclusion ends with its clause.
            Trial(
                source=TrialSourceKind.CTGOV,
                source_id="NCT70000004",
                brief_title="Excluding sunlight as a confounder, face lesions in vitiligo",
                conditions=["Vitiligo"],
            ),
        ]
    )
    hands = retrieve_relevant_trials("hands feet", require_high_signal=False)
    assert _ids(hands) == {"CTRI/2023/06/054258"}
    assert _ids(retrieve_relevant_trials("uvb", require_high_signal=False)) == {"NCT70000003"}
    assert _ids(retrieve_relevant_trials("face", require_high_signal=False)) == {"NCT70000004"}
