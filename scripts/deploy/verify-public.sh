#!/usr/bin/env bash
# Verify a deployed Evidence Engine (health, legal pages, core API smoke).
#
# Usage:
#   ./scripts/deploy/verify-public.sh
#   BASE_URL=https://vitiligo-evidence-engine.fly.dev ./scripts/deploy/verify-public.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/common.sh"

APP="$(vitiligo_fly_app)"
BASE_URL="${BASE_URL:-https://${APP}.fly.dev}"
FAIL=0

vitiligo_require_cmd curl "Install curl"

check() {
  local name="$1"
  local url="$2"
  local expect="${3:-}"
  vitiligo_info "GET $url"
  if ! body="$(curl -fsS "$url")"; then
    echo "  FAIL: request failed" >&2
    FAIL=1
    return
  fi
  if [[ -n "$expect" ]] && ! grep -q "$expect" <<<"$body"; then
    echo "  FAIL: expected pattern not found: $expect" >&2
    FAIL=1
    return
  fi
  echo "  OK"
}

vitiligo_info "Verifying public deploy at $BASE_URL"

check "health" "$BASE_URL/api/health" '"ready"'
check "index" "$BASE_URL/" "Vitiligo Initiative"
check "privacy" "$BASE_URL/privacy" "Privacy Policy"
check "terms" "$BASE_URL/terms" "Not medical advice"
check "graph stats" "$BASE_URL/api/graph/stats" "entities"

vitiligo_info "POST /api/search smoke"
search_resp="$(curl -fsS -X POST "$BASE_URL/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"vitiligo JAK inhibitor","top_k":3}')" || {
  echo "  FAIL: search request failed" >&2
  FAIL=1
}

if [[ -n "${search_resp:-}" ]] && grep -q '"results"' <<<"$search_resp"; then
  echo "  OK"
else
  echo "  FAIL: unexpected search response" >&2
  FAIL=1
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "verify-public: one or more checks failed" >&2
  exit 1
fi

vitiligo_info "All checks passed"
echo "  UI: $BASE_URL"
echo "  Health: $BASE_URL/api/health"
