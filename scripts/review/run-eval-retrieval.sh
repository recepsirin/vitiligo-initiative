#!/usr/bin/env bash
# Run retrieval evaluation over docs/eval-queries.json (semantic search top-K).
#
# Usage:
#   ./scripts/review/run-eval-retrieval.sh
#   ./scripts/review/run-eval-retrieval.sh -o exports/retrieval-eval.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deploy/common.sh
source "$SCRIPT_DIR/../deploy/common.sh"

QUERIES_PATH="${QUERIES_PATH:-docs/eval-queries.json}"
OUTPUT="${OUTPUT:-exports/retrieval-eval.json}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output) OUTPUT="$2"; shift 2 ;;
    -q|--queries) QUERIES_PATH="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [-o OUTPUT] [-q QUERIES_JSON]" >&2
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

vitiligo_cd_root

if [[ ! -f "$QUERIES_PATH" ]]; then
  echo "error: queries file not found: $QUERIES_PATH" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"
PYTHON="$(dirname "$(vitiligo_bin)")/python"

vitiligo_info "Running retrieval eval -> $OUTPUT"
"$PYTHON" - "$QUERIES_PATH" "$OUTPUT" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from vitiligo.embed.search import semantic_search
from vitiligo.evidence import classify_document, evidence_level_label

queries_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
spec = json.loads(queries_path.read_text())
top_k = int(spec.get("top_k", 5))

runs = []
for item in spec["queries"]:
    query = item["query"]
    hits = semantic_search(query=query, top_k=top_k)
    runs.append(
        {
            "id": item["id"],
            "category": item.get("category"),
            "query": query,
            "review_notes": item.get("review_notes"),
            "advisor_relevance": None,
            "advisor_comments": "",
            "results": [
                {
                    "rank": rank,
                    "score": round(hit.score, 4),
                    "source": hit.document.source.value,
                    "source_id": hit.document.source_id,
                    "title": hit.document.title,
                    "year": hit.document.year,
                    "journal": hit.document.journal,
                    "doi": hit.document.doi,
                    "evidence_level": classify_document(hit.document).value,
                    "evidence_level_label": evidence_level_label(
                        classify_document(hit.document)
                    ),
                }
                for rank, hit in enumerate(hits, start=1)
            ],
        }
    )

payload = {
    "generated_at": datetime.now(UTC).isoformat(),
    "queries_file": str(queries_path),
    "top_k": top_k,
    "query_count": len(runs),
    "runs": runs,
}

output_path.write_text(json.dumps(payload, indent=2) + "\n")
print(f"wrote {len(runs)} query runs to {output_path}")
PY

vitiligo_info "Done. Share with advisor for relevance labeling (1–5 per top hit)."
