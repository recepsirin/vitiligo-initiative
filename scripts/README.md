# Scripts

Operational helpers for the Vitiligo Initiative engine. Run from the repository root.

| Script | Purpose |
|--------|---------|
| [`docker-entrypoint.sh`](docker-entrypoint.sh) | Container entrypoint (used by Dockerfile) |
| [`lib/common.sh`](lib/common.sh) | Shared shell helpers |
| [`deploy/docker-smoke.sh`](deploy/docker-smoke.sh) | Build image + run local smoke test |
| [`deploy/fly-first-deploy.sh`](deploy/fly-first-deploy.sh) | First-time Fly.io app, volume, secrets, deploy |
| [`deploy/fly-upload-db.sh`](deploy/fly-upload-db.sh) | Upload `data/vitiligo.db` to Fly volume |
| [`deploy/fly-seed-graph.sh`](deploy/fly-seed-graph.sh) | Run `vitiligo graph seed` on Fly |
| [`deploy/fly-redeploy.sh`](deploy/fly-redeploy.sh) | Redeploy container only |

## Examples

```bash
# Local Docker smoke test
./scripts/deploy/docker-smoke.sh

# Fly.io (requires flyctl + ANTHROPIC_API_KEY)
./scripts/deploy/fly-first-deploy.sh
./scripts/deploy/fly-upload-db.sh
./scripts/deploy/fly-seed-graph.sh

# Override app name
FLY_APP=my-engine ./scripts/deploy/fly-redeploy.sh
```

See [`docs/deploy.md`](../docs/deploy.md) for full deployment documentation.
