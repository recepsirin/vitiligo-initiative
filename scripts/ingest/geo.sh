#!/usr/bin/env bash
# Ingest all vitiligo-linked GEO DataSets metadata (~300+ GSE series).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ingest/common.sh
source "$SCRIPT_DIR/common.sh"

LIMIT="${1:-}"

if [[ -n "$LIMIT" ]]; then
  vitiligo_info "GEO smoke ingest (limit=$LIMIT)"
  vitiligo_run ingest geo --limit "$LIMIT"
else
  vitiligo_info "GEO full ingest (all matching DataSets)"
  vitiligo_run ingest geo
fi

vitiligo_info "Embedding new GEO documents"
vitiligo_run embed run

vitiligo_info "Corpus snapshot"
vitiligo_run db stats
vitiligo_run embed stats
