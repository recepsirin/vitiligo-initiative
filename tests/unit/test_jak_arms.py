"""Unit tests for the harmonized JAK arm table (labels taken from real registry records)."""

from __future__ import annotations

from typing import Any

import pytest

from vitiligo.reports.jak import JakAtlas, JakTrial, Measurement, OutcomeResult
from vitiligo.reports.jak_arms import (
    analysis_population,
    harmonize_arms,
    parse_arm,
    parse_endpoint,
    parse_week,
    summarize_arms,
)


def _trial(agents: list[str], routes: list[str] | None = None, **kwargs: Any) -> JakTrial:
    base: dict[str, Any] = {
        "study_id": "NCT00000001",
        "linked_records": [],
        "agents": agents,
        "match_basis": "registry_text",
        "source": "ctgov",
        "source_id": "NCT00000001",
        "url": None,
        "title": "A study",
        "status": "COMPLETED",
        "phases": ["PHASE2"],
        "stage": "PHASE_2",
        "study_type": "INTERVENTIONAL",
        "jak_arm_types": [],
        "routes": routes or [],
        "phototherapy_in_trial": False,
        "jak_with_phototherapy_arm": False,
        "lead_sponsor": None,
        "sponsor_class": None,
        "enrollment": None,
        "start_date": None,
        "completion_date": None,
        "countries": [],
        "has_results": True,
        "outcomes": [],
        "adverse_events": None,
        "publications": [],
    }
    base.update(kwargs)
    return JakTrial(**base)


@pytest.mark.parametrize(
    ("title", "row_label", "expected"),
    [
        (
            "Percentage of Participants Achieving a ≥ 75% Improvement From Baseline in the "
            "Face Vitiligo Area Scoring Index (F-VASI75) Score at Week 24",
            None,
            "F-VASI75",
        ),
        ("Percentage of Participants Achieving F-VASI 50 at Week 24", None, "F-VASI50"),
        ("Percentage of Participants Achieving T-VASI50 at Week 24", None, "T-VASI50"),
        # Several thresholds in the title: the row label decides; without it, nothing.
        ("... (F-VASI25/50/75/90) Score at Week 52", "F-VASI90", "F-VASI90"),
        ("... (F-VASI25/50/75/90) Score at Week 52", None, None),
        ("Achieving a ≥ 25%, ≥ 50%, and ≥ 75% Improvement in the Face Vitiligo Area", None, None),
        (
            'Achieving a Genital VNS of "4 - A Lot Less Noticeable" or "5 - No Longer Noticeable"',
            None,
            "VNS 4-5 responder (genital)",
        ),
        # Category distributions and continuous scores are not responder rates.
        ("Percentage of Participants in Each Category of VNS", "Week 24, as noticeable", None),
        ("Percent Change From Baseline in T-VASI", "Week 24", None),
    ],
)
def test_parse_endpoint(title: str, row_label: str | None, expected: str | None) -> None:
    endpoint = parse_endpoint(title, row_label)
    assert (endpoint.label if endpoint else None) == expected


@pytest.mark.parametrize(
    ("row_label", "title", "time_frame", "expected"),
    [
        ("Week 52", "F-VASI50 at Weeks 52, 104, and 156", None, (52, "row_label")),
        (None, "F-VASI75 at Week 24 - DR Period", "Week 24", (24, "outcome_title")),
        (None, "Percentage achieving F-VASI75", "Baseline; Week 24", (24, "time_frame")),
        (None, "Percentage achieving F-VASI75", "Baseline; up to Week 48", (None, None)),
        (None, "T-VASI50 at Designated Time Points", "Baseline, Weeks 4, 8 and 24", (None, None)),
    ],
)
def test_parse_week(
    row_label: str | None,
    title: str,
    time_frame: str | None,
    expected: tuple[int | None, str | None],
) -> None:
    assert parse_week(row_label, title, time_frame) == expected


