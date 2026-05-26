# Deploy & hosting

## Current posture (May 2026)

**Local-first.** Run the Evidence Engine on your machine for development, advisor demos, and KOL review:

```bash
vitiligo serve                    # http://127.0.0.1:8765
./scripts/deploy/verify-local.sh  # smoke test
./scripts/review/kol-share-pack.sh   # advisor materials (no public URL required)
```

Share with advisors via **screen share** + the KOL pack tarball — not a public URL.

---

## Planned public hosting: DigitalOcean

When a public URL is needed, the target platform is **DigitalOcean** (likely a Droplet or App Platform with a persistent volume for `vitiligo.db`). Rationale: predictable pricing, full control over SQLite + FastAPI + fastembed, no vendor lock-in to edge/serverless constraints.

**Not yet implemented** — deploy scripts for DO will replace the Fly.io tooling below.

Rough cost expectation: ~$12–24/mo for a small always-on instance + block storage (similar to prior Fly estimates).

---

## Deprecated: Fly.io (will be removed)

Fly.io configs and scripts under `fly.toml` and `scripts/deploy/fly-*.sh` are **deprecated** and scheduled for removal. Do not use for new deployments.

<details>
<summary>Legacy Fly.io instructions (reference only)</summary>

### Prerequisites

- [Fly CLI](https://fly.io/docs/hands-on/install-flyctl/)
- A built corpus at `data/vitiligo.db` locally

### First deploy

```bash
fly auth login
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/deploy/fly-deploy-all.sh
```

Verify: `./scripts/deploy/verify-public.sh`

</details>

---

## Render (optional alternative)

`render.yaml` remains as an optional blueprint. Same SQLite-on-disk requirement as DigitalOcean. Lower priority than DO path.

1. Connect the GitHub repo in Render → **New Blueprint** → select `render.yaml`
2. Set `ANTHROPIC_API_KEY` in the dashboard
3. Upload `vitiligo.db` to the attached disk at `/var/data/vitiligo.db`

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

Helper scripts: [`scripts/deploy/`](../scripts/deploy/) (Fly scripts deprecated; `docker-smoke.sh`, `verify-local.sh`, `prepare-db.sh` still useful locally).

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VITILIGO_DB_PATH` | `data/vitiligo.db` | SQLite corpus path |
| `ANTHROPIC_API_KEY` | — | Required for `/api/ask` and `/api/hypothesize` |
| `VITILIGO_RATE_LIMIT_POST_PER_MINUTE` | `30` | Per-IP POST limit (`0` = off) |
| `VITILIGO_PREWARM_EMBEDDINGS` | `true` | Load fastembed model at startup |
| `FASTEMBED_CACHE_PATH` | — | ONNX model cache directory |
| `PORT` | — | Host platform port override |

---

## Monitoring

- **`GET /api/health`** — readiness, version, LLM configured, corpus counts
- **`GET /api/stats`** — documents, embeddings, trials breakdown

Rate-limited clients receive **HTTP 429** with a `Retry-After` header on excess POST requests to `/api/*`.

---

## Security notes

- Search and Trials are public-read; Ask/Hypothesize call Anthropic (cost exposure).
- Keep rate limits enabled in production.
- Do not commit `.env`, API keys, or `vitiligo.db`.
- Add auth (API keys, OAuth) before wide public launch if abuse becomes an issue.
