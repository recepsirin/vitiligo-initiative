# Scripts

Operational helpers for the Vitiligo Initiative engine. Run from the repository root.

| Script | Purpose |
|--------|---------|
| [`docker-entrypoint.sh`](docker-entrypoint.sh) | Container entrypoint (used by Dockerfile) |
| [`deploy/common.sh`](deploy/common.sh) | Shared shell helpers |
| [`deploy/docker-smoke.sh`](deploy/docker-smoke.sh) | Build image + run local smoke test |
| [`deploy/fly-deploy-all.sh`](deploy/fly-deploy-all.sh) | One-shot Fly deploy (prepare → deploy → upload → seed → health) |
| [`deploy/verify-public.sh`](deploy/verify-public.sh) | Post-deploy smoke test (health, legal pages, search API) |
| [`deploy/fly-first-deploy.sh`](deploy/fly-first-deploy.sh) | First-time Fly.io app, volume, secrets, deploy |
| [`deploy/prepare-db.sh`](deploy/prepare-db.sh) | Verify DB + stats before Fly upload |
| [`review/graph-spotcheck.sh`](review/graph-spotcheck.sh) | Automated KG v1 spot-check |
| [`deploy/fly-upload-db.sh`](deploy/fly-upload-db.sh) | Upload `data/vitiligo.db` to Fly volume |
| [`deploy/fly-seed-graph.sh`](deploy/fly-seed-graph.sh) | Run `vitiligo graph seed` on Fly |
| [`deploy/fly-redeploy.sh`](deploy/fly-redeploy.sh) | Redeploy container only |
| [`ingest/common.sh`](ingest/common.sh) | Ingest script helpers |
| [`ingest/geo.sh`](ingest/geo.sh) | Full GEO metadata ingest + embed |
| [`ingest/sync-engine.sh`](ingest/sync-engine.sh) | GEO + graph seed + embed + stats |

## Examples

```bash
# Local Docker smoke test
./scripts/deploy/docker-smoke.sh

# Verify corpus before upload
./scripts/deploy/prepare-db.sh
./scripts/deploy/prepare-db.sh --gzip

# Fly.io (requires: fly auth login, ANTHROPIC_API_KEY, data/vitiligo.db)
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/deploy/fly-deploy-all.sh
./scripts/deploy/verify-public.sh

# Or step-by-step:
./scripts/deploy/fly-first-deploy.sh
./scripts/deploy/fly-upload-db.sh
./scripts/deploy/fly-seed-graph.sh

# Override app name
FLY_APP=my-engine ./scripts/deploy/fly-redeploy.sh

# Ingestion / derived artifacts
./scripts/ingest/geo.sh              # full GEO (~311 GSE series) + embed
./scripts/ingest/geo.sh 10             # smoke test (10 records)
WITH_GEO=0 ./scripts/ingest/sync-engine.sh   # graph seed + embed only
./scripts/ingest/sync-engine.sh        # GEO + graph + embed + stats
vitiligo graph export -o exports/graph-review.json
./scripts/review/graph-spotcheck.sh
```

See [`docs/deploy.md`](../docs/deploy.md) for full deployment documentation.
