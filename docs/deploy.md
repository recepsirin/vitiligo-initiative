# Deploy and hosting

## Local (current)

The engine runs local-first. Advisors see it by screen share and the review pack, not a public URL.

```bash
vitiligo serve                       # http://127.0.0.1:8765
./scripts/deploy/verify-local.sh     # smoke test
./scripts/review/kol-share-pack.sh   # advisor pack
```

## Public hosting

Any host works if it can run the Docker image with a persistent volume for `vitiligo.db`. `render.yaml` is a ready blueprint. DigitalOcean (about $12–24 a month) is the planned long-term host and has no scripts yet.

**No domain is needed.** Render serves the blueprint at `<name>.onrender.com` with TLS, from the service's `name`. A custom domain is a presentation choice, not a requirement. The `starter` plan is, though: Render's free tier has no persistent disks, and the corpus needs one.

**Render:**
1. New Blueprint → select `render.yaml`.
2. No API key to set: the served app makes no model call.
3. Upload `vitiligo.db` to `/var/data/vitiligo.db` and restart the service.

**Before upload:** `./scripts/deploy/prepare-db.sh [--gzip]` validates the corpus. **After deploy:** `BASE_URL=https://… ./scripts/deploy/verify-public.sh`. If `/api/health` shows no graph entities, run `vitiligo graph seed` on the server.

**Docker locally:**

```bash
./scripts/deploy/docker-smoke.sh
# or
docker build -t vitiligo-engine .
docker run --rm -p 8765:8765 -v "$(pwd)/data:/data" vitiligo-engine
```

Both of those mount `data/` over `/data`, so the corpus comes from the mount. That
is the right test for a host with a volume, and the wrong one for a host without:
it would pass even if the corpus baked into the image were missing. To check the
image carries its own corpus, run it with no `-v` at all:

```bash
docker run --rm -p 8765:8765 vitiligo-engine
curl -s localhost:8765/api/health
```

Look for `"ready": true` with a non-zero document and trial count. `"degraded"`
with `documents: 0` means the image has no corpus — and the page would still
answer 200 with an empty table rather than erroring, so this is worth checking
before a deploy rather than after.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VITILIGO_DB_PATH` | `data/vitiligo.db` | Corpus path |
| `VITILIGO_RATE_LIMIT_POST_PER_MINUTE` | `30` | POST limit per client (`0` = off) |
| `VITILIGO_TRUSTED_PROXY_HOPS` | `0` | Proxies in front of the app. The client IP and URL scheme are read that many entries from the right of `X-Forwarded-For` / `X-Forwarded-Proto` (Render: `1`). Never set it higher than the real proxy count. |
| `VITILIGO_PREWARM_EMBEDDINGS` | `true` | Load the embedding model at startup |
| `FASTEMBED_CACHE_PATH` | — | Embedding model cache |
| `PORT` | — | Host port override |

## Monitoring and safety

- `GET /api/health` (readiness, version, corpus counts) and `GET /api/stats`.
- Over-limit clients get HTTP 429 with `Retry-After`.
- Per-client limits live in process memory, so run one uvicorn worker (the entrypoint does).
- Never commit `.env`, keys or `vitiligo.db`. Add authentication before a wide public launch if abuse appears.

The engine calls no model API, so a deployment needs no key, no spend cap and
no budget state — there is nothing to vault, leak or rotate.
