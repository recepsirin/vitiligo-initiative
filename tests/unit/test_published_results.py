"""Tests for trial results published without a verifiable table cell."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from vitiligo.models.baseline import ModelFilters, usable
from vitiligo.reports.bounds import bound_rate
from vitiligo.reports.paper_results import load_toplines, toplines_from

CURATION = Path(__file__).resolve().parents[2] / "curation"


def _published() -> list[dict]:
    return json.loads((CURATION / "published-results.json").read_text())["results"]


def test_the_frozen_topline_file_is_untouched() -> None:
    """These rows go in their own file precisely so that one keeps its hash.

    v0.4, v0.5 and the evidence ranking are defined by topline-results.json and
    their sealed data hashes depend on it. Adding a row there to save a file is
    how a sealed model quietly stops reproducing.
    """
    digest = hashlib.sha256((CURATION / "topline-results.json").read_bytes()).hexdigest()
    assert digest == "8abd1de39294cd82c2748ba1d1f6bc67e3745e854f057491aa03351753e5a85e"


def test_published_rows_cannot_reach_the_model() -> None:
    """The instrument filter is what keeps them out, not an intention to.

    HI-Light's endpoint is the Vitiligo Noticeability Scale, so a VASI fit must
    not see it. If a VASI-threshold row is ever added to this file, this fails.
    """
    rows = toplines_from(_published())
    assert rows
    for instrument in ("F-VASI", "T-VASI"):
        filters = ModelFilters.of(rows, instrument)
        assert not [r for r in rows if usable(r, instrument, filters)]


# The counts the abstract prints, against which the stored percentages must
# round-trip. Recorded here so a mistyped rate or arm size fails the test.
PRINTED = {"Topical corticosteroid": 20, "NB-UVB": 27, "TCS + NB-UVB": 34}


def test_each_percentage_recovers_the_count_the_abstract_printed() -> None:
    """The abstract gives both, so storing the percentage must not lose the count.

    A percentage kept to one decimal recovers the numerator only while the arm
    is small; at these sizes it does. An earlier version of this test compared
    the same arithmetic with itself and could not fail at all.
    """
    rows = {r["arm_label"]: r for r in _published()}
    assert set(rows) == set(PRINTED)
    for label, printed in PRINTED.items():
        row = rows[label]
        assert round(row["percent"] / 100 * row["n"]) == printed
        assert row["n"] <= row["randomised"]


def test_every_row_carries_the_denominator_its_bound_needs() -> None:
    """A rate without the randomised group size cannot be bracketed.

    HI-Light lost 28% of participants before the primary endpoint, so the
    bracket is the finding: each arm's bound is about 27 points wide, against a
    9.8-point spread between the arms as observed.
    """
    for row in _published():
        responders = round(row["percent"] / 100 * row["n"])
        bounds = bound_rate(responders=responders, analysed=row["n"], group=row["randomised"])
        assert bounds is not None
        assert bounds.width > 20.0
        assert bounds.covers(row["percent"])


def test_the_two_curation_files_describe_different_trials() -> None:
    """A trial in both files would have its arms counted twice."""
    frozen = {r.source_id for r in load_toplines(CURATION / "topline-results.json")}
    published = {r["trial"] for r in _published()}
    assert frozen and published
    assert not frozen & published
