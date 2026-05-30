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

vitiligo_info() {
  echo "==> $*"
}

vitiligo_warn() {
  echo "warning: $*" >&2
}

vitiligo_bin() {
  local bin="${VITILIGO_BIN:-}"
  if [[ -z "$bin" ]]; then
    vitiligo_cd_root
    if [[ -x ".venv/bin/vitiligo" ]]; then
      bin=".venv/bin/vitiligo"
    elif command -v vitiligo >/dev/null 2>&1; then
      bin="vitiligo"
    else
      echo "error: vitiligo CLI not found (activate .venv or set VITILIGO_BIN)" >&2
      exit 1
    fi
  fi
  printf '%s' "$bin"
}

vitiligo_run() {
  vitiligo_cd_root
  "$(vitiligo_bin)" "$@"
}
