"""Every package must import on its own, whatever is imported first.

`vitiligo.reports` imports `vitiligo.graph`, so anything under graph that
imports reports at module level closes a cycle. The cycle is invisible to the
CLI and the test suite, which happen to import graph first; it breaks only for
code whose first import is `vitiligo.reports`.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

PACKAGES = [
    "vitiligo.reports",
    "vitiligo.reports.candidates",
    "vitiligo.reports.jak",
    "vitiligo.reports.jak_arms",
    "vitiligo.graph",
    "vitiligo.graph.evidence_seed",
    "vitiligo.mechanisms",
    "vitiligo.cli",
    "vitiligo.web.app",
]


@pytest.mark.parametrize("module", PACKAGES)
def test_module_imports_as_the_first_import(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"importing {module} first fails:\n{result.stderr[-900:]}"
