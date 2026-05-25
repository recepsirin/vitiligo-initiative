#!/usr/bin/env bash
# Ingest helpers — re-use deploy/common.sh (includes vitiligo_run).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/../deploy/common.sh"
