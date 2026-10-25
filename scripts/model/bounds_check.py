"""Score the scenario model on rates it refuses to fit, using what bounds them.

Excluding TRuE-V's week-52 rows for mixing analysis populations removed the
only F-VASI evidence the week-24-to-later back-test had. Those rows still say
something: 48.0% of the 177 assessed, out of 222 at week 24, puts the rate over
that group between 38.3% and 58.6% whatever the 45 uncounted patients did. A
prediction outside that range is wrong at either end, so the rows can be scored
where they cannot be fitted.

    python scripts/model/bounds_check.py --instrument F-VASI \
        --out exports/model/bounds-check-F-VASI.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from vitiligo.models.jak_mbma import FitSettings, build_dataset, check_against_bounds, fit
from vitiligo.reports import build_jak_atlas
from vitiligo.reports.jak_arms import harmonize_arms
from vitiligo.storage import init_db


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument", default="F-VASI", choices=["F-VASI", "T-VASI"])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    init_db()
    rows = harmonize_arms(build_jak_atlas())
    data = build_dataset(rows, args.instrument)
    posterior = fit(data, FitSettings())
    checks = check_against_bounds(posterior, rows, args.instrument)

    print(
        f"\n{args.instrument}: {len(data.observations)} observations fitted, "
        f"{len(checks)} bounded rates to check\n"
    )
    if not checks:
        print("  nothing is bounded: every row is either fitted or lacks a reference group.")
        return 0

    header = (
        f"{'trial':14} {'wk':>3} {'thr':>4} {'reported':>16} "
        f"{'bracket over group':>22} {'predicted (95%)':>24} {'':>8}"
    )
    print(header)
    print("-" * len(header))
    for c in checks:
        verdict = "inside" if c.inside else ("overlaps" if c.overlaps else "OUTSIDE")
        print(
            f"{c.source_id:14} {c.week:>3} {c.threshold:>4} "
            f"{c.reported:>7.1f}% of {c.reported_n:<5} "
            f"{c.floor:>8.1f}-{c.ceiling:<5.1f} of {c.group:<4} "
            f"{c.predicted.mean:>7.1f}% [{c.predicted.lo95:4.1f},{c.predicted.hi95:5.1f}] "
            f"{verdict:>8}"
        )
    inside = sum(c.inside for c in checks)
    overlaps = sum(c.overlaps for c in checks)
    print(
        f"\n  posterior mean inside the bracket: {inside} of {len(checks)}"
        f"\n  95% interval reaching the bracket: {overlaps} of {len(checks)}"
    )
    print(
        "\n  A bracket is what the trial can establish, not an estimate. Landing outside one\n"
        "  is a failure; landing inside a 20-point bracket is a weak pass."
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "instrument": args.instrument,
                    "observations_fitted": len(data.observations),
                    "inside": inside,
                    "overlaps": overlaps,
                    "checks": [asdict(c) for c in checks],
                },
                indent=2,
                default=str,
            )
        )
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
