# Review scripts

| Script | Purpose |
|--------|---------|
| [`graph-spotcheck.sh`](graph-spotcheck.sh) | Automated KG v1 invariant checks + manual review checklist |
| [`run-eval-retrieval.sh`](run-eval-retrieval.sh) | Semantic search over [`docs/eval-queries.json`](../../docs/eval-queries.json) |
| [`kol-share-pack.sh`](kol-share-pack.sh) | Bundle graph export, briefs, spot-check log, retrieval eval (`.tar.gz`) |

```bash
# Automated graph checks
vitiligo graph export -o exports/graph-review.json
./scripts/review/graph-spotcheck.sh

# Retrieval evaluation (20 advisor-labeled queries)
./scripts/review/run-eval-retrieval.sh -o exports/retrieval-eval.json

# Full advisor email attachment (~120 KB)
./scripts/review/kol-share-pack.sh
```

Exit code 0 on spot-check = automated checks passed. Advisors still label relevance in `retrieval-eval.json` and skim `graph-review.json`.
