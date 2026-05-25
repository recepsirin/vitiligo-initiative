#!/usr/bin/env bash
# Seed the knowledge graph on a deployed Fly.io machine.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

APP="$(vitiligo_fly_app)"

vitiligo_require_cmd fly "Install: https://fly.io/docs/hands-on/install-flyctl/"

vitiligo_info "Seeding knowledge graph on $APP"
fly ssh console -a "$APP" -C "vitiligo graph seed && vitiligo graph stats"

vitiligo_info "Done. Browse graph: fly open / -a $APP (Graph tab)"
