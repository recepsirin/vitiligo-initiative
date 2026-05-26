"""Corpus-backed trial query tests (real vitiligo.db only where seeded data is insufficient)."""

from __future__ import annotations

import pytest

from vitiligo.storage import TrialSourceKind
from vitiligo.trials import TrialFilter, list_trials


@pytest.mark.corpus
def test_list_trials_still_matches_title_fields_on_local_corpus(require_local_corpus) -> None:
    rux = list_trials(TrialFilter(query="ruxolitinib", sources=(TrialSourceKind.CTGOV,), limit=5))
    assert rux
    assert any("ruxolitinib" in (t.brief_title or t.summary or "").lower() for t in rux)
