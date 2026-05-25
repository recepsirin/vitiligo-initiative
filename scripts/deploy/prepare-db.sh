#!/usr/bin/env bash
# Verify the local corpus DB and prepare it for Fly.io upload.
#
# Usage:
#   ./scripts/deploy/prepare-db.sh           # inspect + checklist
#   ./scripts/deploy/prepare-db.sh --gzip  # also create data/vitiligo.db.gz
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/common.sh"

GZIP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -g | --gzip) GZIP=1; shift ;;
    -h | --help)
      echo "Usage: prepare-db.sh [--gzip]"
      echo "  Verify vitiligo.db, print corpus stats, optional gzip for transfer."
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      exit 2
      ;;
  esac
done

vitiligo_cd_root

DB="$(vitiligo_default_db_path)"
if [[ ! "$DB" = /* ]]; then
  DB="$(vitiligo_repo_root)/$DB"
fi

if [[ ! -f "$DB" ]]; then
  echo "error: database not found: $DB" >&2
  echo "Run ingestion first (e.g. ./scripts/ingest/sync-engine.sh)." >&2
  exit 1
fi

SIZE_MB="$(du -m "$DB" | awk '{print $1}')"
vitiligo_info "Database: $DB (${SIZE_MB} MB)"

if command -v vitiligo >/dev/null 2>&1 || [[ -x ".venv/bin/vitiligo" ]]; then
  vitiligo_info "Corpus stats"
  vitiligo_run db stats || true
  vitiligo_run graph stats || true
  vitiligo_run embed stats || true
else
  vitiligo_warn "vitiligo CLI not available — skipping stats"
fi

if [[ "$GZIP" -eq 1 ]]; then
  vitiligo_require_cmd gzip
  GZ_PATH="${DB}.gz"
  vitiligo_info "Compressing -> $GZ_PATH"
  gzip -kf "$DB"
  GZ_MB="$(du -m "$GZ_PATH" | awk '{print $1}')"
  vitiligo_info "Compressed size: ${GZ_MB} MB (upload .gz only if you will gunzip on the server)"
fi

cat <<EOF

Ready for deploy:
  1. ./scripts/deploy/fly-first-deploy.sh     (once)
  2. ./scripts/deploy/fly-upload-db.sh        (uploads $DB)
  3. ./scripts/deploy/fly-seed-graph.sh
  4. fly open /api/health -a $(vitiligo_fly_app)

Expert graph review (local):
  vitiligo graph export -o exports/graph-$(date +%Y%m%d).json

EOF
