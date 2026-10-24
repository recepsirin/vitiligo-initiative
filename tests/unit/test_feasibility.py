"""Tests for whether a hypothesis can be tested with data that exists."""

from __future__ import annotations

from typing import Any

from vitiligo.mechanisms.feasibility import (
    BLOCKED_ON_NEW_DATA,
    MISSING_DATASET,
    NO_DATA_NAMED,
    TESTABLE_NOW,
    assess,
    named_datasets,
)
from vitiligo.mechanisms.schema import from_dict

HELD = {"GSE203262", "GSE169238", "NCT04530344"}


def _mechanism(**test_over: Any) -> Any:
    test = {
        "question": "Does the score predict relapse?",
        "data": "Derived from GSE203262, applied to GSE169238.",
        "if_correct": "Hazard ratio above 1.",
        "if_incorrect": "No association.",
        "decides": "An association leaves the claim standing.",
    }
    test.update(test_over)
    return from_dict({"id": "x", "title": "T", "test": test})


def test_the_datasets_a_test_names_are_read_off_the_record() -> None:
    m = _mechanism(data="Derived from GSE203262 and GSE169238, checked against NCT04530344.")
    assert named_datasets(m) == ["GSE203262", "GSE169238", "NCT04530344"]


def test_a_dataset_named_twice_is_listed_once() -> None:
    assert named_datasets(_mechanism(data="GSE203262, then GSE203262 again.")) == ["GSE203262"]


def test_a_test_whose_datasets_are_all_held_can_start() -> None:
    result = assess(_mechanism(), HELD)
    assert result.status == TESTABLE_NOW
    assert result.can_start
    assert result.held == ["GSE203262", "GSE169238"]


def test_a_dataset_we_do_not_hold_is_named_as_the_blocker() -> None:
    result = assess(_mechanism(data="Applied to GSE999999."), HELD)
    assert result.status == MISSING_DATASET
    assert result.missing == ["GSE999999"]
    assert not result.can_start


def test_needing_uncollected_samples_outranks_holding_every_dataset() -> None:
    """The failure this check exists for: both records read 'testable now' until declared.

    Holding the reference datasets says nothing about whether the samples the
    test actually needs have ever been collected.
    """
    optimistic = assess(_mechanism(), HELD)
    assert optimistic.status == TESTABLE_NOW  # what it looked like before declaring

    declared = assess(
        _mechanism(needs_new_data=True, new_data="Skin sampled after treatment stops."),
        HELD,
    )
    assert declared.status == BLOCKED_ON_NEW_DATA
    assert not declared.can_start
    assert declared.held == ["GSE203262", "GSE169238"]  # still reported, still true
    assert "after treatment stops" in declared.note


def test_a_test_naming_no_dataset_says_so_rather_than_claiming_readiness() -> None:
    result = assess(_mechanism(data="A cohort we would have to assemble."), HELD)
    assert result.status == NO_DATA_NAMED
    assert not result.can_start
