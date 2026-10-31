"""Tests for the vitiligo trials with readable results that are not JAK trials."""

from __future__ import annotations

import pytest

from vitiligo.reports.clinical import MIN_ANALYSED, build_evidence_rows
from vitiligo.reports.jak import build_jak_atlas
from vitiligo.reports.jak_arms import ArmEndpointRow, harmonize_arms
from vitiligo.reports.non_jak import NON_JAK_TRIALS, non_jak_arm_rows


@pytest.fixture(scope="module")
def jak_rows() -> list[ArmEndpointRow]:
    return harmonize_arms(build_jak_atlas())


@pytest.fixture(scope="module")
def non_jak_rows() -> list[ArmEndpointRow]:
    return non_jak_arm_rows()


@pytest.mark.corpus
def test_a_proportion_is_not_read_as_a_percentage(require_local_corpus, non_jak_rows) -> None:
    """AMG 714 posts its responder rates as proportions: 15% is "0.150".

    Read as a percentage that is 0.15%, a hundredfold understatement, and the
    row would say nought responders of forty. The unit says which it is.
    """
    week48 = [
        r
        for r in non_jak_rows
        if r.source_id == "NCT04338581" and r.week == 48 and r.arm_role == "active"
    ]
    f75 = next(r for r in week48 if (r.instrument, r.threshold) == ("F-VASI", 75))
    assert (f75.responders, f75.n_analyzed) == (8, 40)
    assert f75.percent == pytest.approx(20.0)


@pytest.mark.corpus
def test_the_placebo_arm_is_shown_although_it_is_below_the_floor(
    require_local_corpus, jak_rows, non_jak_rows
) -> None:
    """AMG 714 randomised 19 to placebo, one short of the 20-patient floor.

    That floor stops a rate from a handful of patients reading as reliable. A
    comparator is not read that way — it is read beside the treated arm with
    its own denominator printed — and suppressing it left the only
    placebo-controlled non-JAK result in the corpus showing uncontrolled,
    which is the failure this table exists to prevent.
    """
    rows = build_evidence_rows(jak_rows + non_jak_rows)
    amg = [r for r in rows if r.trial == "NCT04338581"]
    assert amg, "AMG 714 should reach the clinician table"
    for row in amg:
        assert row.control_percent is not None, f"{row.endpoint} lost its comparator"
        assert row.control_analysed == 19
        assert row.control_analysed < MIN_ANALYSED


@pytest.mark.corpus
def test_relaxing_the_floor_changes_no_jak_row(require_local_corpus, jak_rows) -> None:
    """Only one trial in the corpus has a week-24 control below the floor.

    If a JAK comparator ever falls under it, this fails and the change has to
    be thought about again rather than inherited.
    """
    rows = build_evidence_rows(jak_rows)
    assert len(rows) == 66
    for row in rows:
        if row.control_analysed is not None:
            assert row.control_analysed >= MIN_ANALYSED


@pytest.mark.corpus
def test_the_regimen_is_stated_rather_than_parsed(require_local_corpus, non_jak_rows) -> None:
    """The arm is labelled "AMG 714"; the dose is in prose nothing reads.

    Without the table in ``non_jak`` the row reaches a clinician with no dose
    and no route, which is not a prescribable description.
    """
    active = [r for r in non_jak_rows if r.source_id == "NCT04338581" and r.arm_role == "active"]
    assert active
    for row in active:
        assert row.arm_agent == "AMG 714"
        assert row.route == "subcutaneous"
        assert (row.dose_value, row.dose_unit, row.frequency) == (300.0, "mg", "Q2W")


@pytest.mark.corpus
def test_the_placebo_arm_keeps_no_agent(require_local_corpus, non_jak_rows) -> None:
    """The regimen is applied to treated arms only; a placebo has no dose."""
    placebo = [r for r in non_jak_rows if r.arm_role == "placebo"]
    assert placebo
    assert all(r.arm_agent is None and r.dose_value is None for r in placebo)


def test_only_threshold_endpoints_are_listed() -> None:
    """Two non-JAK trials post responder counts and are deliberately absent.

    NCT01517893 counts participants with *a decrease* in VASI and NCT04374435
    those with *a percent change* in body surface area. Neither names a
    threshold, so neither is comparable with an F-VASI50, and listing them
    here would invite exactly that comparison.
    """
    listed = {t.source_id for t in NON_JAK_TRIALS}
    assert "NCT01517893" not in listed
    assert "NCT04374435" not in listed
    assert listed == {"NCT04338581"}


@pytest.mark.corpus
def test_non_jak_rows_never_enter_the_model(require_local_corpus, non_jak_rows) -> None:
    """AMG 714 reports F-VASI and T-VASI thresholds, so a filter would take it.

    What keeps it out is that the model builds its rows from the JAK atlas and
    never calls this module. This asserts the separation at its source: the
    atlas does not contain the trial.
    """
    assert non_jak_rows
    atlas_ids = {t.source_id for t in build_jak_atlas().trials}
    for trial in NON_JAK_TRIALS:
        assert trial.source_id not in atlas_ids
