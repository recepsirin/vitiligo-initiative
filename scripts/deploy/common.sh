#!/usr/bin/env bash
# Shared helpers for Vitiligo Initiative deploy scripts.
set -euo pipefail

vitiligo_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

vitiligo_cd_root() {
  cd "$(vitiligo_repo_root)"
}

vitiligo_require_cmd() {
  local cmd="$1"
  local hint="${2:-}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: required command not found: $cmd" >&2
    if [[ -n "$hint" ]]; then
      echo "$hint" >&2
    fi
    exit 1
  fi
}

vitiligo_default_db_path() {
  printf '%s' "${VITILIGO_DB_PATH:-data/vitiligo.db}"
}

vitiligo_fly_app() {
  printf '%s' "${FLY_APP:-vitiligo-evidence-engine}"
}

vitiligo_info() {
  echo "==> $*"
}

vitiligo_warn() {
  echo "warning: $*" >&2
}
