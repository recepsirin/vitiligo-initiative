"""Unit tests for the JAK-inhibitor atlas: agent matching and CT.gov results parsing."""

from __future__ import annotations

from typing import Any

import pytest

from vitiligo.reports.jak import (
    _dedupe_sponsors,
    _jak_with_phototherapy_arm,
    _routes,
    match_agents,
    outcome_domains,
    parse_ctgov_adverse_events,
    parse_ctgov_outcomes,
)
from vitiligo.storage import Trial, TrialSourceKind


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ruxolitinib cream 1.5%", ["ruxolitinib"]),
        ("A Study of INCB018424 Phosphate Cream", ["ruxolitinib"]),
        ("INCB 18424-309", ["ruxolitinib"]),
        ("Deuruxolitinib 8 mg", ["deuruxolitinib"]),  # must not also match ruxolitinib
        ("PF-06651600 and PF-06700841", ["ritlecitinib", "brepocitinib"]),
        ("pf06651600 capsule", ["ritlecitinib"]),
        ("Ritlecitinib tosilate", ["ritlecitinib"]),
        ("SHR0302 Base Gel", ["ivarmacitinib"]),
        ("ATI-50002 topical solution", ["ifidancitinib"]),
        ("ZASOCITINIB / TAK-279", ["zasocitinib"]),
        ("Anzupgo 20 mg/g cream", ["delgocitinib"]),
        ("Tacrolimus ointment", []),
        ("JAK-2 inhibitor", []),  # class mentions are not agents
    ],
)
def test_match_agents(text: str, expected: list[str]) -> None:
    assert match_agents(text) == expected


def _trial(**kwargs: Any) -> Trial:
    return Trial(source=TrialSourceKind.CTGOV, source_id="NCT00000000", **kwargs)


def test_routes_ignore_placebo_and_vehicle() -> None:
    trial = _trial(
        interventions=[
            {"name": "Ruxolitinib cream", "description": "Cream BID", "other_names": []},
            {"name": "Placebo tablet matching ruxolitinib", "description": "", "other_names": []},
        ]
    )
    assert _routes(trial) == ["topical"]


def test_jak_with_phototherapy_arm_states() -> None:
    combo = _trial(
        arm_groups=[
            {
                "label": "Ritlecitinib + NB-UVB",
                "type": "EXPERIMENTAL",
                "intervention_names": ["Drug: Ritlecitinib", "Device: NB-UVB"],
            }
        ]
    )
    assert _jak_with_phototherapy_arm(combo) is True

    comparator = _trial(
        interventions=[{"name": "PUVA"}, {"name": "Tofacitinib"}],
        arm_groups=[
            {"label": "A", "type": "ACTIVE_COMPARATOR", "intervention_names": ["Drug: PUVA"]},
            {"label": "B", "type": "EXPERIMENTAL", "intervention_names": ["Drug: Tofacitinib"]},
        ],
    )
    assert _jak_with_phototherapy_arm(comparator) is False

    title_only = _trial(
        brief_title="Tofacitinib in combination with NB-UVB",
        interventions=[{"name": "Tofacitinib"}],
        arm_groups=[{"label": "B", "intervention_names": ["Drug: Tofacitinib"]}],
    )
    assert _jak_with_phototherapy_arm(title_only) is None

    assert _jak_with_phototherapy_arm(_trial(arm_groups=[])) is None


