"""Unit tests for the clinician-facing evidence table.

Each test here names a number this module printed before it existed, and fails
if that number can reach a clinician again. The rows are shaped like the
registry records they come from (NCT03099304, NCT03715829, NCT04057573).
"""

from __future__ import annotations

from typing import Any

from vitiligo.reports.clinical import build_evidence_rows, evidence_to_dict
from vitiligo.reports.jak_arms import ArmEndpointRow


def _row(**over: Any) -> ArmEndpointRow:
    base: dict[str, Any] = {
        "study_id": "NCT00000001",
        "source_id": "NCT00000001",
        "trial_agents": ["ruxolitinib"],
        "arm_label": "Ruxolitinib Cream 1.5% BID",
        "period": None,
        "arm_role": "active",
        "arm_agent": "ruxolitinib",
        "dose_value": 1.5,
        "dose_unit": "%",
        "loading_dose_value": None,
        "frequency": "BID",
        "route": "topical",
        "phototherapy": False,
        "endpoint": "F-VASI75",
        "instrument": "F-VASI",
        "threshold": 75,
        "body_region": "face",
        "assessor": None,
        "week": 24,
        "week_source": "title",
        "outcome_type": "PRIMARY",
        "n_analyzed": 200,
        "percent": 30.0,
        "responders": 60,
        "responders_derived": False,
        "value_raw": "30.0",
        "outcome_title": "F-VASI75 at week 24",
        "row_label": None,
        "flags": [],
    }
    base.update(over)
    return ArmEndpointRow(**base)


def test_shrinking_arm_does_not_outrank_the_randomised_group() -> None:
    """NCT03099304 read 100% of 9 at week 156 against 45.5% of 33 at week 24."""
    rows = build_evidence_rows(
        [
            _row(week=24, n_analyzed=33, responders=15, percent=45.5),
            _row(week=52, n_analyzed=33, responders=19, percent=57.6),
            _row(week=104, n_analyzed=19, responders=17, percent=89.5),
            _row(week=156, n_analyzed=9, responders=9, percent=100.0),
        ]
    )
    assert [(r.week, r.percent, r.analysed) for r in rows] == [(24, 45.5, 33)]


def test_the_largest_arm_wins_its_cell_not_the_highest_rate() -> None:
    """NCT05247489's seven patients read 85.7%; TRuE-V2's 222 read 30.9%.

    This is what keeps the tiny arm off the page today: it shares a cell with a
    pivotal trial, and size decides. The floors below cover the case where it
    does not.
    """
    rows = build_evidence_rows(
        [
            _row(source_id="NCT05247489", n_analyzed=7, responders=6, percent=85.7),
            _row(source_id="NCT04057573", n_analyzed=222, responders=69, percent=30.9),
        ]
    )
    assert [(r.percent, r.analysed) for r in rows] == [(30.9, 222)]


def test_an_arm_too_small_to_state_a_rate_is_dropped_outright() -> None:
    """A seven-patient arm alone in its cell has no larger arm to lose to.

    Nothing in the present corpus reaches the page this way, because TRuE-V
    reports every threshold NCT05247489 does. A trial reporting a threshold
    nobody else does would, so the floor stands between that and a clinician.
    """
    assert build_evidence_rows([_row(n_analyzed=7, responders=7, percent=100.0)]) == []


def test_a_week_24_arm_that_lost_patients_is_dropped() -> None:
    """NCT05247489 enrolled 16 and reported 7 at week 24, at 100%.

    Sized above the floor so this fails for attrition alone: 24 of 40 is 60%.
    """
    rows = build_evidence_rows(
        [
            _row(week=4, n_analyzed=40, responders=0, percent=0.0),
            _row(week=24, n_analyzed=24, responders=22, percent=91.7),
        ]
    )
    assert rows == []


def test_loading_dose_arms_stay_apart() -> None:
    """Ritlecitinib 50 mg QD was three arms: 12.1%, 8.5% and 7.7% F-VASI75."""
    common: dict[str, Any] = {
        "source_id": "NCT03715829",
        "arm_agent": "ritlecitinib",
        "dose_value": 50.0,
        "dose_unit": "mg",
        "frequency": "QD",
        "route": "oral",
        "assessor": "central",
    }
    rows = build_evidence_rows(
        [
            _row(**common, loading_dose_value=200.0, n_analyzed=58, responders=7, percent=12.1),
            _row(**common, loading_dose_value=100.0, n_analyzed=59, responders=5, percent=8.5),
            _row(**common, loading_dose_value=None, n_analyzed=52, responders=4, percent=7.7),
        ]
    )
    assert sorted(((r.loading_dose or 0.0), r.percent) for r in rows) == [
        (0.0, 7.7),
        (100.0, 8.5),
        (200.0, 12.1),
    ]


