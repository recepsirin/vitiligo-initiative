"""Tests for the global LLM spend guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from vitiligo.web.llm_budget import LLMBudget, LLMBudgetExceeded


class FakeClock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_disabled_budget_is_a_no_op_and_creates_no_file(tmp_path: Path) -> None:
    state = tmp_path / "state.db"
    budget = LLMBudget(state)
    assert budget.reserve("ask") is None
    budget.record(None, 10, 10)
    assert not state.exists()


def test_per_minute_cap_counts_in_flight_calls(tmp_path: Path) -> None:
    clock = FakeClock()
    budget = LLMBudget(tmp_path / "s.db", requests_per_minute=2, clock=clock)
    budget.reserve("ask")
    budget.reserve("hypothesize")  # still running: no tokens recorded yet
    with pytest.raises(LLMBudgetExceeded) as exc:
        budget.reserve("ask")
    assert 1 <= exc.value.retry_after_s <= 61
    clock.now += 61
    assert budget.reserve("ask") is not None


def test_daily_token_budget_is_rolling(tmp_path: Path) -> None:
    clock = FakeClock()
    budget = LLMBudget(tmp_path / "s.db", daily_token_budget=1_000, clock=clock)
    call = budget.reserve("hypothesize")
    budget.record(call, 700, 300)
    clock.now += 3_600
    with pytest.raises(LLMBudgetExceeded) as exc:
        budget.reserve("ask")
    # Frees up when the first call leaves the 24 h window (~23 h from now).
    assert 22 * 3_600 <= exc.value.retry_after_s <= 24 * 3_600
    clock.now += 23 * 3_600 + 1
    assert budget.reserve("ask") is not None


def test_state_is_shared_between_instances(tmp_path: Path) -> None:
    """Two workers (or a restart) see the same usage."""
    clock = FakeClock()
    worker_a = LLMBudget(tmp_path / "s.db", daily_token_budget=100, clock=clock)
    worker_b = LLMBudget(tmp_path / "s.db", daily_token_budget=100, clock=clock)
    worker_a.record(worker_a.reserve("ask"), 60, 40)
    with pytest.raises(LLMBudgetExceeded):
        worker_b.reserve("ask")
    assert worker_b.status().tokens_last_24h == 100