@pytest.mark.parametrize(
    ("label", "agents", "role", "dose", "loading", "frequency"),
    [
        (
            "Double-Blind Period: Ruxolitinib Cream 1.5% BID",
            ["ruxolitinib"],
            "active",
            1.5,
            None,
            "BID",
        ),
        ("Double-Blind Period: Vehicle Cream BID", ["ruxolitinib"], "placebo", None, None, "BID"),
        (
            "Treatment-Extension Period: Vehicle Cream to Ruxolitinib Cream 1.5% BID",
            ["ruxolitinib"],
            "sequence",
            None,
            None,
            "BID",
        ),
        ("Ruxolitinib Cream 1.5% QD: 1.5 % BID", ["ruxolitinib"], "sequence", None, None, "BID"),
        ("Ruxolitinib Cream 1.5% BID: 1.5% BID", ["ruxolitinib"], "active", 1.5, None, "BID"),
        (
            "Cohort B: Ruxolitinib 1.5% Cream BID to Ruxolitinib 1.5% Cream BID",
            ["ruxolitinib"],
            "active",
            1.5,
            None,
            "BID",
        ),
        (
            "PF-06651600 200 mg - 50 mg QD",
            ["ritlecitinib", "brepocitinib"],
            "active",
            50.0,
            200.0,
            "QD",
        ),
        ("Upa 6 mg Period 1, Then Upa 6 mg Period 2", ["upadacitinib"], "active", 6.0, None, None),
        ("Placebo Period 1", ["upadacitinib"], "placebo", None, None, None),
    ],
)
def test_parse_arm(
    label: str,
    agents: list[str],
    role: str,
    dose: float | None,
    loading: float | None,
    frequency: str | None,
) -> None:
    arm = parse_arm(label, _trial(agents))
    assert (arm.role, arm.dose_value, arm.loading_dose_value, arm.frequency) == (
        role,
        dose,
        loading,
        frequency,
    )


def test_parse_arm_infers_abbreviated_agent_and_route() -> None:
    arm = parse_arm(
        "Upa 11 mg Period 1, Then Upa 11 mg Period 2", _trial(["upadacitinib"], ["oral"])
    )
    assert (arm.agent, arm.route) == ("upadacitinib", "oral")
    assert set(arm.flags) == {"agent_inferred_from_trial", "route_inferred_from_trial"}


def _outcome(title: str, measurements: list[Measurement], **kwargs: Any) -> OutcomeResult:
    base: dict[str, Any] = {
        "type": "PRIMARY",
        "title": title,
        "description": None,
        "time_frame": "Baseline; Week 24",
        "param_type": "NUMBER",
        "dispersion_type": None,
        "unit": "percentage of participants",
        "reporting_status": "POSTED",
        "domains": [],
        "measurements": measurements,
        "analyses": [],
    }
    base.update(kwargs)
    return OutcomeResult(**base)


def _m(group: str, value: str | None, n: str | None, class_title: str | None = None) -> Measurement:
    return Measurement(
        group_id=group,
        group_title=group,
        class_title=class_title,
        category_title=None,
        value=value,
        spread=None,
        lower_limit=None,
        upper_limit=None,
        n_analyzed=n,
    )


def test_harmonize_arms_end_to_end() -> None:
    primary = _outcome(
        "Percentage of Participants Achieving F-VASI75 at Week 24",
        [
            _m("Ruxolitinib Cream 1.5% BID", "29.8", "221"),
            _m("Vehicle Cream BID", "7.4", "109"),
            _m("Treatment-Extension Period: Ruxolitinib Cream 1.5% BID", "NA", "0"),
        ],
    )
    repeated = _outcome(
        "Percentage of Participants Achieving F-VASI75 at Designated Time Points",
        [_m("Ruxolitinib Cream 1.5% BID", "29.8", "221", class_title="Week 24")],
        time_frame="Baseline, Weeks 12 and 24",
    )
    counts = _outcome(
        "Number of Participants Achieving T-VASI50 at Week 24",
        [_m("Ruxolitinib Cream 1.5% BID", "52", "200")],
        param_type="COUNT_OF_PARTICIPANTS",
        unit="Participants",
    )
    trial = _trial(["ruxolitinib"], outcomes=[primary, repeated, counts])
    atlas = JakAtlas(
        generated_at="t",
        engine_version="v",
        corpus={},
        methodology="",
        caveats=[],
        agents=[],
        trials=[trial],
    )

    rows = harmonize_arms(atlas)
    rux = [r for r in rows if r.endpoint == "F-VASI75" and r.arm_role == "active"]
    assert len(rux) == 2  # n=0 extension group skipped
    assert all(r.responders == 66 and r.responders_derived for r in rux)
    assert all("reported_twice" in r.flags for r in rux)
    vehicle = next(r for r in rows if r.arm_role == "placebo")
    assert (vehicle.percent, vehicle.responders, vehicle.week) == (7.4, 8, 24)
    t_vasi = next(r for r in rows if r.endpoint == "T-VASI50")
    assert (t_vasi.percent, t_vasi.responders, t_vasi.responders_derived) == (26.0, 52, False)

    summary = summarize_arms(rows)
    assert summary["model_ready_rows"] == 4
    assert summary["by_endpoint"] == {"F-VASI75": 3, "T-VASI50": 1}


