"""Durability forecast scoring: closed forms against simulation, and benchmarks."""

from __future__ import annotations

import math

import numpy as np
import pytest

from vitiligo.discovery import durability as dur


def test_hr_log_score_widens_the_forecast_by_the_posted_error() -> None:
    # Posted HR 0.4 with CI 0.2-0.8: SE of log HR = ln(4) / (2 * 1.96).
    se = math.log(4) / (2 * 1.959964)
    rng = np.random.default_rng(0)
    truth = rng.normal(math.log(0.35), 0.5, 400_000)
    density = np.mean(np.exp(-0.5 * ((math.log(0.4) - truth) / se) ** 2)) / (
        se * math.sqrt(2 * math.pi)
    )
    assert dur.hr_log_score(0.4, 0.2, 0.8, math.log(0.35), 0.5) == pytest.approx(
        math.log(density), abs=0.01
    )
    # A forecast centred on the result beats the uninformed benchmark;
    # one confidently wrong does not.
    assert dur.hr_log_score(0.4, 0.2, 0.8, math.log(0.4), 0.3) > dur.hr_benchmark_log_score(
        0.4, 0.2, 0.8
    )
    assert dur.hr_log_score(0.4, 0.2, 0.8, math.log(3.0), 0.1) < dur.hr_benchmark_log_score(
        0.4, 0.2, 0.8
    )


def test_retention_scores_and_uniform_benchmark() -> None:
    draws = np.full(1000, 0.4)
    se = 0.2 / (2 * 1.959964)
    expected = -0.5 * math.log(2 * math.pi * se**2)  # density at its own centre
    assert dur.retention_log_score(0.4, 0.3, 0.5, draws) == pytest.approx(expected)
    # Uniform benchmark: the estimate well inside [0, 1] has density about 1.
    assert dur.retention_log_score(0.4, 0.3, 0.5, draws) > dur.retention_benchmark_log_score(
        0.4, 0.3, 0.5
    )
    assert dur.retention_benchmark_log_score(0.5, 0.45, 0.55) == pytest.approx(0.0, abs=1e-6)
    # Near the edge, part of the error spills outside [0, 1].
    assert dur.retention_benchmark_log_score(0.0, -0.1, 0.1) == pytest.approx(
        math.log(0.5), abs=1e-6
    )


def test_sealed_durability_forecasts_verify() -> None:
    import hashlib
    import json
    from pathlib import Path

    from vitiligo.discovery.ledger import verify_seal

    folder = Path(__file__).resolve().parents[2] / "forecasts" / "durability"
    for path in sorted(folder.glob("*.json")):
        record = json.loads(path.read_text())
        assert verify_seal(record), path
        draws = (path.parent / record["draws_file"]).read_bytes()
        assert hashlib.sha256(draws).hexdigest() == record["draws_sha256"], path
        # Kept out of the weekly binomial scoring, which reads "prediction".
        assert "prediction" not in record and "target" not in record
