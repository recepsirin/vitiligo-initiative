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


VASI_INSTRUMENTS = frozenset({"F-VASI", "T-VASI"})


def test_no_row_here_is_a_vasi_threshold() -> None:
    """This is the invariant, asserted on the file rather than on the filter.

    Checking only that `usable()` rejects these rows passes for the wrong
    reason: an injected F-VASI75 row at week 156 was rejected by a max-week
    design annotation, not by the instrument filter, so the test would have
    held while the guard it names was broken.
    """
    for row in _published():
        assert row["instrument"] not in VASI_INSTRUMENTS, (
            f"{row['trial']} {row['arm_label']} is a VASI row and belongs in the "
            "extraction pipeline, not in this file"
        )


def test_published_rows_cannot_reach_the_model() -> None:
    """And the model filter agrees, for whatever reason it reaches that answer."""
    rows = toplines_from(_published())
    assert rows
    for instrument in ("F-VASI", "T-VASI"):
        filters = ModelFilters.of(rows, instrument)
        assert not [r for r in rows if usable(r, instrument, filters)]


# The counts HI-Light's abstract prints, against which its stored percentages
# must round-trip. Recorded here so a mistyped rate or arm size fails.
HILIGHT_PRINTED = {"Topical corticosteroid": 20, "NB-UVB": 27, "TCS + NB-UVB": 34}


def test_hilight_percentages_recover_the_counts_its_abstract_printed() -> None:
    """The abstract gives both, so storing the percentage must not lose the count.

    A percentage kept to one decimal recovers the numerator only while the arm
    is small; at these sizes it does. An earlier version of this test compared
    the same arithmetic with itself and could not fail at all.
    """
    rows = {r["arm_label"]: r for r in _published() if r["trial"] == "ISRCTN17160087"}
    assert set(rows) == set(HILIGHT_PRINTED)
    for label, printed in HILIGHT_PRINTED.items():
        assert rows[label]["responders"] == printed


def test_the_stored_count_is_the_one_the_percentage_implies() -> None:
    """The count is stored, not derived, because deriving it is lossy.

    27 of 123 is 21.95%, which this file rounds to 22.0; multiplying back gives
    27.06. That rounds to 27 correctly, but an equality check against the exact
    product fails, and an earlier version of this test did exactly that.
    """
    rows = _published()
    assert rows
    for row in rows:
        assert "responders" in row, f"{row['trial']} {row['arm_label']} wk{row['week']}"
        assert round(row["percent"] / 100 * row["n"]) == row["responders"]
        assert 0 <= row["responders"] <= row["n"]


def test_every_row_can_be_bracketed(_=None) -> None:
    """A rate without its randomised group size cannot be bounded.

    The bound is the reason these rows are worth storing at all, so a row that
    cannot produce one does not belong. The width is data, not a requirement:
    a narrow bound means the visit kept its participants.
    """
    for row in _published():
        bounds = bound_rate(
            responders=row["responders"], analysed=row["n"], group=row["randomised"]
        )
        assert bounds is not None, f"{row['trial']} {row['arm_label']} wk{row['week']}"
        assert bounds.covers(row["percent"])
        assert row["n"] <= row["randomised"]


def test_the_week_156_figure_is_kept_with_what_makes_it_readable() -> None:
    """100% at three years is two patients out of thirty-one randomised.

    This row is the reason the file exists. Stored as a percentage alone it is
    the most misleading number in the corpus; stored with its denominators it
    is bounded at 6.5% to 100%, which says plainly that it settles nothing.
    """
    row = next(
        r
        for r in _published()
        if r["trial"] == "NCT03099304" and r["week"] == 156 and r["percent"] == 100.0
    )
    assert (row["n"], row["randomised"]) == (2, 31)
    bounds = bound_rate(responders=2, analysed=2, group=31)
    assert bounds is not None
    assert (bounds.floor, bounds.ceiling) == (6.5, 100.0)


def test_the_two_curation_files_describe_different_trials() -> None:
    """A trial in both files would have its arms counted twice."""
    frozen = {r.source_id for r in load_toplines(CURATION / "topline-results.json")}
    published = {r["trial"] for r in _published()}
    assert frozen and published
    assert not frozen & published