def test_central_read_wins_over_a_larger_local_read() -> None:
    """Ritlecitinib 10 mg read 7.0% centrally and 18.4% locally at week 24."""
    rows = build_evidence_rows(
        [
            _row(
                source_id="NCT03715829",
                assessor="central",
                n_analyzed=43,
                responders=3,
                percent=7.0,
            ),
            _row(
                source_id="NCT03715829", assessor="local", n_analyzed=49, responders=9, percent=18.4
            ),
        ]
    )
    assert [(r.assessor, r.percent) for r in rows] == [("central", 7.0)]


def test_a_smaller_central_read_is_not_mistaken_for_attrition() -> None:
    """The central series peaked at 59 and the local at 67; 52 of 59 is not a loss."""
    local: dict[str, Any] = {"source_id": "NCT03715829", "assessor": "local"}
    central: dict[str, Any] = {"source_id": "NCT03715829", "assessor": "central"}
    rows = build_evidence_rows(
        [
            _row(**local, week=4, n_analyzed=67, responders=0, percent=0.0),
            _row(**local, week=24, n_analyzed=65, responders=4, percent=6.2),
            _row(**central, week=4, n_analyzed=59, responders=0, percent=0.0),
            _row(**central, week=24, n_analyzed=52, responders=4, percent=7.7),
        ]
    )
    assert [(r.assessor, r.percent, r.analysed) for r in rows] == [("central", 7.7, 52)]


def test_open_label_continuation_is_reported_apart_from_the_controlled_week() -> None:
    """TRuE-V2's 48.0% of 177 at week 52 has no comparator: both arms were on drug."""
    rows = build_evidence_rows(
        [
            _row(
                source_id="NCT04057573",
                arm_label="Double-Blind Period: Ruxolitinib Cream 1.5% BID",
                n_analyzed=222,
                responders=69,
                percent=30.9,
            ),
            _row(
                source_id="NCT04057573",
                arm_label="Double-Blind Period: Vehicle Cream BID",
                arm_role="placebo",
                arm_agent=None,
                n_analyzed=109,
                responders=12,
                percent=11.4,
            ),
            _row(
                source_id="NCT04057573",
                arm_label="Treatment-Extension Period: Ruxolitinib Cream 1.5% BID",
                week=52,
                n_analyzed=177,
                responders=85,
                percent=48.0,
                outcome_type="SECONDARY",
                flags=["extension_period"],
            ),
        ]
    )
    assert len(rows) == 1
    row = rows[0]
    assert (row.week, row.percent, row.control_percent, row.difference) == (24, 30.9, 11.4, 19.5)
    assert row.later is not None
    assert (row.later.week, row.later.percent, row.later.analysed) == (52, 48.0, 177)
    assert row.later.retention == 0.797


def test_phototherapy_is_not_folded_into_the_drug_alone() -> None:
    """Ruxolitinib with NB-UVB read 76.5%; ruxolitinib alone read 51.4%."""
    rows = build_evidence_rows(
        [
            _row(
                endpoint="F-VASI50",
                instrument="F-VASI",
                threshold=50,
                n_analyzed=222,
                responders=114,
                percent=51.4,
            ),
            _row(
                endpoint="F-VASI50",
                instrument="F-VASI",
                threshold=50,
                phototherapy=True,
                source_id="NCT05247489",
                n_analyzed=34,
                responders=26,
                percent=76.5,
            ),
        ]
    )
    assert sorted((r.phototherapy, r.percent) for r in rows) == [(False, 51.4), (True, 76.5)]


def test_payload_states_the_week_and_carries_retention() -> None:
    rows = build_evidence_rows([_row()])
    payload = evidence_to_dict(rows)
    assert payload["week"] == 24
    assert payload["count"] == 1
    assert "which patients its figure counted" in str(payload["note"])
    assert payload["rows"][0]["difference"] is None


