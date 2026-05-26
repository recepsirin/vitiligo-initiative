# Review scripts

| Script | Purpose |
|--------|---------|
| [`graph-spotcheck.sh`](graph-spotcheck.sh) | Automated KG v1 invariant checks + manual review checklist |

```bash
vitiligo graph export -o exports/graph-review.json
./scripts/review/graph-spotcheck.sh
```

Exit code 0 = automated checks passed. Still do a quick manual skim of the export before sharing with advisors.
