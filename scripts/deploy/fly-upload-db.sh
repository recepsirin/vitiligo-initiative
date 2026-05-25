#!/usr/bin/env bash
# Upload local vitiligo.db to the Fly.io volume via SFTP.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

vitiligo_cd_root

APP="$(vitiligo_fly_app)"
LOCAL_DB="${1:-$(vitiligo_default_db_path)}"
REMOTE_DB="${FLY_REMOTE_DB_PATH:-/data/vitiligo.db}"

vitiligo_require_cmd fly "Install: https://fly.io/docs/hands-on/install-flyctl/"

if [[ ! -f "$LOCAL_DB" ]]; then
  echo "error: local database not found: $LOCAL_DB" >&2
  exit 1
fi

SIZE_MB="$(du -m "$LOCAL_DB" | awk '{print $1}')"
vitiligo_info "Uploading $LOCAL_DB (${SIZE_MB} MB) -> $APP:$REMOTE_DB"

fly ssh sftp shell -a "$APP" <<EOF
put ${LOCAL_DB} ${REMOTE_DB}
ls -lh ${REMOTE_DB}
bye
EOF

vitiligo_info "Upload complete. Check health: fly open /api/health -a $APP"