def test_a_second_trial_of_the_same_dose_is_reported_beside_it() -> None:
    """TRuE-V1 read 29.8% of 221 and TRuE-V2 30.9% of 222: the agreement is the finding.

    Only the larger arm heads the row, so without this the first trial is invisible.
    """
    rows = build_evidence_rows(
        [
            _row(source_id="NCT04057573", n_analyzed=222, responders=69, percent=30.9),
            _row(source_id="NCT04052425", n_analyzed=221, responders=66, percent=29.8),
            _row(
                source_id="NCT04052425",
                arm_role="placebo",
                arm_agent=None,
                arm_label="Vehicle Cream BID",
                n_analyzed=109,
                responders=8,
                percent=7.4,
            ),
        ]
    )
    assert len(rows) == 1
    assert (rows[0].trial, rows[0].percent) == ("NCT04057573", 30.9)
    assert [(o.trial, o.percent, o.analysed, o.control_percent) for o in rows[0].also_reported] == [
        ("NCT04052425", 29.8, 221, 7.4)
    ]


def test_as_observed_rows_are_labelled_rather_than_dropped() -> None:
    """Dropping them took the clinician table from 66 rows to 17.

    Ritlecitinib and povorcitinib report only the patients assessed at a visit,
    so excluding that population deletes both drugs from the page entirely. The
    page shows each figure with what it counted; the model, which has to combine
    them arithmetically, is the part that excludes.
    """
    rows = build_evidence_rows(
        [
            _row(
                source_id="NCT03715829",
                arm_agent="ritlecitinib",
                dose_value=50.0,
                dose_unit="mg",
                frequency="QD",
                route="oral",
                assessor="central",
                n_analyzed=58,
                responders=7,
                percent=12.1,
                flags=["population:as_observed"],
            )
        ]
    )
    assert len(rows) == 1
    assert rows[0].population == "as_observed"
    assert rows[0].population_note == "counts only patients assessed at that visit"


def test_a_subgroup_never_reaches_the_page() -> None:
    """A sex or age subgroup is not the arm that was randomised."""
    assert build_evidence_rows([_row(flags=["population:subgroup"])]) == []


def test_a_continuation_states_its_own_population() -> None:
    """TRuE-V's week 24 and week 52 figures were not measured the same way."""
    rows = build_evidence_rows(
        [
            _row(
                source_id="NCT04057573",
                arm_label="Double-Blind Period: Ruxolitinib Cream 1.5% BID",
                n_analyzed=222,
                responders=69,
                percent=30.9,
                flags=["population:multiple_imputation"],
            ),
            _row(
                source_id="NCT04057573",
                arm_label="Treatment-Extension Period: Ruxolitinib Cream 1.5% BID",
                week=52,
                n_analyzed=177,
                responders=85,
                percent=48.0,
                outcome_type="SECONDARY",
                flags=["extension_period", "population:as_observed"],
            ),
        ]
    )
    assert len(rows) == 1
    assert rows[0].population == "multiple_imputation"
    assert rows[0].later is not None
    assert rows[0].later.population == "as_observed"


def test_a_continuation_is_bracketed_by_the_group_it_started_with() -> None:
    """48.0% of 177 is the most favourable reading; over 222 it is 38.3-58.6%."""
    rows = build_evidence_rows(
        [
            _row(
                source_id="NCT04057573",
                arm_label="Double-Blind Period: Ruxolitinib Cream 1.5% BID",
                n_analyzed=222,
                responders=69,
                percent=30.9,
                flags=["population:multiple_imputation"],
            ),
            _row(
                source_id="NCT04057573",
                arm_label="Treatment-Extension Period: Ruxolitinib Cream 1.5% BID",
                week=52,
                n_analyzed=177,
                responders=85,
                percent=48.0,
                outcome_type="SECONDARY",
                flags=["extension_period", "population:as_observed"],
            ),
        ]
    )
    assert len(rows) == 1
    later = rows[0].later
    assert later is not None
    bounds = later.bounds
    assert bounds is not None
    assert (bounds.floor, bounds.ceiling, bounds.group, bounds.missing) == (38.3, 58.6, 222, 45)


def test_the_payload_serves_the_bracket() -> None:
    rows = build_evidence_rows(
        [
            _row(n_analyzed=222, responders=69, percent=30.9),
            _row(
                arm_label="Treatment-Extension Period: Ruxolitinib Cream 1.5% BID",
                week=52,
                n_analyzed=177,
                responders=85,
                percent=48.0,
                outcome_type="SECONDARY",
                flags=["extension_period"],
            ),
        ]
    )
    payload = evidence_to_dict(rows)
    served = payload["rows"][0]["later"]["bounds"]
    assert served == {
        "floor": 38.3,
        "ceiling": 58.6,
        "group": 222,
        "missing": 45,
        "width": 20.3,
    }
