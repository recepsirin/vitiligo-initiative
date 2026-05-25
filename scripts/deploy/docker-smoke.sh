#!/usr/bin/env bash
# Build the Evidence Engine image and run a local smoke test.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

vitiligo_cd_root

IMAGE="${IMAGE:-vitiligo-engine:local}"
PORT="${PORT:-8765}"
DB_PATH="$(vitiligo_default_db_path)"

vitiligo_require_cmd docker "Install Docker Desktop: https://docs.docker.com/get-docker/"

vitiligo_info "Building Docker image: $IMAGE"
docker build -t "$IMAGE" .

if [[ ! -f "$DB_PATH" ]]; then
  vitiligo_warn "Database not found at $DB_PATH — UI will start in degraded mode."
  vitiligo_warn "Run ingestion locally first or mount an existing vitiligo.db."
fi

vitiligo_info "Starting container on http://127.0.0.1:$PORT"
exec docker run --rm -p "${PORT}:8765" \
  ${ANTHROPIC_API_KEY:+-e "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"} \
  -v "$(vitiligo_repo_root)/$(dirname "$DB_PATH"):/data" \
  -e "VITILIGO_DB_PATH=/data/$(basename "$DB_PATH")" \
  "$IMAGE"
