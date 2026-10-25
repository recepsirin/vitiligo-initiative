"""Unit tests for partial-identification bounds on a reported rate.

The motivating figure is TRuE-V2's week-52 F-VASI75: 85 responders among the
177 patients assessed, out of the 222 the arm had at week 24.
"""

from __future__ import annotations

import pytest

from vitiligo.reports.bounds import bound_rate


def test_true_v2_week_52_f_vasi75() -> None:
    """The published 48.0% sits near the top of what the group could have done."""
    bounds = bound_rate(85, 177, 222)
    assert bounds is not None
    assert (bounds.reported, bounds.floor, bounds.ceiling) == (48.0, 38.3, 58.6)
    assert (bounds.missing, bounds.width) == (45, 20.3)
    assert not bounds.identified


def test_a_rate_the_group_could_not_have_produced_is_rejected() -> None:
    """This is what the bracket is for: the model predicts 62.4% at week 52."""
    bounds = bound_rate(85, 177, 222)
    assert bounds is not None
    assert not bounds.covers(62.4)
    assert bounds.covers(48.0)
    assert bounds.covers(38.3)
    assert bounds.covers(58.6)


def test_a_reference_smaller_than_the_counted_set_is_refused() -> None:
    """A group below ``analysed`` would give a bracket narrower than the truth.

    That is the one direction a bound must never be wrong in, so the record is
    treated as unusable rather than bounded on a guess.
    """
    assert bound_rate(85, 177, 100) is None


@pytest.mark.parametrize(
    ("responders", "analysed", "group"),
    [
        (None, 177, 222),
        (85, 0, 222),
        (85, 177, 0),
        (85, 177, None),
        (-1, 177, 222),
        (200, 177, 222),
    ],
)
def test_unusable_records_are_not_bounded(
    responders: int | None, analysed: int | None, group: int | None
) -> None:
    assert bound_rate(responders, analysed, group) is None


def test_complete_data_leaves_nothing_to_bound() -> None:
    bounds = bound_rate(50, 100, 100)
    assert bounds is not None
    assert bounds.identified
    assert bounds.floor == bounds.ceiling == bounds.reported == 50.0
    assert bounds.width == 0.0


def test_a_low_rate_can_still_be_badly_undetermined() -> None:
    """T-VASI90 reads 6.8% of 177, and could be anything up to 25.7% of 222.

    The width comes from the missing patients, not from the size of the rate,
    so a small number is not a safe one.
    """
    bounds = bound_rate(12, 177, 222)
    assert bounds is not None
    assert (bounds.reported, bounds.floor, bounds.ceiling) == (6.8, 5.4, 25.7)