def _study_with_results() -> dict[str, Any]:
    return {
        "resultsSection": {
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "type": "PRIMARY",
                        "title": "Percentage of Participants Achieving F-VASI75 at Week 24",
                        "paramType": "NUMBER",
                        "unitOfMeasure": "percentage of participants",
                        "timeFrame": "Week 24",
                        "reportingStatus": "POSTED",
                        "groups": [
                            {"id": "OG000", "title": "Ruxolitinib"},
                            {"id": "OG001", "title": "Vehicle"},
                        ],
                        "denoms": [
                            {
                                "units": "Participants",
                                "counts": [
                                    {"groupId": "OG000", "value": "221"},
                                    {"groupId": "OG001", "value": "109"},
                                ],
                            }
                        ],
                        "classes": [
                            {
                                "categories": [
                                    {
                                        "measurements": [
                                            {"groupId": "OG000", "value": "29.8"},
                                            {"groupId": "OG001", "value": "7.4"},
                                        ]
                                    }
                                ]
                            },
                            {
                                "title": "Week 52",
                                "denoms": [
                                    {
                                        "units": "Participants",
                                        "counts": [{"groupId": "OG000", "value": "180"}],
                                    }
                                ],
                                "categories": [
                                    {
                                        "title": "Responders",
                                        "measurements": [
                                            {
                                                "groupId": "OG000",
                                                "value": "50.3",
                                                "lowerLimit": "43.0",
                                                "upperLimit": "57.6",
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                        "analyses": [
                            {
                                "groupIds": ["OG000", "OG001"],
                                "pValue": "< 0.0001",
                                "paramType": "Odds Ratio (OR)",
                                "paramValue": "5.28",
                                "statisticalComment": "dropped",
                            }
                        ],
                    }
                ]
            },
            "adverseEventsModule": {
                "timeFrame": "52 weeks",
                "frequencyThreshold": "5",
                "eventGroups": [
                    {
                        "id": "EG000",
                        "title": "Ruxolitinib",
                        "seriousNumAffected": 8,
                        "seriousNumAtRisk": 311,
                        "otherNumAffected": 40,
                        "otherNumAtRisk": 311,
                        "deathsNumAffected": 0,
                        "deathsNumAtRisk": 311,
                    }
                ],
            },
        }
    }


def test_parse_ctgov_outcomes_keeps_values_verbatim() -> None:
    [outcome] = parse_ctgov_outcomes(_study_with_results())
    assert outcome.type == "PRIMARY"
    assert outcome.domains == ["repigmentation"]
    week24 = [m for m in outcome.measurements if m.class_title is None]
    assert [(m.group_title, m.value, m.n_analyzed) for m in week24] == [
        ("Ruxolitinib", "29.8", "221"),
        ("Vehicle", "7.4", "109"),
    ]
    [week52] = [m for m in outcome.measurements if m.class_title == "Week 52"]
    # Class-level denominators override the measure-level ones.
    assert (week52.n_analyzed, week52.category_title) == ("180", "Responders")
    assert (week52.lower_limit, week52.upper_limit) == ("43.0", "57.6")
    assert outcome.analyses == [
        {
            "groupIds": ["OG000", "OG001"],
            "pValue": "< 0.0001",
            "paramType": "Odds Ratio (OR)",
            "paramValue": "5.28",
        }
    ]


def test_parse_ctgov_adverse_events() -> None:
    ae = parse_ctgov_adverse_events(_study_with_results())
    assert ae is not None
    assert ae.other_frequency_threshold == "5"
    [group] = ae.groups
    assert (group.serious_affected, group.serious_at_risk, group.other_affected) == (8, 311, 40)


def test_parsers_tolerate_missing_results() -> None:
    assert parse_ctgov_outcomes({}) == []
    assert parse_ctgov_adverse_events({}) is None


def test_outcome_domains() -> None:
    assert outcome_domains("Change in T-VASI", None) == ["repigmentation"]
    assert outcome_domains("Number of participants with TEAEs", "adverse events") == ["safety"]
    assert outcome_domains("Plasma concentration of drug", None) == ["pharmacokinetics"]


def test_dedupe_sponsors_folds_registry_spellings() -> None:
    names = [
        "Pfizer",
        "Pfizer Inc.",
        "Incyte Corporation",
        "Incyte Corp.",
        "Centre Hospitalier Universitaire de Nice",
        "Centre Hospitalier Universitaire De Nice",
        "AbbVie Deutschland GmbH & Co. KG",
        "AbbVie",
    ]
    assert _dedupe_sponsors(names) == [
        "Pfizer",
        "Incyte Corporation",
        "Centre Hospitalier Universitaire de Nice",
        "AbbVie Deutschland GmbH & Co. KG",
        "AbbVie",
    ]
