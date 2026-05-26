#!/usr/bin/env bash
# Automated sanity checks for knowledge graph v1 expert spot-check.
#
# Exits non-zero if core vitiligo graph invariants fail.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/../deploy/common.sh"

EXPORT_PATH="${1:-exports/graph-review.json}"

vitiligo_cd_root

vitiligo_info "Graph stats"
if ! vitiligo_run graph stats; then
  echo "error: graph stats failed (run: vitiligo graph seed)" >&2
  exit 1
fi

vitiligo_info "Vitiligo neighbors (sample)"
vitiligo_run graph neighbors vitiligo -l 8

vitiligo_info "Running invariant checks"
PYTHON="$(dirname "$(vitiligo_bin)")/python"
"$PYTHON" - <<'PY'
from __future__ import annotations

import sys

from vitiligo.graph.query import get_neighbors, search_entities, summarize_graph
from vitiligo.storage import get_engine, init_db
from vitiligo.storage.models import EntityKind, GraphEntity
from sqlmodel import Session, select

init_db()
summary = summarize_graph()
counts = {r.label: r.count for r in summary["total"]}
by_predicate = {r.label: r.count for r in summary.get("by_predicate", [])}
entities = counts.get("entities", 0)
edges = counts.get("edges", 0)
errors: list[str] = []

if entities < 100:
    errors.append(f"too few entities ({entities}) — expected hundreds after seed")
if edges < 100:
    errors.append(f"too few edges ({edges}) — expected hundreds after seed")

with Session(get_engine(), expire_on_commit=False) as session:
    vitiligo = session.exec(
        select(GraphEntity).where(
            GraphEntity.kind == EntityKind.DISEASE,
            GraphEntity.key == "vitiligo",
        )
    ).first()
    if vitiligo is None:
        errors.append("missing vitiligo disease anchor node")

neighbors = get_neighbors("vitiligo", hops=1, limit=50)
if len(neighbors) < 10:
    errors.append(f"vitiligo has only {len(neighbors)} neighbor edges (expected many)")

if not search_entities("ruxolitinib", limit=5):
    errors.append("no ruxolitinib entity found (priors/trials seed may be missing)")

if not search_entities("JAK1", limit=3):
    errors.append("no JAK1 target entity found")

for expected, minimum in (("treats", 50), ("associated_with", 50), ("investigates", 50)):
    if by_predicate.get(expected, 0) < minimum:
        errors.append(f"too few '{expected}' edges ({by_predicate.get(expected, 0)})")

if errors:
    print("SPOT-CHECK FAILED:", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    sys.exit(1)

print("SPOT-CHECK OK")
print(f"  entities={entities} edges={edges} vitiligo_neighbors={len(neighbors)}")
PY

if [[ -f "$EXPORT_PATH" ]]; then
  vitiligo_info "Export file present: $EXPORT_PATH ($(du -h "$EXPORT_PATH" | awk '{print $1}'))"
else
  vitiligo_warn "No export at $EXPORT_PATH — run: vitiligo graph export -o $EXPORT_PATH"
fi

cat <<EOF

Manual spot-check (5–10 min):
  - Open $EXPORT_PATH and skim drug→vitiligo and target→vitiligo edges
  - Confirm Phase 3 drugs appear (ruxolitinib, povorcitinib, upadacitinib)
  - Flag any obvious wrong organism or unrelated disease links

EOF
