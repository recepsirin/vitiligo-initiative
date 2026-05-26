#!/usr/bin/env bash
# Generate evidence-first candidate report (JSON + Markdown).
#
# Usage:
#   ./scripts/review/generate-candidate-report.sh
#   WITH_LLM=1 ./scripts/review/generate-candidate-report.sh   # optional Anthropic narrative
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/../deploy/common.sh"

JSON_OUT="${JSON_OUT:-exports/candidate-report.json}"
MD_OUT="${MD_OUT:-docs/candidate-report-v1.md}"
WITH_LLM="${WITH_LLM:-0}"

vitiligo_cd_root

vitiligo_info "Ensuring embeddings are current"
vitiligo_run embed run

vitiligo_info "Graph spot-check"
"$SCRIPT_DIR/graph-spotcheck.sh" >/dev/null

LLM_ARGS=()
if [[ "$WITH_LLM" == "1" ]]; then
  LLM_ARGS=(--llm)
fi

vitiligo_info "Building candidate report"
vitiligo_run report candidates \
  --json "$JSON_OUT" \
  --markdown "$MD_OUT" \
  "${LLM_ARGS[@]+"${LLM_ARGS[@]}"}"

vitiligo_info "Done"
echo "  JSON:     $JSON_OUT"
echo "  Markdown: $MD_OUT"
