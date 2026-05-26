#!/usr/bin/env bash
# Verify a locally running Evidence Engine (vitiligo serve).
#
# Usage:
#   vitiligo serve &   # in another terminal
#   ./scripts/deploy/verify-local.sh
#
#   BASE_URL=http://127.0.0.1:8765 ./scripts/deploy/verify-local.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"
export BASE_URL
exec "$SCRIPT_DIR/verify-public.sh"
