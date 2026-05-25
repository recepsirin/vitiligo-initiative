#!/usr/bin/env bash
# Redeploy the Evidence Engine container (no database upload).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/common.sh"

vitiligo_cd_root

APP="$(vitiligo_fly_app)"

vitiligo_require_cmd fly "Install: https://fly.io/docs/hands-on/install-flyctl/"

vitiligo_info "Deploying $APP"
fly deploy -a "$APP"

vitiligo_info "Health check: fly open /api/health -a $APP"
