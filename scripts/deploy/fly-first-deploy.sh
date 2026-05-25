#!/usr/bin/env bash
# First-time Fly.io setup for the Evidence Engine (Amsterdam region).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/common.sh"

vitiligo_cd_root

APP="$(vitiligo_fly_app)"
REGION="${FLY_REGION:-ams}"
VOLUME="${FLY_VOLUME:-vitiligo_data}"

vitiligo_require_cmd fly "Install: https://fly.io/docs/hands-on/install-flyctl/"

vitiligo_info "Fly app: $APP (region: $REGION)"

if ! fly status -a "$APP" >/dev/null 2>&1; then
  vitiligo_info "Creating app from fly.toml (no deploy yet)"
  fly launch --no-deploy --copy-config -a "$APP" || fly launch --no-deploy --copy-config
else
  vitiligo_info "App $APP already exists"
fi

if ! fly volumes list -a "$APP" 2>/dev/null | grep -q "$VOLUME"; then
  vitiligo_info "Creating volume $VOLUME in $REGION"
  fly volumes create "$VOLUME" --region "$REGION" --size 1 -a "$APP"
else
  vitiligo_info "Volume $VOLUME already present"
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  vitiligo_warn "ANTHROPIC_API_KEY is not set in the environment."
  vitiligo_warn "Set it before deploy: fly secrets set ANTHROPIC_API_KEY=... -a $APP"
else
  vitiligo_info "Setting ANTHROPIC_API_KEY secret"
  fly secrets set "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" -a "$APP"
fi

vitiligo_info "Deploying container"
fly deploy -a "$APP"

cat <<EOF

Next steps:
  1. Upload corpus:  ./scripts/deploy/fly-upload-db.sh
  2. Seed graph:     ./scripts/deploy/fly-seed-graph.sh
  3. Verify:         fly open /api/health -a $APP

EOF
