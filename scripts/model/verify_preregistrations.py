"""Check that each pre-registration still matches the hash sealed before its first fit.

Amendments are appended after sealing, so the check replaces the Amendments
section with the "None yet." it had when sealed and hashes the result.

    python scripts/model/verify_preregistrations.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

SEALS = {
    "lab/simulator/PREREGISTRATION.md": "lab/simulator/results/preregistration.sha256",
    "docs/model-v0.3-preregistration.md": "forecasts/v0.3-preregistration.sha256",
    "docs/model-v0.4-preregistration.md": "forecasts/v0.4-preregistration.sha256",
    "docs/model-v0.5-preregistration.md": "forecasts/v0.5-preregistration.sha256",
    "docs/voi-preregistration.md": "forecasts/voi-preregistration.sha256",
}


def main() -> int:
    failed = 0
    for doc, seal in SEALS.items():
        text = Path(doc).read_text()
        sealed_hash, *_rest = Path(seal).read_text().split()
        original = re.sub(r"## Amendments\n\n[\s\S]*\Z", "## Amendments\n\nNone yet.\n", text)
        ok = hashlib.sha256(original.encode()).hexdigest() == sealed_hash
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {doc} ({Path(seal).read_text().strip().split()[-1]})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
