#!/usr/bin/env bash
# End-to-end Fly.io deploy: verify corpus, deploy app, upload DB, seed graph, check health.
#
# Prerequisites:
#   fly auth login   (or export FLY_ACCESS_TOKEN)
#   export ANTHROPIC_API_KEY=sk-ant-...
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/common.sh"

vitiligo_cd_root

APP="$(vitiligo_fly_app)"
LOCAL_DB="${1:-$(vitiligo_default_db_path)}"
SKIP_PREPARE="${SKIP_PREPARE:-0}"

vitiligo_require_cmd fly "Install: https://fly.io/docs/hands-on/install-flyctl/"
vitiligo_require_cmd curl "Install curl for health verification"

if ! fly auth whoami >/dev/null 2>&1; then
  echo "error: not logged in to Fly — run: fly auth login" >&2
  echo "       or set FLY_ACCESS_TOKEN for non-interactive deploy" >&2
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  vitiligo_warn "ANTHROPIC_API_KEY is not set — Ask/Hypothesize will fail on Fly"
  vitiligo_warn "Export it before running: export ANTHROPIC_API_KEY=sk-ant-..."
fi

if [[ ! -f "$LOCAL_DB" ]]; then
  echo "error: local database not found: $LOCAL_DB" >&2
  echo "Build the corpus locally first (see docs/engine.md)." >&2
  exit 1
fi

if [[ "$SKIP_PREPARE" != "1" ]]; then
  vitiligo_info "Verifying local corpus"
  "$SCRIPT_DIR/prepare-db.sh" "$LOCAL_DB"
fi

vitiligo_info "Deploying Fly app: $APP"
"$SCRIPT_DIR/fly-first-deploy.sh"

vitiligo_info "Uploading database"
"$SCRIPT_DIR/fly-upload-db.sh" "$LOCAL_DB"

vitiligo_info "Seeding knowledge graph on Fly"
"$SCRIPT_DIR/fly-seed-graph.sh"

HEALTH_URL="https://${APP}.fly.dev/api/health"
vitiligo_info "Waiting for health check: $HEALTH_URL"

for _ in $(seq 1 30); do
  if curl -fsS "$HEALTH_URL" >/tmp/vitiligo-health.json 2>/dev/null; then
    if grep -q '"ready"[[:space:]]*:[[:space:]]*true' /tmp/vitiligo-health.json; then
      vitiligo_info "Health check passed"
      cat /tmp/vitiligo-health.json
      echo
      vitiligo_info "Open UI: fly open / -a $APP"
      exit 0
    fi
  fi
  sleep 5
done

echo "error: health check did not reach ready=true within 150s" >&2
echo "Check logs: fly logs -a $APP" >&2
curl -fsS "$HEALTH_URL" 2>/dev/null || true
exit 1
