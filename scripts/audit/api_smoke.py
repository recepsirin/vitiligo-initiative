#!/usr/bin/env python3
"""Backward-compatible wrapper — prefer ``pytest -m smoke``."""

from __future__ import annotations

import sys

import pytest


def main() -> int:
    return pytest.main(["-q", "-m", "smoke", "tests/smoke/test_smoke_api.py"])


if __name__ == "__main__":
    raise SystemExit(main())
