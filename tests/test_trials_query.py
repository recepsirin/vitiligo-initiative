"""Tests for structured trial queries."""

from __future__ import annotations

import pytest

from vitiligo.storage import TrialSourceKind
from vitiligo.trials import TrialFilter, list_trials


def _ids(trials: list) -> set[str]:
    return {t.source_id for t in trials}


@pytest.mark.integration
def test_list_trials_matches_intervention_names_on_local_corpus(require_local_corpus) -> None:
    """Regression: drugs listed only under interventions must be findable."""
    tacrolimus = list_trials(TrialFilter(query="tacrolimus", limit=50))
    assert "NCT03365141" in _ids(tacrolimus)

    baricitinib = list_trials(TrialFilter(query="baricitinib", limit=50))
    assert "NCT07554222" in _ids(baricitinib)

    pimecrolimus = list_trials(TrialFilter(query="pimecrolimus", limit=50))
    assert "NCT01082393" in _ids(pimecrolimus)


@pytest.mark.integration
def test_list_trials_still_matches_title_fields(require_local_corpus) -> None:
    rux = list_trials(
        TrialFilter(query="ruxolitinib", sources=(TrialSourceKind.CTGOV,), limit=5)
    )
    assert rux
    assert any("ruxolitinib" in (t.brief_title or t.summary or "").lower() for t in rux)
