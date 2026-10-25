#!/usr/bin/env bash
# Generate evidence-first candidate report (JSON + Markdown).
#
# Usage:
#   ./scripts/review/generate-candidate-report.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/../deploy/common.sh"

JSON_OUT="${JSON_OUT:-exports/candidate-report.json}"
MD_OUT="${MD_OUT:-docs/candidate-report-v1.md}"

vitiligo_cd_root

vitiligo_info "Ensuring embeddings are current"
vitiligo_run embed run

vitiligo_info "Graph spot-check"
"$SCRIPT_DIR/graph-spotcheck.sh" >/dev/null

vitiligo_info "Building candidate report"
vitiligo_run report candidates \
  --json "$JSON_OUT" \
  --markdown "$MD_OUT"

vitiligo_info "Done"
echo "  JSON:     $JSON_OUT"
echo "  Markdown: $MD_OUT"
