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

**Not yet implemented** — add DO-specific deploy scripts when you are ready for a public URL.

Rough cost expectation: ~$12–24/mo for a small always-on instance + block storage.

After deploy, verify with:

```bash
BASE_URL=https://your-host.example ./scripts/deploy/verify-public.sh
```

Use `./scripts/deploy/prepare-db.sh` (optionally `--gzip`) to validate the corpus before uploading `vitiligo.db` to the host volume. Seed the graph on the server with `vitiligo graph seed` if `/api/health` shows zero graph entities.

---

## Render (optional alternative)

`render.yaml` remains as an optional blueprint. Same SQLite-on-disk requirement as DigitalOcean. Lower priority than DO path.

1. Connect the GitHub repo in Render → **New Blueprint** → select `render.yaml`
2. Set `ANTHROPIC_API_KEY` in the dashboard
3. Upload `vitiligo.db` to the attached disk at `/var/data/vitiligo.db` (restart the service afterward so the in-process embedding index reloads; mtime changes also trigger reload on the next search)

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

Helper scripts: [`scripts/deploy/`](../scripts/deploy/) — `docker-smoke.sh`, `verify-local.sh`, `verify-public.sh`, `prepare-db.sh`.

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
