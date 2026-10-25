"""Corpus-backed trial query tests (real vitiligo.db only where seeded data is insufficient)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from vitiligo.storage import TrialSourceKind
from vitiligo.trials import TrialFilter, list_trials


@pytest.mark.corpus
def test_list_trials_still_matches_title_fields_on_local_corpus(require_local_corpus) -> None:
    rux = list_trials(TrialFilter(query="ruxolitinib", sources=(TrialSourceKind.CTGOV,), limit=5))
    assert rux
    assert any("ruxolitinib" in (t.brief_title or t.summary or "").lower() for t in rux)


@pytest.mark.corpus
def test_the_ictrp_test_fixture_is_not_in_the_served_store(require_local_corpus) -> None:
    """The ICTRP XML fixture must never be ingested as if it were real data.

    It was. ``ingest ictrp`` pointed at ``tests/fixtures/ictrp_vitiligo_sample.xml``
    put two invented trials into the store on 2026-05-25, where they stayed for
    five months and seeded three graph entities and six edges. One of them,
    "ChiCTR2300070001", is a real registry id belonging to a trial of
    acupuncture for tinnitus; the other does not exist at all.

    The fixture's NCT03099304 is a real trial and is excluded: it belongs in
    the store, under ``ctgov``, from the registry itself.
    """
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "ictrp_vitiligo_sample.xml"
    invented = {
        i
        for i in re.findall(r"<TrialID>([^<]+)</TrialID>", fixture.read_text())
        if not i.startswith("NCT")
    }
    assert invented, "fixture has no ICTRP-native ids; this test would pass vacuously"

    held = {
        trial.source_id
        for trial in list_trials(TrialFilter(sources=(TrialSourceKind.ICTRP,), limit=1000))
    }
    assert held, "no ICTRP records in the store; this test would pass vacuously"
    assert not (invented & held), (
        f"test-fixture trials are being served as real data: {sorted(invented & held)}"
    )
