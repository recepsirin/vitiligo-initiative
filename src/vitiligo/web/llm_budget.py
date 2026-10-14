"""Global spend guard for the paid LLM endpoints (Ask, Hypothesize).

Per-IP rate limits cannot stop many real clients (or one client with many
IPs) from running up the Anthropic bill. This guard applies limits across
*all* clients:

- ``requests_per_minute``: LLM calls started in the last 60 s, in-flight
  calls included;
- ``daily_token_budget``: input + output tokens recorded in the last 24 h.

State lives in a small SQLite file next to the corpus — not in the corpus DB,
whose mtime drives the search caches — so it survives restarts and is shared
by every worker on the same host. The token budget is a soft cap: calls that
are already running when it is reached still complete.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_MINUTE = 60.0
_DAY = 86_400.0
_RETENTION = 2 * _DAY

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY,
    started_at REAL NOT NULL,
    endpoint TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_llm_calls_started_at ON llm_calls (started_at);
"""


class LLMBudgetExceeded(RuntimeError):  # noqa: N818 — matches LLMUnavailable naming
    """Raised when a global LLM limit is reached; carries a retry hint."""

    def __init__(self, message: str, retry_after_s: int) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


@dataclass(frozen=True)
class LLMBudgetStatus:
    calls_last_minute: int
    tokens_last_24h: int


class LLMBudget:
    """Reserve-then-record guard; a no-op when both limits are 0."""

    def __init__(
        self,
        state_path: Path,
        *,
        requests_per_minute: int = 0,
        daily_token_budget: int = 0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._path = state_path
        self._per_minute = max(0, requests_per_minute)
        self._daily_tokens = max(0, daily_token_budget)
        self._clock = clock
        self._initialized = False

    @property
    def enabled(self) -> bool:
        return bool(self._per_minute or self._daily_tokens)

    def _connect(self) -> sqlite3.Connection:
        if not self._initialized:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, timeout=10, isolation_level=None)
        if not self._initialized:
            conn.executescript(_SCHEMA)
            self._initialized = True
        return conn

    def reserve(self, endpoint: str) -> int | None:
        """Check the limits and register a starting call; return its id.

        Raises ``LLMBudgetExceeded`` when a limit is reached. Returns None when
        the guard is disabled.
        """
        if not self.enabled:
            return None
        now = self._clock()
        conn = self._connect()
        try:
            # IMMEDIATE takes the write lock up front, so check + insert is
            # atomic across workers sharing the state file.
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("DELETE FROM llm_calls WHERE started_at < ?", (now - _RETENTION,))
                if self._per_minute:
                    row = conn.execute(
                        "SELECT COUNT(*), MIN(started_at) FROM llm_calls WHERE started_at >= ?",
                        (now - _MINUTE,),
                    ).fetchone()
                    if row[0] >= self._per_minute:
                        retry = max(1, int(row[1] + _MINUTE - now) + 1)
                        raise LLMBudgetExceeded(
                            "The AI features are busy right now (global limit of "
                            f"{self._per_minute} requests per minute). Please retry shortly.",
                            retry,
                        )
                if self._daily_tokens:
                    used = conn.execute(
                        "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) "
                        "FROM llm_calls WHERE started_at >= ?",
                        (now - _DAY,),
                    ).fetchone()[0]
                    if used >= self._daily_tokens:
                        oldest = conn.execute(
                            "SELECT MIN(started_at) FROM llm_calls "
                            "WHERE started_at >= ? AND input_tokens + output_tokens > 0",
                            (now - _DAY,),
                        ).fetchone()[0]
                        retry = max(60, int((oldest or now) + _DAY - now))
                        raise LLMBudgetExceeded(
                            "The daily budget for AI features has been reached. "
                            "Search and Trials still work; please retry later.",
                            retry,
                        )
                cursor = conn.execute(
                    "INSERT INTO llm_calls (started_at, endpoint) VALUES (?, ?)", (now, endpoint)
                )
                conn.execute("COMMIT")
                return cursor.lastrowid
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    def record(
        self, call_id: int | None, input_tokens: int | None, output_tokens: int | None
    ) -> None:
        """Store the token usage of a finished call (no-op when disabled)."""
        if call_id is None:
            return
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE llm_calls SET input_tokens = ?, output_tokens = ? WHERE id = ?",
                (input_tokens or 0, output_tokens or 0, call_id),
            )
        finally:
            conn.close()

    def status(self) -> LLMBudgetStatus:
        """Current usage across all clients (zeros when disabled)."""
        if not self.enabled:
            return LLMBudgetStatus(calls_last_minute=0, tokens_last_24h=0)
        now = self._clock()
        conn = self._connect()
        try:
            calls = conn.execute(
                "SELECT COUNT(*) FROM llm_calls WHERE started_at >= ?", (now - _MINUTE,)
            ).fetchone()[0]
            tokens = conn.execute(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) "
                "FROM llm_calls WHERE started_at >= ?",
                (now - _DAY,),
            ).fetchone()[0]
        finally:
            conn.close()
        return LLMBudgetStatus(calls_last_minute=int(calls), tokens_last_24h=int(tokens))
