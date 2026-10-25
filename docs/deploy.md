# Deploy and hosting

## Local (current)

The engine runs local-first. Advisors see it by screen share and the review pack, not a public URL.

```bash
vitiligo serve                       # http://127.0.0.1:8765
./scripts/deploy/verify-local.sh     # smoke test
./scripts/review/kol-share-pack.sh   # advisor pack
```

## Public hosting

Not yet done, and the two things that decide it are measured, not estimated.

**It needs more than 512 MB.** Against the built image, a 512 MB container is
OOM-killed during startup — exit 137, before it logs a line — with or without
the embedding prewarm. Steady use is only 269 MiB; the peak is startup, where
`build_jak_atlas()` reaches about 140 MB over the interpreter and warming the
index another 47 MB. A 1 GB container starts in about ten seconds and serves in
about 3 ms. So the smallest viable instance is 1 GB, which rules out the free
and 512 MB tiers of the usual hosts rather than merely making them slow.

**The corpus is not in the repository.** `data/` is gitignored and
`vitiligo.db` is far over GitHub's 100 MB per-file limit, so any host that
builds from a git clone produces an image with no database, and the app comes up
degraded with zero rows while still answering 200. Either attach a volume and
upload the corpus to it, or build the image where the corpus is and push it to a
registry for the host to pull. The `COPY` in the Dockerfile is written to
succeed either way, so one image serves both.

There is no host-specific blueprint here. One lived in the repository for Render
and was never deployable: it asked for 512 MB, which cannot run this, and its
build copied a corpus that a clone does not contain. Config nobody has exercised
is worse than none, because it reads as tested.

**Before upload:** `./scripts/deploy/prepare-db.sh [--gzip]` validates the
corpus. **After deploy:** `BASE_URL=https://… ./scripts/deploy/verify-public.sh`.
If `/api/health` shows no graph entities, run `vitiligo graph seed` on the server.

**Worth weighing first.** The clinician page reads 8.4 MB of the 493 MB corpus
and serves 35 KB of JSON. Publishing that as static files costs no instance, no
memory limit and no registry, and leaves the engine local for search and the
model work.

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
