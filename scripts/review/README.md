# Review scripts

| Script | Purpose |
|--------|---------|
| [`graph-spotcheck.sh`](graph-spotcheck.sh) | Automated KG v1 invariant checks + manual review checklist |
| [`run-eval-retrieval.sh`](run-eval-retrieval.sh) | Semantic search over [`docs/eval-queries.json`](../../docs/eval-queries.json) |
| [`promote-eval-to-manifest.py`](promote-eval-to-manifest.py) | Promote advisor-labeled eval hits into `regression_expectations.json` |
| [`kol-share-pack.sh`](kol-share-pack.sh) | Bundle graph export, briefs, spot-check log, retrieval eval (`.tar.gz`) |
| [`generate-candidate-report.sh`](generate-candidate-report.sh) | Evidence-first candidate rankings → JSON + Markdown |

```bash
# Automated graph checks
vitiligo graph export -o exports/graph-review.json
./scripts/review/graph-spotcheck.sh

# Retrieval evaluation (20 advisor-labeled queries)
./scripts/review/run-eval-retrieval.sh -o exports/retrieval-eval.json
# Advisors set advisor_relevance (1-5) on each top hit (or on the run).
python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json
python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json --apply          # add new cases
python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json --update --apply # refresh existing
python scripts/test/build_regression_db.py
pytest -m confidence

# Evidence-first candidate report (deterministic scoring)
./scripts/review/generate-candidate-report.sh
# Optional LLM narrative layer: WITH_LLM=1 ./scripts/review/generate-candidate-report.sh

# Full advisor email attachment (~120 KB)
./scripts/review/kol-share-pack.sh
```

Exit code 0 on spot-check = automated checks passed. Advisors still label relevance in `retrieval-eval.json` and skim `graph-review.json`.
