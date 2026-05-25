#!/usr/bin/env bash
# Ingest helpers — source deploy/common.sh for repo root + logging.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/../deploy/common.sh"

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