# The exact population descriptions ClinicalTrials.gov carries for these trials.
_TRUE_V_WEEK_24 = (
    "Intent-to-Treat Population: all randomized participants. Treatment groups for this "
    "population were defined according to the treatment assignment at the time of "
    "randomization. Data from participants at a single site were excluded from this analysis "
    "owing to serious noncompliance with the protocol. Missing F-VASI scores were imputed by "
    "Multiple Imputation with Fully Conditional Specification."
)
_TRUE_V_WEEK_52 = (
    "ITT Population. Data from participants at a single site were excluded from this analysis "
    "owing to serious noncompliance with the protocol. Only participants with available data "
    "were analyzed."
)


def test_true_v_primary_endpoint_is_not_mistaken_for_a_subgroup() -> None:
    """Its imputation text also says a site "were excluded from this analysis".

    A subgroup pattern loose enough to match that discards the primary endpoint
    of both pivotal trials, which is the most important figure in the corpus.
    """
    assert analysis_population(_TRUE_V_WEEK_24) == "multiple_imputation"


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        (_TRUE_V_WEEK_52, "as_observed"),
        ("ITT Population. Only participants with available data were analyzed.", "as_observed"),
        # The registry really does contain this typo, after the matched phrase.
        ("Full Analysis Set. Only participants with available data wee analyzed.", "as_observed"),
        (
            "The analysis population included all participants who received at least 1 dose of "
            "randomized study medication and had a baseline and at least 1 post-baseline "
            "measurement. Number of participants analyzed signifies number of participants who "
            "were evaluable for this outcome measure.",
            "as_observed",
        ),
        (
            "ITT Population. Missing post-Baseline values were considered as not having achieved "
            "F-PhGVA response for visits up to Week 24.",
            "nri",
        ),
        (
            "ITT\\_1: all randomized participants in Period 1; NRI-MI (non-responder imputation "
            "incorporating multiple imputation to handle missing data)",
            "nri",
        ),
        (
            "ITT Population. Missing T-VASI scores were imputed by Multiple Imputation with "
            "Fully Conditional Specification.",
            "multiple_imputation",
        ),
        (
            "The number of participants analyzed for this outcome is a subset of the overall "
            "population: female sex subgroup",
            "subgroup",
        ),
        ("Patients with a pre-existing diagnosis of anxiety disorder were excluded", "subgroup"),
        # Stating a population is not the same as stating how missing data were handled.
        ("Full Analysis Set", None),
        ("Safety Population: all participants who received at least 1 dose of study drug.", None),
        ("", None),
        (None, None),
    ],
)
def test_analysis_population_reads_the_registry_phrasings(
    description: str | None, expected: str | None
) -> None:
    assert analysis_population(description) == expected


def test_both_phrases_present_reads_as_as_observed() -> None:
    """NCT03099304 week 52 claims non-responder imputation and then restricts the set.

    "Only participants with available data" fixes the denominator, and the
    denominator is what makes one rate incomparable with another.
    """
    mixed = (
        "ITT Population. Missing post-Baseline values were considered as not having achieved "
        "responses for visits up to Week 52. Only participants with available data were analyzed."
    )
    assert analysis_population(mixed) == "as_observed"


def test_rows_carry_the_population_their_measure_was_computed_on() -> None:
    week_24 = _outcome(
        "Percentage of Participants Achieving F-VASI75 at Week 24",
        [_m("Ruxolitinib Cream 1.5% BID", "30.9", "222")],
        population_description=_TRUE_V_WEEK_24,
    )
    week_52 = _outcome(
        "Percentage of Participants Achieving F-VASI75 at Week 52",
        [_m("Ruxolitinib Cream 1.5% BID", "48.0", "177")],
        time_frame="Baseline; Week 52",
        population_description=_TRUE_V_WEEK_52,
    )
    atlas = JakAtlas(
        generated_at="t",
        engine_version="v",
        corpus={},
        methodology="",
        caveats=[],
        agents=[],
        trials=[_trial(["ruxolitinib"], outcomes=[week_24, week_52])],
    )
    by_week = {r.week: r for r in harmonize_arms(atlas) if r.arm_role == "active"}
    assert "population:multiple_imputation" in by_week[24].flags
    assert "population:as_observed" in by_week[52].flags
