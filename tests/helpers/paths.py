"""Stable paths for tests regardless of subdirectory layout."""

from __future__ import annotations

from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = TESTS_DIR / "fixtures"
PROJECT_ROOT = TESTS_DIR.parent
