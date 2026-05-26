#!/usr/bin/env bash
# Check Fly.io authentication and print next deploy commands.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/common.sh"

APP="$(vitiligo_fly_app)"

vitiligo_require_cmd fly "Install: https://fly.io/docs/hands-on/install-flyctl/"

if fly auth whoami 2>/dev/null; then
  vitiligo_info "Fly authentication OK"
else
  echo "Not authenticated." >&2
  echo "" >&2
  echo "Run one of:" >&2
  echo "  fly auth login                    # browser login" >&2
  echo "  export FLY_ACCESS_TOKEN=...       # CI / automation" >&2
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  vitiligo_warn "ANTHROPIC_API_KEY not set in this shell (Ask/Hypothesize need it on Fly)"
else
  vitiligo_info "ANTHROPIC_API_KEY present in shell"
fi

if [[ ! -f "$(vitiligo_default_db_path)" ]]; then
  vitiligo_warn "Local DB missing at $(vitiligo_default_db_path)"
else
  vitiligo_info "Local DB: $(vitiligo_default_db_path) ($(du -h "$(vitiligo_default_db_path)" | awk '{print $1}'))"
fi

cat <<EOF

Ready to deploy app: $APP

  ./scripts/deploy/fly-deploy-all.sh
  ./scripts/deploy/verify-public.sh

See docs/release-checklist-v1.0.0.md for full checklist.
EOF
