"""Tests for tier-2 forecasting of unreported trials and their resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from vitiligo.discovery import forecasts as fc
from vitiligo.discovery.ledger import Ledger, verify_seal
from vitiligo.reports.jak_arms import ArmEndpointRow


@pytest.mark.parametrize(
    ("measure", "expected"),
    [
        (
            "US only Co-Primary Endpoints: Response based on Facial Vitiligo Area Scoring Index 75 "
            "(F-VASI75) at Week 52 and Total body Vitiligo Area Scoring Index 50 (T-VASI50) at Week 52",
            [("F-VASI", 75), ("T-VASI", 50)],
        ),
        (
            "Percentage of Participants Achieving Total Vitiligo Area Scoring Index (T-VASI) 50 "
            "(≥ 50% Improvement in T-VASI From Baseline)",
            [("T-VASI", 50)],
        ),
        (
            "Percentage of Participants Achieving >= 75% Improvement From Baseline in Facial Vitiligo "
            "Area Scoring Index",
            [("F-VASI", 75)],
        ),
        (
            "The percentage change in the facial vitiligo area score index (F-VASI) from baseline",
            [],
        ),
        ("Incidence of treatment-emergent adverse events", []),
    ],
)
def test_registry_endpoints(measure: str, expected: list[tuple[str, int]]) -> None:
    assert fc.registry_endpoints(measure) == expected


@pytest.mark.parametrize(
    ("time_frame", "measure", "expected"),
    [
        ("52 Weeks", "", 52),
        ("Baseline, Week 24", "", 24),
        ("At Week 24.", "", 24),
        (None, "F-VASI75 at Week 48", 48),
        ("Weeks 24 and 36", "", None),
    ],
)
def test_registry_week(time_frame: str | None, measure: str, expected: int | None) -> None:
    assert fc.registry_week(time_frame, measure) == expected


def _protocol(arms: list[dict[str, str]], primaries: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "armsInterventionsModule": {"armGroups": arms},
        "outcomesModule": {
            "primaryOutcomes": [{"measure": m, "timeFrame": t} for m, t in primaries]
        },
    }


F75_W52 = ("Response based on F-VASI75 at Week 52", "52 Weeks")


def test_registry_targets_follow_the_registered_design() -> None:
    tranquillo2 = _protocol(
        [
            {"type": "EXPERIMENTAL", "label": "Arm 1- Ritlecitinib 100 milligrams (mg)",
             "description": "Randomized to Ritlecitinib 100 mg QD for 52 weeks before the titration extension period."},
            {"type": "PLACEBO_COMPARATOR", "label": "Arm 3- Placebo", "description": "Placebo QD for 52 weeks."},
            {"type": "EXPERIMENTAL", "label": "Arm 4- Ritlecitinib 100mg",
             "description": "Non-randomized open-label Ritlecitinib 100mg QD for 52 weeks."},
        ],
        [F75_W52, ("US only: Response based on F-VASI75 at Week 52", "52 Weeks")],
    )  # fmt: skip
    upa = _protocol(
        [
            {"type": "EXPERIMENTAL", "label": "Study 1, Period A: Group 1",
             "description": "Participants will receive upadacitinib 15 mg once daily for 48 weeks."},
            {"type": "PLACEBO_COMPARATOR", "label": "Study 1, Period A: Group 2", "description": "Placebo once daily."},
            {"type": "EXPERIMENTAL", "label": "Study 1, Period B: Group 1 Open-Label Extension Period",
             "description": "upadacitinib 15 mg once daily"},
        ],
        [("Percentage of Participants Achieving F-VASI 75 at Week 48", "Week 48")],
    )  # fmt: skip
    rux = _protocol(
        [
            {"type": "EXPERIMENTAL", "label": "Ruxolitinib 1.5 % Cream", "description": "applied as defined in the protocol"},
            {"type": "PLACEBO_COMPARATOR", "label": "Vehicle Cream", "description": ""},
        ],
        [("Proportion achieving a ≥ 75% Improvement From Baseline in the Facial VASI (F-VASI75)", "Week 24")],
    )  # fmt: skip
    povo = _protocol(
        [
            {
                "type": "EXPERIMENTAL",
                "label": "Experimental: Povorcitinib Dose A",
                "description": "",
            },
            {"type": "PLACEBO_COMPARATOR", "label": "Placebo", "description": ""},
        ],
        [F75_W52],
    )
    zaso = _protocol(
        [
            {"type": "EXPERIMENTAL", "label": "Zasocitinib 10 mg", "description": ""},
            {
                "type": "EXPERIMENTAL",
                "label": "Placebo Group 1/ Zasocitinib Medium Dose",
                "description": "",
            },
        ],
        [F75_W52],
    )
    targets, skips = fc.registry_targets(
        [
            ("NCT2", "ACTIVE_NOT_RECRUITING", tranquillo2),
            ("NCTU", "ACTIVE_NOT_RECRUITING", upa),
            ("NCTR", "RECRUITING", rux),
            ("NCTP", "ACTIVE_NOT_RECRUITING", povo),
            ("NCTZ", "RECRUITING", zaso),
            ("NCTT", "TERMINATED", rux),
        ]
    )
    by_trial = {(t.trial, t.arm_label, t.instrument, t.threshold, t.week) for t in targets}
    assert by_trial == {
        ("NCT2", "Arm 1- Ritlecitinib 100 milligrams (mg)", "F-VASI", 75, 52),  # once, not twice
        ("NCTU", "Study 1, Period A: Group 1", "F-VASI", 75, 48),
        ("NCTR", "Ruxolitinib 1.5 % Cream", "F-VASI", 75, 24),
    }
    upa_target = next(t for t in targets if t.trial == "NCTU")
    assert (upa_target.dose_value, upa_target.frequency, upa_target.group) == (
        15.0,
        "QD",
        "Study 1, Period A",
    )
    rux_target = next(t for t in targets if t.trial == "NCTR")
    assert rux_target.frequency is None and "QD/BID mixture" in rux_target.assumptions[0]
    reasons = {s.trial: s.reason for s in skips}
    assert "dose not disclosed" in reasons["NCTP"]
    assert "switches to active" in reasons["NCTZ"]
    assert reasons["NCTT"] == "status TERMINATED"


def _target(**kwargs: Any) -> fc.ForecastTarget:
    base: dict[str, Any] = {
        "trial": "NCT9", "group": None, "arm_label": "Drug 50 mg", "control_label": "Placebo",
        "agent": "ritlecitinib", "dose_value": 50.0, "dose_unit": "mg", "frequency": "QD",
        "phototherapy": False, "instrument": "F-VASI", "threshold": 75, "week": 52,
        "registry_measure": "F-VASI75 at week 52",
    }  # fmt: skip
    base.update(kwargs)
    return fc.ForecastTarget(**base)


def test_forecast_mixes_frequencies_when_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []

    def fake_draws(posterior: Any, scenario: Any, **_: Any) -> tuple[np.ndarray, np.ndarray]:
        seen.append(scenario.frequency)
        level = 0.4 if scenario.frequency == "BID" else 0.2
        return np.full(1000, level), np.full(1000, 0.05)

    monkeypatch.setattr(fc, "predict_draws", fake_draws)
    monkeypatch.setattr(fc, "_extrapolation_notes", lambda posterior, scenario: [])
    summary, p_active, _ = fc.forecast_target(object(), _target(frequency=None), routes={})  # type: ignore[arg-type]
    assert seen == ["QD", "BID"]
    assert sorted(set(p_active.round(2))) == [0.2, 0.4]
    assert summary["p_active_beats_control"] == 1.0


def _sealed(tmp_path: Path, target: fc.ForecastTarget) -> tuple[Path, dict[str, Any]]:
    rng = np.random.default_rng(0)
    p_active = np.clip(rng.normal(0.30, 0.05, 2000), 0.01, 0.99)
    p_control = np.clip(rng.normal(0.08, 0.02, 2000), 0.01, 0.99)
    summary = {
        "p_active": fc.asdict(fc.Interval.of(p_active)),
        "p_control": fc.asdict(fc.Interval.of(p_control)),
        "difference": fc.asdict(fc.Interval.of(p_active - p_control)),
        "p_active_beats_control": 1.0,
        "extrapolation": [],
    }
    return fc.write_forecast(target, summary, p_active, p_control, tmp_path / "f", context={})


def _posted(trial: str, role: str, dose: float | None, r: int, n: int) -> ArmEndpointRow:
    active = role == "active"
    return ArmEndpointRow(
        study_id=trial, source_id=trial, trial_agents="ritlecitinib", arm_label="x", period=None,
        arm_role=role, arm_agent="ritlecitinib" if active else None, dose_value=dose,
        dose_unit="mg" if active else None, loading_dose_value=None, frequency="QD" if active else None,
        route="oral", phototherapy=False, endpoint="F-VASI75", instrument="F-VASI", threshold=75,
        body_region="face", assessor=None, week=52, week_source="outcome_title", outcome_type="PRIMARY",
        n_analyzed=n, percent=100 * r / n, responders=r, responders_derived=False, value_raw=str(r),
        outcome_title="F-VASI75 at Week 52", row_label=None, flags=[],
    )  # fmt: skip


def test_write_forecast_seals_record_and_draws(tmp_path: Path) -> None:
    path, record = _sealed(tmp_path, _target())
    assert verify_seal(json.loads(path.read_text()))
    assert (path.parent / record["draws_file"]).is_file()
    assert record["target"]["key"] == _target().key


def test_resolve_scores_posted_results_and_leaves_others_pending(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.db")
    path, record = _sealed(tmp_path, _target())
    ledger.import_forecast(record, str(path))
    other_path, other = _sealed(tmp_path, _target(trial="NCT8", arm_label="Other 50 mg"))
    ledger.import_forecast(other, str(other_path))

    rows = [_posted("NCT9", "active", 50.0, 120, 400), _posted("NCT9", "placebo", None, 16, 200)]
    results = {r.label: r for r in fc.resolve(ledger, rows)}
    done = results[record["label"]]
    assert done.resolved
    assert done.detail["active_in80"] and done.detail["direction_correct"]
    assert done.detail["log_score"] < 0
    assert not results[other["label"]].resolved
    assert [label for _s, label, _f, _r in ledger.pending_forecasts()] == [other["label"]]


def test_resolve_reconstructs_targets_of_manual_forecasts(tmp_path: Path) -> None:
    from vitiligo.models.jak_mbma import freeze

    ledger = Ledger(tmp_path / "ledger.db")
    manual = freeze(
        {
            "label": "Tranquillo NCT05583526: ritlecitinib 50 mg QD vs placebo, F-VASI75 at week 52",
            "dataset": {"instrument": "F-VASI"},
            "prediction": {
                "scenario": {"agent": "ritlecitinib", "dose": 50.0, "frequency": "QD", "threshold": 75, "week": 52},
                "p_active": {"lo80": 0.1, "hi80": 0.8, "lo95": 0.05, "hi95": 0.9},
                "difference": {"lo80": 0.05, "hi80": 0.6},
                "p_active_beats_control": 0.98,
            },
        }
    )  # fmt: skip
    ledger.import_forecast(manual, "manual.json")
    rows = [
        _posted("NCT05583526", "active", 50.0, 160, 400),
        _posted("NCT05583526", "placebo", None, 20, 200),
    ]
    [result] = fc.resolve(ledger, rows)
    assert result.resolved and result.detail["active_in80"] and "log_score" not in result.detail


def test_sealing_requires_a_public_results_check(tmp_path: Path) -> None:
    """Registry status alone missed public toplines; sealing must record a wider search."""
    from typer.testing import CliRunner

    from vitiligo.cli import app

    runner = CliRunner()
    frozen = runner.invoke(
        app,
        ["model", "predict", "--agent", "x", "--dose", "1", "--freeze", str(tmp_path / "f.json")],
    )
    assert frozen.exit_code == 2 and "--public-results-check" in frozen.output
    assert not (tmp_path / "f.json").exists()
    pending = runner.invoke(app, ["discover", "forecast-pending", "--out", str(tmp_path / "o")])
    assert pending.exit_code == 2  # the option is required
    blank = runner.invoke(
        app,
        [
            "discover",
            "forecast-pending",
            "--out",
            str(tmp_path / "o"),
            "--public-results-check",
            " ",
        ],
    )
    assert blank.exit_code == 2 and not (tmp_path / "o").exists()


def _posted_study(nct: str, active_pct: str, control_pct: str) -> dict[str, Any]:
    """A minimal ClinicalTrials.gov v2 study with posted F-VASI75 results at week 24."""
    groups = [{"id": "OG000", "title": "Ruxolitinib 1.5% Cream BID"},
              {"id": "OG001", "title": "Vehicle Cream BID"}]  # fmt: skip
    return {
        "hasResults": True,
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": "Ruxolitinib cream in vitiligo"},
            "conditionsModule": {"conditions": ["Vitiligo"]},
            "statusModule": {"overallStatus": "COMPLETED"},
            "armsInterventionsModule": {
                "armGroups": [
                    {"label": "Ruxolitinib 1.5% Cream BID", "type": "EXPERIMENTAL",
                     "interventionNames": ["Drug: Ruxolitinib cream"]},
                    {"label": "Vehicle Cream BID", "type": "PLACEBO_COMPARATOR",
                     "interventionNames": ["Drug: Vehicle cream"]},
                ],
                "interventions": [{"type": "DRUG", "name": "Ruxolitinib cream"},
                                  {"type": "DRUG", "name": "Vehicle cream"}],
            },
        },
        "resultsSection": {"outcomeMeasuresModule": {"outcomeMeasures": [{
            "type": "PRIMARY", "title": "Percentage of Participants Achieving F-VASI75 at Week 24",
            "paramType": "NUMBER", "unitOfMeasure": "percentage of participants",
            "timeFrame": "Week 24", "reportingStatus": "POSTED", "groups": groups,
            "denoms": [{"units": "Participants", "counts": [
                {"groupId": "OG000", "value": "200"}, {"groupId": "OG001", "value": "100"}]}],
            "classes": [{"categories": [{"measurements": [
                {"groupId": "OG000", "value": active_pct}, {"groupId": "OG001", "value": control_pct}]}]}],
        }]}},
    }  # fmt: skip


def test_check_forecasts_scores_sealed_files_straight_from_the_registry(tmp_path: Path) -> None:
    target = _target(
        trial="NCT09999999", arm_label="Ruxolitinib 1.5% Cream BID", control_label="Vehicle Cream BID",
        agent="ruxolitinib", dose_value=1.5, dose_unit="%", frequency="BID", week=24,
    )  # fmt: skip
    path, _record = _sealed(tmp_path, target)
    pending_path, _ = _sealed(tmp_path, _target(trial="NCT08888888"))
    fetched: list[str] = []

    def fetch(nct: str) -> dict[str, Any] | None:
        fetched.append(nct)
        return _posted_study(nct, "30.0", "8.0") if nct == "NCT09999999" else None

    results = dict(fc.check_forecasts([tmp_path], fetch))
    assert sorted(fetched) == ["NCT08888888", "NCT09999999"]
    scored = results[path]
    assert scored.resolved and scored.detail["observed"]["responders_active"] == 60
    assert scored.detail["active_in80"] and scored.detail["direction_correct"]
    assert scored.detail["log_score"] < 0
    assert not results[pending_path].resolved

    tampered = json.loads(path.read_text()) | {"label": "edited"}
    path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="seal"):
        fc.check_forecasts([tmp_path], fetch)


def test_compare_models_uses_targets_scored_by_every_model() -> None:
    def record(trial: str, week: int = 24) -> dict[str, Any]:
        return {"target": {"trial": trial, "instrument": "F-VASI", "threshold": 75, "week": week,
                           "dose_value": 1.5}}  # fmt: skip

    def res(score: float | None) -> fc.Resolution:
        detail = {"log_score": score} if score is not None else {"reason": "results not posted yet"}
        return fc.Resolution("s", "l", score is not None, detail)

    scored = [
        ("v0.2", record("A"), res(-5.0)), ("v0.4", record("A"), res(-4.0)),
        ("v0.2", record("B"), res(-6.0)), ("v0.4", record("B"), res(None)),  # B unresolved for v0.4
        ("v0.2", record("C"), res(None)), ("v0.4", record("C"), res(None)),
    ]  # fmt: skip
    out = fc.compare_models(scored)
    assert out == {"v0.2 vs v0.4": {"targets": 1, "v0.2": -5.0, "v0.4": -4.0}}
    # Manual records are matched by their reconstructed target.
    manual = {"label": "Tranquillo NCT05583526: x", "dataset": {"instrument": "F-VASI"},
              "prediction": {"scenario": {"agent": "r", "dose": 50.0, "threshold": 75, "week": 24}}}  # fmt: skip
    assert fc.comparison_key(manual) == ("NCT05583526", "F-VASI", 75, 24, 50.0)
