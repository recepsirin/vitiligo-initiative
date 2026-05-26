#!/usr/bin/env bash
# Full local smoke audit — requires data/vitiligo.db and optional ANTHROPIC_API_KEY.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

VITILIGO="${ROOT}/.venv/bin/vitiligo"
PY="${ROOT}/.venv/bin/python"

FAIL=0
pass() { echo "  OK  $1"; }
fail() { echo "  FAIL $1"; FAIL=1; }

echo "==> Ruff"
if "${ROOT}/.venv/bin/ruff" check src tests >/dev/null 2>&1; then pass "ruff"; else fail "ruff"; fi

echo "==> Pytest"
if "${ROOT}/.venv/bin/pytest" tests/ -q >/dev/null 2>&1; then pass "pytest"; else fail "pytest"; fi

echo "==> prepare-db"
if ./scripts/deploy/prepare-db.sh >/dev/null 2>&1; then pass "prepare-db"; else fail "prepare-db"; fi

echo "==> graph-spotcheck"
if ./scripts/review/graph-spotcheck.sh >/dev/null 2>&1; then pass "graph-spotcheck"; else fail "graph-spotcheck"; fi

echo "==> CLI smoke (read-only)"
run_cli() {
  if "$VITILIGO" "$@" >/dev/null 2>&1; then pass "vitiligo $*"; else fail "vitiligo $*"; fi
}
run_cli version
run_cli db stats
run_cli embed stats
run_cli trials stats
run_cli priors stats
run_cli graph stats
run_cli search "JAK inhibitor vitiligo" --top-k 3
run_cli trials search tacrolimus --limit 5
run_cli graph search ruxolitinib --limit 3

echo "==> Confidence regression (pytest)"
if "${ROOT}/.venv/bin/python" "${ROOT}/scripts/test/build_regression_db.py" --output /tmp/vitiligo-regression-audit.db \
  && VITILIGO_REGRESSION_DB=/tmp/vitiligo-regression-audit.db "${ROOT}/.venv/bin/pytest" tests/ -q -m confidence; then
  pass "pytest -m confidence"
else
  fail "pytest -m confidence"
fi

echo "==> Candidate confidence (full corpus)"
if "${ROOT}/.venv/bin/pytest" tests/confidence/test_confidence_corpus.py -q; then pass "test_confidence_corpus.py"; else fail "test_confidence_corpus.py"; fi

echo "==> API smoke (pytest)"
if "${ROOT}/.venv/bin/pytest" tests/ -q -m smoke; then pass "pytest -m smoke"; else fail "pytest -m smoke"; fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "audit: failures detected" >&2
  exit 1
fi
echo "audit: all smoke checks passed"
