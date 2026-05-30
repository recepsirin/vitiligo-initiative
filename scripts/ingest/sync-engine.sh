#!/usr/bin/env bash
# Refresh derived engine artifacts after document/trial/prior ingestion.
#
# Safe to re-run: idempotent upserts, graph merge, embed only missing vectors.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ingest/common.sh
source "$SCRIPT_DIR/common.sh"

WITH_GEO="${WITH_GEO:-1}"

vitiligo_cd_root
vitiligo_info "Sync engine — $(vitiligo_bin)"

if [[ "$WITH_GEO" == "1" ]]; then
  vitiligo_info "Step 1/4: GEO metadata"
  vitiligo_run ingest geo
else
  vitiligo_info "Step 1/4: GEO skipped (WITH_GEO=0)"
fi

vitiligo_info "Step 2/4: Knowledge graph seed"
vitiligo_run graph seed

vitiligo_info "Step 3/4: Embed documents missing vectors"
vitiligo_run embed run

vitiligo_info "Step 4/4: Stats"
vitiligo_run db stats
vitiligo_run graph stats
vitiligo_run embed stats

vitiligo_info "Sync complete"
