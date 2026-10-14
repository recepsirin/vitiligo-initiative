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

**Render:**
1. New Blueprint → select `render.yaml`.
2. Set `ANTHROPIC_API_KEY` in the dashboard.
3. Upload `vitiligo.db` to `/var/data/vitiligo.db` and restart the service.

**Before upload:** `./scripts/deploy/prepare-db.sh [--gzip]` validates the corpus. **After deploy:** `BASE_URL=https://… ./scripts/deploy/verify-public.sh`. If `/api/health` shows no graph entities, run `vitiligo graph seed` on the server.

**Docker locally:**

```bash
./scripts/deploy/docker-smoke.sh
# or
docker build -t vitiligo-engine .
docker run --rm -p 8765:8765 -e ANTHROPIC_API_KEY -v "$(pwd)/data:/data" vitiligo-engine
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VITILIGO_DB_PATH` | `data/vitiligo.db` | Corpus path |
| `ANTHROPIC_API_KEY` | — | Enables Ask and Hypothesize |
| `VITILIGO_RATE_LIMIT_POST_PER_MINUTE` | `30` | POST limit per client (`0` = off) |
| `VITILIGO_TRUSTED_PROXY_HOPS` | `0` | Proxies in front of the app. The client IP and URL scheme are read that many entries from the right of `X-Forwarded-For` / `X-Forwarded-Proto` (Render: `1`). Never set it higher than the real proxy count. |
| `VITILIGO_LLM_REQUESTS_PER_MINUTE` | `0` | Ask/Hypothesize calls per minute, all clients (`0` = off; Render: `10`) |
| `VITILIGO_LLM_DAILY_TOKEN_BUDGET` | `0` | Ask/Hypothesize tokens per rolling 24 h, all clients (`0` = off; Render: `2000000`) |
| `VITILIGO_STATE_DB_PATH` | next to the corpus | Runtime state (LLM budget); keep it on the persistent volume |
| `VITILIGO_PREWARM_EMBEDDINGS` | `true` | Load the embedding model at startup |
| `FASTEMBED_CACHE_PATH` | — | Embedding model cache |
| `PORT` | — | Host port override |

## Monitoring and safety

- `GET /api/health` (readiness, version, corpus counts) and `GET /api/stats`.
- Over-limit clients get HTTP 429 with `Retry-After`.
- Per-client limits live in process memory, so run one uvicorn worker (the entrypoint does). The global LLM caps are persisted and shared.
- Set a monthly spend limit in the Anthropic console as the last line of defence.
- Never commit `.env`, keys or `vitiligo.db`. Add authentication before a wide public launch if abuse appears.
