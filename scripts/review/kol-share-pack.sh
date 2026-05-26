#!/usr/bin/env bash
# Bundle materials for KOL advisor review (graph export, briefs, spot-check, retrieval eval, candidate report).
#
# Usage:
#   ./scripts/review/kol-share-pack.sh
#   ./scripts/review/kol-share-pack.sh exports/my-kol-pack
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/../deploy/common.sh"

STAMP="$(date +%Y%m%d)"
OUT="${1:-exports/kol-share-${STAMP}}"

vitiligo_cd_root
mkdir -p "$OUT"

vitiligo_info "Building KOL share pack at $OUT"

vitiligo_info "Graph spot-check"
if ! "$SCRIPT_DIR/graph-spotcheck.sh" >"$OUT/spotcheck.log" 2>&1; then
  echo "error: graph spot-check failed — see $OUT/spotcheck.log" >&2
  exit 1
fi

vitiligo_info "Graph export"
vitiligo_run graph export -o "$OUT/graph-review.json"

vitiligo_info "Retrieval evaluation"
OUTPUT="$OUT/retrieval-eval.json" "$SCRIPT_DIR/run-eval-retrieval.sh"

vitiligo_info "Candidate report"
vitiligo_run report candidates \
  --json "$OUT/candidate-report.json" \
  --markdown "$OUT/candidate-report-v1.md"
cp docs/candidate-intents.json "$OUT/"

vitiligo_info "Copy briefs"
cp docs/scientific-brief.md docs/kol-meeting-prep.md docs/eval-queries.json "$OUT/"

cat >"$OUT/README.txt" <<EOF
Vitiligo Initiative — KOL review pack (${STAMP})

Contents:
  scientific-brief.md       — disease + engine context
  kol-meeting-prep.md       — meeting agenda and demo script
  graph-review.json         — full knowledge graph export for edge review
  spotcheck.log             — automated graph invariant checks (should pass)
  retrieval-eval.json       — 20 semantic search queries + top-5 hits each
  eval-queries.json         — query definitions (for methods paper evaluation)
  candidate-report-v1.md    — evidence-scored therapeutic candidate rankings
  candidate-report.json     — machine-readable candidate report
  candidate-intents.json    — research intents used for per-intent rankings

Advisor tasks:
  1. Skim graph-review.json for drug→vitiligo and target→vitiligo edges
  2. Label retrieval-eval.json hits (advisor_relevance 1–5, advisor_comments)
  3. Review candidate-report-v1.md — validate top 10 rankings and missing drugs
  4. Note any missing Phase 3 drugs or pivotal trials

Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Engine version: $(vitiligo_run version 2>/dev/null | tail -1 || echo unknown)
EOF

ARCHIVE="${OUT}.tar.gz"
tar -czf "$ARCHIVE" -C "$(dirname "$OUT")" "$(basename "$OUT")"

vitiligo_info "Pack ready"
echo "  Directory: $OUT"
echo "  Archive:   $ARCHIVE ($(du -h "$ARCHIVE" | awk '{print $1}'))"
echo ""
echo "Attach $ARCHIVE to advisor email (see docs/advisor-outreach.md)."
