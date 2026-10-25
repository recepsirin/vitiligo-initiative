"""Export the discovery ledger to JSON, so the one thing nothing can rebuild is in git.

`data/discovery-ledger.db` is gitignored, lives on one disk, and holds the
record of what the discovery loop has tested. The `tests` table carries
`alpha_t`, the error budget spent on each test. Controlling the false discovery
rate across an open-ended stream requires knowing how much has already been
spent, so losing that file does not cost work that can be redone — it ends the
guarantee, because there is no way to recover what was spent.

The sealed forecasts are already in `forecasts/` as their own files, so this
exports their identity and resolution rather than the record again; everything
else is exported whole. JSON columns are parsed rather than escaped, so a diff
shows what changed instead of one long line.

    python scripts/discovery/export_ledger.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from vitiligo.config import get_settings

# Exported whole: nothing else holds them.
WHOLE = ("meta", "hypotheses", "policy_events", "tests")
# The record itself lives in forecasts/<file>; keep what identifies and resolves it.
FORECAST_FIELDS = ("sha256", "label", "frozen_at", "file", "status", "resolved_at")
JSON_COLUMNS = ("spec_json", "observed_json", "predicted_json", "resolution_json")


def _value(column: str, value: Any) -> Any:
    if column in JSON_COLUMNS and isinstance(value, str) and value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _rows(
    conn: sqlite3.Connection, table: str, fields: tuple[str, ...] | None = None
) -> list[dict]:
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    keep = [c for c in columns if fields is None or c in fields]
    out = []
    for row in conn.execute(f"SELECT {', '.join(keep)} FROM {table} ORDER BY 1"):
        out.append({c: _value(c, v) for c, v in zip(keep, row, strict=True)})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("forecasts/ledger-export.json"))
    args = parser.parse_args()

    path = get_settings().resolved_ledger_path
    if not path.is_file():
        print(f"No ledger at {path}")
        return 1

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    export: dict[str, Any] = {
        "note": (
            "Exported from data/discovery-ledger.db, which is gitignored. Forecast "
            "records themselves live in forecasts/<file>; this keeps their identity "
            "and resolution. Regenerate with scripts/discovery/export_ledger.py."
        ),
        "source": path.name,
    }
    for table in WHOLE:
        export[table] = _rows(conn, table)
    export["forecasts"] = _rows(conn, "forecasts", FORECAST_FIELDS)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(export, indent=2, sort_keys=True, default=str) + "\n")

    counts = ", ".join(f"{len(export[t])} {t}" for t in (*WHOLE, "forecasts"))
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB): {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
