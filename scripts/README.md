# Scripts

Operational helpers for the Vitiligo Initiative engine. Run from the repository root.

| Script | Purpose |
|--------|---------|
| [`docker-entrypoint.sh`](docker-entrypoint.sh) | Container entrypoint (used by Dockerfile) |
| [`deploy/common.sh`](deploy/common.sh) | Shared shell helpers |
| [`deploy/docker-smoke.sh`](deploy/docker-smoke.sh) | Build image + run local smoke test |
| [`deploy/verify-public.sh`](deploy/verify-public.sh) | Post-deploy smoke test (`BASE_URL` required) |
| [`deploy/verify-local.sh`](deploy/verify-local.sh) | Smoke test against local `vitiligo serve` |
| [`deploy/prepare-db.sh`](deploy/prepare-db.sh) | Verify DB + stats before host upload |
| [`review/generate-candidate-report.sh`](review/generate-candidate-report.sh) | Evidence-first candidate rankings (JSON + Markdown) |
| [`review/kol-share-pack.sh`](review/kol-share-pack.sh) | Bundle advisor review materials (graph + briefs + retrieval eval) |
| [`review/run-eval-retrieval.sh`](review/run-eval-retrieval.sh) | Run 20-query semantic search evaluation set |
| [`review/graph-spotcheck.sh`](review/graph-spotcheck.sh) | Automated KG v1 spot-check |
| [`ingest/common.sh`](ingest/common.sh) | Ingest script helpers |
| [`ingest/geo.sh`](ingest/geo.sh) | Full GEO metadata ingest + embed |
| [`ingest/sync-engine.sh`](ingest/sync-engine.sh) | GEO + graph seed + embed + stats |

## Examples

```bash
# Local demo + verification
vitiligo serve &
./scripts/deploy/verify-local.sh
./scripts/review/kol-share-pack.sh

# Ingestion / derived artifacts
./scripts/ingest/geo.sh              # full GEO (~311 GSE series) + embed
./scripts/ingest/geo.sh 10             # smoke test (10 records)
WITH_GEO=0 ./scripts/ingest/sync-engine.sh   # graph seed + embed only
./scripts/ingest/sync-engine.sh        # GEO + graph + embed + stats
vitiligo graph export -o exports/graph-review.json
./scripts/review/graph-spotcheck.sh
./scripts/review/kol-share-pack.sh   # advisor email attachment
```

See [`docs/deploy.md`](../docs/deploy.md) — **local-first**; DigitalOcean planned for public hosting.
