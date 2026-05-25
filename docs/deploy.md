# Deploy the Evidence Engine (Fly.io or Render)

The web UI is a FastAPI app (`vitiligo serve`) backed by a local SQLite corpus
(~250 MB with full PubMed + PMC embeddings). Production deployment needs:

1. A container image (Dockerfile included)
2. A **persistent disk** for `vitiligo.db` (not in git)
3. **`ANTHROPIC_API_KEY`** for Ask / Hypothesize (Search and Trials work without it)

Helper scripts live under [`scripts/deploy/`](../scripts/deploy/). See [`scripts/README.md`](../scripts/README.md).

---

## Fly.io (recommended — Amsterdam `ams` region)

### Prerequisites

- [Fly CLI](https://fly.io/docs/hands-on/install-flyctl/)
- A built corpus at `data/vitiligo.db` locally

### First deploy

```bash
# Verify local corpus (optional)
./scripts/deploy/prepare-db.sh

# One-shot: app + volume + secrets + deploy
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/deploy/fly-first-deploy.sh

# Upload corpus + seed knowledge graph
./scripts/deploy/fly-upload-db.sh
./scripts/deploy/fly-seed-graph.sh
```

Manual equivalent:

```bash
fly launch --no-deploy --copy-config
fly volumes create vitiligo_data --region ams --size 1
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly deploy
fly ssh sftp shell   # put data/vitiligo.db /data/vitiligo.db
fly ssh console -C "vitiligo graph seed"
```

Verify:

```bash
fly open /api/health
# expect: "ready": true, documents > 0, graph_entities > 0
```

### Updates

```bash
./scripts/deploy/fly-redeploy.sh
# Re-upload vitiligo.db only when the corpus changes:
./scripts/deploy/fly-upload-db.sh
```

### Useful commands

```bash
fly logs
fly status
fly ssh console -C "ls -lh /data"
```

---

## Render

1. Connect the GitHub repo in Render → **New Blueprint** → select `render.yaml`
2. Set `ANTHROPIC_API_KEY` in the dashboard (sync: false in blueprint)
3. After first deploy, upload `vitiligo.db` to the attached disk at `/var/data/vitiligo.db`
   (Render shell or one-off job)

Health check: `GET /api/health` (returns `degraded` until the DB is present).

---

## Docker (local smoke test)

```bash
./scripts/deploy/docker-smoke.sh
```

Or manually:

```bash
docker build -t vitiligo-engine .
docker run --rm -p 8765:8765 \
  -e ANTHROPIC_API_KEY \
  -v "$(pwd)/data:/data" \
  vitiligo-engine
```

Open http://127.0.0.1:8765

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VITILIGO_DB_PATH` | `data/vitiligo.db` | SQLite corpus path |
| `ANTHROPIC_API_KEY` | — | Required for `/api/ask` and `/api/hypothesize` |
| `VITILIGO_RATE_LIMIT_POST_PER_MINUTE` | `30` | Per-IP POST limit (`0` = off) |
| `VITILIGO_PREWARM_EMBEDDINGS` | `true` | Load fastembed model at startup |
| `FASTEMBED_CACHE_PATH` | — | ONNX model cache directory |
| `PORT` | — | Set by Fly/Render; overrides `VITILIGO_WEB_PORT` |
| `FLY_APP` | `vitiligo-evidence-engine` | Override Fly app name in deploy scripts |

---

## Monitoring

- **`GET /api/health`** — readiness, version, LLM configured, corpus counts
- **`GET /api/stats`** — documents, embeddings, trials breakdown

Rate-limited clients receive **HTTP 429** with a `Retry-After` header on excess
POST requests to `/api/*`.

---

## Security notes

- Search and Trials are public-read; Ask/Hypothesize call Anthropic (cost exposure).
- Keep rate limits enabled in production.
- Do not commit `.env`, API keys, or `vitiligo.db`.
- Add auth (API keys, OAuth) before wide public launch if abuse becomes an issue.
