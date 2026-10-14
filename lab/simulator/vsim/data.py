"""Search and exam data, selected exactly as the benchmark selects them.

The search set S never contains a row after week 24; the exam set E is only
readable once a selection has been sealed (see ``exam.py``).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from vitiligo.models.jak_mbma import build_dataset
from vitiligo.reports.jak_arms import ArmEndpointRow

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "arms-snapshot.json"
SNAPSHOT_SHA = ROOT / "data" / "arms-snapshot.sha256"
SEARCH_MAX_WEEK = 24
INSTRUMENTS = ("F-VASI", "T-VASI")
REGION = {"F-VASI": 0, "T-VASI": 1}  # face, body
LOADING_WEEKS = 4.0  # registry: induction dose for 4 weeks, then maintenance


@dataclass(frozen=True)
class ArmWeek:
    """One arm of one trial at one week: cumulative responders at nested thresholds."""

    instrument: str
    trial: str
    label: str
    active: bool
    agent: str | None
    daily_dose: float | None
    dose_unit: str | None
    loading_dose: float | None
    phototherapy: bool
    week: int
    n: int
    thresholds: tuple[int, ...]
    responders: tuple[int, ...]

    @property
    def arm_key(self) -> tuple[object, ...]:
        """Identity of the regimen (the benchmark's arm key, without the label)."""
        return (
            self.trial,
            self.active,
            self.agent,
            self.daily_dose,
            self.dose_unit,
            self.loading_dose,
            self.phototherapy,
        )


def load_rows() -> tuple[list[ArmEndpointRow], dict[str, str]]:
    """Arm table rows and agent routes from the hash-checked snapshot."""
    body = SNAPSHOT.read_text()
    expected = SNAPSHOT_SHA.read_text().split()[0]
    if hashlib.sha256(body.encode()).hexdigest() != expected:
        raise RuntimeError("arms snapshot does not match its recorded SHA-256")
    payload = json.loads(body)
    return [ArmEndpointRow(**r) for r in payload["rows"]], dict(payload["agent_routes"])


def _arm_weeks(
    rows: list[ArmEndpointRow],
    routes: dict[str, str],
    *,
    max_week: int | None,
    drop_active_of: str | None = None,
) -> list[ArmWeek]:
    out: list[ArmWeek] = []
    for instrument in INSTRUMENTS:
        drop = [(drop_active_of, True)] if drop_active_of else []
        data = build_dataset(rows, instrument, max_week=max_week, drop=drop, agent_routes=routes)
        for obs in data.observations:
            arm = data.arms[obs.arm]
            out.append(
                ArmWeek(
                    instrument=instrument,
                    trial=arm.source_id,
                    label=arm.label,
                    active=arm.active,
                    agent=arm.agent,
                    daily_dose=arm.daily_dose,
                    dose_unit=arm.dose_unit,
                    loading_dose=arm.loading_dose,
                    phototherapy=arm.phototherapy,
                    week=obs.week,
                    n=obs.n,
                    thresholds=obs.thresholds,
                    responders=obs.responders,
                )
            )
    return out


def search_set(
    rows: list[ArmEndpointRow], routes: dict[str, str], *, drop_active_of: str | None = None
) -> list[ArmWeek]:
    """S: every usable observation up to week 24 (optionally without one trial's active arms)."""
    out = _arm_weeks(rows, routes, max_week=SEARCH_MAX_WEEK, drop_active_of=drop_active_of)
    assert all(a.week <= SEARCH_MAX_WEEK for a in out)
    return out


def controlled_trials(arm_weeks: list[ArmWeek]) -> list[str]:
    """Trials with both a control and an active arm in the same instrument."""
    found: set[str] = set()
    for instrument in INSTRUMENTS:
        sub = [a for a in arm_weeks if a.instrument == instrument]
        for trial in {a.trial for a in sub}:
            roles = {a.active for a in sub if a.trial == trial}
            if roles == {True, False}:
                found.add(trial)
    return sorted(found)


def exam_targets_unlocked(rows: list[ArmEndpointRow], routes: dict[str, str]) -> list[ArmWeek]:
    """E: active-arm observations after week 24. Only ``exam.py`` may call this."""
    return [
        a for a in _arm_weeks(rows, routes, max_week=None) if a.active and a.week > SEARCH_MAX_WEEK
    ]


def reference_doses(rows: list[ArmEndpointRow], routes: dict[str, str]) -> dict[str, float]:
    """Highest daily dose per agent in the trial *designs* (no outcomes involved)."""
    ref: dict[str, float] = {}
    for a in _arm_weeks(rows, routes, max_week=None):
        if a.active and a.agent and a.daily_dose:
            ref[a.agent] = max(ref.get(a.agent, 0.0), a.daily_dose)
    return ref
