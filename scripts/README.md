# Scripts

Operational helpers for the Vitiligo Initiative engine. Run from the repository root.

| Script | Purpose |
|--------|---------|
| [`docker-entrypoint.sh`](docker-entrypoint.sh) | Container entrypoint (used by Dockerfile) |
| [`deploy/common.sh`](deploy/common.sh) | Shared shell helpers |
| [`deploy/docker-smoke.sh`](deploy/docker-smoke.sh) | Build image + run local smoke test |
| [`deploy/fly-deploy-all.sh`](deploy/fly-deploy-all.sh) | **Deprecated** — one-shot Fly deploy (use DigitalOcean when public) |
| [`deploy/verify-public.sh`](deploy/verify-public.sh) | Post-deploy smoke test (health, legal pages, search API) |
| [`deploy/auth-check.sh`](deploy/auth-check.sh) | **Deprecated** — Fly login check |
| [`deploy/verify-local.sh`](deploy/verify-local.sh) | Smoke test against local `vitiligo serve` |
| [`deploy/fly-first-deploy.sh`](deploy/fly-first-deploy.sh) | **Deprecated** — first-time Fly.io app |
| [`deploy/prepare-db.sh`](deploy/prepare-db.sh) | Verify DB + stats before upload |
| [`review/generate-candidate-report.sh`](review/generate-candidate-report.sh) | Evidence-first candidate rankings (JSON + Markdown) |
| [`review/kol-share-pack.sh`](review/kol-share-pack.sh) | Bundle advisor review materials (graph + briefs + retrieval eval) |
| [`review/run-eval-retrieval.sh`](review/run-eval-retrieval.sh) | Run 20-query semantic search evaluation set |
| [`review/graph-spotcheck.sh`](review/graph-spotcheck.sh) | Automated KG v1 spot-check |
| [`deploy/fly-upload-db.sh`](deploy/fly-upload-db.sh) | **Deprecated** — Fly volume upload |
| [`deploy/fly-seed-graph.sh`](deploy/fly-seed-graph.sh) | **Deprecated** — graph seed on Fly |
| [`deploy/fly-redeploy.sh`](deploy/fly-redeploy.sh) | **Deprecated** — Fly container redeploy |
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

See [`docs/deploy.md`](../docs/deploy.md) — **local-first**; Fly.io deprecated; DigitalOcean planned.
