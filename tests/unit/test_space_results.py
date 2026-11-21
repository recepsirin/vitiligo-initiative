"""Results read from trial papers, as the trial explorer files and shows them."""

from __future__ import annotations

from vitiligo.reports.space_results import (
    explorer_index,
    explorer_trials,
    quote_rule,
    result_row,
)

ENTRY = {"trial": "pmid:15550128", "arms": [{"id": "A", "label": "0.03% tacrolimus ointment"}]}


def _always(_: str) -> bool:
    return True


def test_adverse_events_baselines_and_access_figures_stay_off_the_page() -> None:
    for kind in ("adverse event", "baseline", "access"):
        value = {"arm": "A", "outcome": "x", "type": kind, "n": 22, "percent": 9.1}
        assert result_row(ENTRY, value, ["15550128"], _always) is None, kind


def test_a_value_without_a_result_stays_off_but_a_printed_p_value_counts() -> None:
    direction_only = {"arm": "A vs B", "type": "comparison", "direction": "favours A"}
    assert result_row(ENTRY, direction_only, ["15550128"], _always) is None
    bound = {"arm": "A vs B", "type": "comparison", "p": "< 0.001", "direction": "favours A"}
    assert result_row(ENTRY, bound, ["15550128"], _always) is not None


def test_an_arm_letter_reads_as_its_label_and_a_printed_arm_as_printed() -> None:
    value = {"arm": "A", "type": "responders", "responders": 19, "n": 22, "percent": 86.4}
    row = result_row(ENTRY, value, ["15550128"], _always)
    assert row is not None and row["arm"] == "0.03% tacrolimus ointment"
    printed = result_row(ENTRY, {**value, "arm": "control"}, ["15550128"], _always)
    assert printed is not None and printed["arm"] == "control"


def test_a_quote_appears_only_where_the_paper_is_cc_by_or_cc0() -> None:
    allowed = quote_rule({"PMC1": "cc by", "PMC2": "cc by-nc"}, {"111": "PMC1"})
    assert allowed("pmid:111#abstract") and allowed("pmc:PMC1#table")
    assert not allowed("pmc:PMC2#table") and not allowed("doi:10.1/x#abstract")
    value = {
        "arm": "A",
        "type": "responders",
        "n": 22,
        "percent": 86.4,
        "source": "pmc:PMC2#table",
        "quote": ["Nineteen (86.4%) children"],
    }
    row = result_row(ENTRY, value, ["15550128"], allowed)
    assert row is not None and "quote" not in row


def test_results_are_filed_under_the_explorer_rows_they_belong_to() -> None:
    index = explorer_index(
        [
            {"id": "NCT04052425"},
            {"id": "NCT04057573"},
            {"id": "15550128", "pmid": "15550128"},
            {"id": "10.1/AbC", "doi": "10.1/AbC"},
        ]
    )
    pooled = {"trial": "pooled:NCT04052425+NCT04057573", "linked": ["NCT04052425", "NCT04057573"]}
    assert explorer_trials(pooled, index) == ["NCT04052425", "NCT04057573"]
    assert explorer_trials({"trial": "pmid:15550128"}, index) == ["15550128"]
    assert explorer_trials({"trial": "doi:10.1/abc"}, index) == ["10.1/AbC"]
    # A paper of a registered trial is not an explorer row of its own; it follows its link.
    assert explorer_trials({"trial": "pmid:999", "linked": ["NCT04052425"]}, index) == [
        "NCT04052425"
    ]
