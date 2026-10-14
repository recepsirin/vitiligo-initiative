"""SQLite ledger of the discovery loop: every hypothesis, test and decision.

Kept in its own file (never the corpus DB), so it survives corpus rebuilds and
its writes never invalidate search caches. The ledger is also what makes the
statistics valid across runs: the global test index ``t``, the discovery count
used by e-LOND and the set of consumed evidence units all live here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY,
    hash TEXT NOT NULL UNIQUE,
    family TEXT NOT NULL,
    statement TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    tier INTEGER NOT NULL,
    status TEXT NOT NULL,          -- abstained | proposed | discovery | evidence | inconclusive
    belief REAL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tests (
    id INTEGER PRIMARY KEY,
    t INTEGER NOT NULL UNIQUE,     -- global e-LOND test index
    hypothesis_id INTEGER NOT NULL REFERENCES hypotheses(id),
    unit_key TEXT NOT NULL UNIQUE, -- each evidence unit is spent once, ever
    round_id TEXT NOT NULL,
    trial TEXT,                    -- held-out trial the evidence came from
    arm TEXT NOT NULL,
    log_e REAL NOT NULL,
    alpha_t REAL NOT NULL,
    discovery INTEGER NOT NULL,
    observed_json TEXT NOT NULL,
    predicted_json TEXT NOT NULL,
    tested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policy_events (
    id INTEGER PRIMARY KEY,
    round_id TEXT NOT NULL,
    trial TEXT,
    arm TEXT NOT NULL,
    reward REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    frozen_at TEXT NOT NULL,
    file TEXT NOT NULL,
    status TEXT NOT NULL,          -- pending | resolved
    record_json TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    resolution_json TEXT,
    resolved_at TEXT
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def spec_hash(spec: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()


def verify_seal(record: dict[str, Any]) -> bool:
    """True if a frozen forecast's SHA-256 matches its content."""
    body = {k: v for k, v in record.items() if k != "sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest() == record.get("sha256")


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            # Ledgers created before these columns existed.
            for table, column in (
                ("forecasts", "resolution_json"),
                ("forecasts", "resolved_at"),
                ("tests", "trial"),
                ("policy_events", "trial"),
            ):
                columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
            for table in ("tests", "policy_events"):
                # Round ids are '<UTC timestamp without dashes>-<trial>'.
                conn.execute(
                    f"UPDATE {table} SET trial = substr(round_id, instr(round_id, '-') + 1)"
                    " WHERE trial IS NULL"
                )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------ state reads

    def next_test_index(self) -> int:
        with closing(self._connect()) as conn:
            return int(conn.execute("SELECT COALESCE(MAX(t), 0) + 1 FROM tests").fetchone()[0])

    def discoveries(self, *, exclude_trial: str | None = None) -> int:
        """Discoveries so far; ``exclude_trial`` leaves out those made on that trial's data."""
        with closing(self._connect()) as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM tests WHERE discovery = 1"
                    " AND (?1 IS NULL OR trial IS NOT ?1)",
                    (exclude_trial,),
                ).fetchone()[0]
            )

    def consumed_units(self) -> set[str]:
        with closing(self._connect()) as conn:
            return {r[0] for r in conn.execute("SELECT unit_key FROM tests")}

    def arm_stats(self, *, exclude_trial: str | None = None) -> dict[str, tuple[float, float]]:
        """(total reward, number of pulls) per policy arm, optionally without one trial's."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT arm, SUM(reward), COUNT(*) FROM policy_events"
                " WHERE (?1 IS NULL OR trial IS NOT ?1) GROUP BY arm",
                (exclude_trial,),
            ).fetchall()
        return {r[0]: (float(r[1]), float(r[2])) for r in rows}

    # ----------------------------------------------------------------- writes

    def record_hypothesis(
        self,
        *,
        family: str,
        statement: str,
        spec: dict[str, Any],
        tier: int,
        status: str,
        belief: float | None,
    ) -> int:
        """Insert (or return the existing id of) a hypothesis keyed by its spec hash."""
        digest = spec_hash(spec)
        with closing(self._connect()) as conn, conn:
            existing = conn.execute(
                "SELECT id FROM hypotheses WHERE hash = ?", (digest,)
            ).fetchone()
            if existing:
                return int(existing[0])
            cursor = conn.execute(
                "INSERT INTO hypotheses (hash, family, statement, spec_json, tier, status, belief,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    digest,
                    family,
                    statement,
                    json.dumps(spec, sort_keys=True),
                    tier,
                    status,
                    belief,
                    _now(),
                ),
            )
            assert cursor.lastrowid is not None
            return int(cursor.lastrowid)

    def record_test(
        self,
        *,
        hypothesis_id: int,
        t: int,
        unit_key: str,
        round_id: str,
        trial: str,
        arm: str,
        log_e: float,
        alpha_t: float,
        discovery: bool,
        status: str,
        observed: dict[str, Any],
        predicted: dict[str, Any],
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO tests (t, hypothesis_id, unit_key, round_id, trial, arm, log_e,"
                " alpha_t, discovery, observed_json, predicted_json, tested_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    t,
                    hypothesis_id,
                    unit_key,
                    round_id,
                    trial,
                    arm,
                    log_e,
                    alpha_t,
                    int(discovery),
                    json.dumps(observed, sort_keys=True),
                    json.dumps(predicted, sort_keys=True),
                    _now(),
                ),
            )
            conn.execute("UPDATE hypotheses SET status = ? WHERE id = ?", (status, hypothesis_id))

    def record_policy_events(
        self, round_id: str, trial: str, events: list[tuple[str, float]]
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executemany(
                "INSERT INTO policy_events (round_id, trial, arm, reward, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                [(round_id, trial, arm, reward, _now()) for arm, reward in events],
            )

    def import_forecast(self, record: dict[str, Any], file: str) -> bool:
        """Store a sealed tier-2 forecast as pending; returns False if already present."""
        if not verify_seal(record):
            raise ValueError(f"seal does not match content: {file}")
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO forecasts (sha256, label, frozen_at, file, status,"
                " record_json, imported_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (
                    record["sha256"],
                    str(record.get("label", "")),
                    str(record.get("frozen_at", "")),
                    file,
                    json.dumps(record, sort_keys=True),
                    _now(),
                ),
            )
            return cursor.rowcount == 1

    def set_meta(self, key: str, value: str) -> None:
        """Record a methodology note or disclosure (shown in every summary)."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO meta (key, value, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                " updated_at = excluded.updated_at",
                (key, value, _now()),
            )

    def meta(self) -> dict[str, str]:
        with closing(self._connect()) as conn:
            return {r[0]: r[1] for r in conn.execute("SELECT key, value FROM meta ORDER BY key")}

    def pending_forecasts(self) -> list[tuple[str, str, str, dict[str, Any]]]:
        """(sha256, label, file, record) of forecasts not yet resolved."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT sha256, label, file, record_json FROM forecasts WHERE status = 'pending'"
                " ORDER BY id"
            ).fetchall()
        return [(r[0], r[1], r[2], json.loads(r[3])) for r in rows]

    def forecast_labels(self) -> list[str]:
        with closing(self._connect()) as conn:
            return [r[0] for r in conn.execute("SELECT label FROM forecasts")]

    def resolve_forecast(self, sha256: str, detail: dict[str, Any]) -> None:
        """Mark a forecast resolved and store its score (the sealed record is unchanged)."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE forecasts SET status = 'resolved', resolution_json = ?, resolved_at = ?"
                " WHERE sha256 = ?",
                (json.dumps(detail, sort_keys=True, default=str), _now(), sha256),
            )

    # ---------------------------------------------------------------- reports

    def summary(self) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            status = dict(
                conn.execute("SELECT status, COUNT(*) FROM hypotheses GROUP BY status").fetchall()
            )
            tests = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(discovery), 0) FROM tests"
            ).fetchone()
            forecasts = dict(
                conn.execute("SELECT status, COUNT(*) FROM forecasts GROUP BY status").fetchall()
            )
        return {
            "meta": self.meta(),
            "hypotheses_by_status": status,
            "tests": int(tests[0]),
            "discoveries": int(tests[1]),
            "forecasts_by_status": forecasts,
            "policy_arms": {
                arm: {"reward": r, "pulls": n} for arm, (r, n) in sorted(self.arm_stats().items())
            },
        }

    def tested(self) -> list[dict[str, Any]]:
        """All tests in order, joined with their hypothesis statements."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT t.t, h.statement, h.belief, h.status, t.arm, t.log_e, t.alpha_t,"
                " t.discovery, t.round_id FROM tests t JOIN hypotheses h"
                " ON h.id = t.hypothesis_id ORDER BY t.t"
            ).fetchall()
        return [dict(r) for r in rows]
