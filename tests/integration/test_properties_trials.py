"""Property-based invariants for trial query filters (seeded temp DB)."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from vitiligo.storage import TrialSourceKind
from vitiligo.trials import TrialFilter, list_trials
from vitiligo.trials.query import count_trials

pytestmark = pytest.mark.integration

_QUERY_TERMS = st.sampled_from(["tacrolimus", "baricitinib", "vitiligo", "pimecrolimus", "herbal"])
_STATUSES = st.sampled_from([None, "RECRUITING", "COMPLETED", "AUTHORISED"])
_PHASES = st.sampled_from([None, "PHASE2", "PHASE3", "NA"])
_COUNTRIES = st.sampled_from([None, "United States", "Germany", "China", "France"])
_SOURCES = st.sampled_from(
    [
        tuple(TrialSourceKind),
        (TrialSourceKind.CTGOV,),
        (TrialSourceKind.ICTRP, TrialSourceKind.EUCTR),
    ]
)
_HAS_RESULTS = st.sampled_from([None, True, False])
_LIMITS = st.integers(min_value=1, max_value=50)
_OFFSETS = st.integers(min_value=0, max_value=20)


@st.composite
def trial_filters(draw: st.DrawFn) -> TrialFilter:
    return TrialFilter(
        query=draw(_QUERY_TERMS),
        status=draw(_STATUSES),
        phase=draw(_PHASES),
        country=draw(_COUNTRIES),
        sources=draw(_SOURCES),
        has_results=draw(_HAS_RESULTS),
        limit=draw(_LIMITS),
        offset=draw(_OFFSETS),
    )


def _ids(trials: list) -> set[str]:
    return {t.source_id for t in trials}


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(trial_filters())
def test_count_is_at_least_page_size(seeded_trial_db, filt: TrialFilter) -> None:
    rows = list_trials(filt)
    total = count_trials(filt)
    assert total >= len(rows)
    assert len(rows) <= filt.limit


@settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(_QUERY_TERMS, _LIMITS)
def test_query_is_case_insensitive(seeded_trial_db, term: str, limit: int) -> None:
    lower = list_trials(TrialFilter(query=term.lower(), limit=limit))
    upper = list_trials(TrialFilter(query=term.upper(), limit=limit))
    assert _ids(lower) == _ids(upper)


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(_QUERY_TERMS, st.integers(min_value=1, max_value=2))
def test_pagination_pages_are_disjoint(seeded_trial_db, term: str, page_size: int) -> None:
    page0 = list_trials(TrialFilter(query=term, limit=page_size, offset=0))
    page1 = list_trials(TrialFilter(query=term, limit=page_size, offset=page_size))
    assert _ids(page0).isdisjoint(_ids(page1))
