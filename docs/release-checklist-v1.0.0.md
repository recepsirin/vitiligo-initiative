# Release Checklist — Evidence Engine v1.0.0

**Goal:** Public URL live, advisor-ready, methods evaluation in flight.  
**Target app:** `vitiligo-evidence-engine` (Fly.io `ams`)

---

## Pre-deploy (local)

```bash
./scripts/deploy/prepare-db.sh
./scripts/review/graph-spotcheck.sh
./scripts/review/kol-share-pack.sh
.venv/bin/pytest tests/ -q
.venv/bin/ruff check src tests

# Optional: local UI smoke
vitiligo serve &
./scripts/deploy/verify-local.sh
```

- [ ] `data/vitiligo.db` present (~273 MB, 14k+ docs)
- [ ] Graph spot-check passes
- [ ] KOL pack generated (`exports/kol-share-*.tar.gz`)
- [ ] 60 tests green

---

## Deploy (Fly.io)

```bash
fly auth login
./scripts/deploy/auth-check.sh
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/deploy/fly-deploy-all.sh
./scripts/deploy/verify-public.sh
```

- [ ] `fly auth whoami` succeeds
- [ ] `ANTHROPIC_API_KEY` set via `fly secrets` (not in repo)
- [ ] `/api/health` → `"ready": true`, documents > 0, graph stats > 0
- [ ] `/privacy` and `/terms` load
- [ ] Search API returns results
- [ ] Ask + Hypothesize work (LLM configured)

---

## Post-deploy (same day)

- [ ] Update README Status with public URL
- [ ] Git tag `v1.0.0` + GitHub release notes (see [`CHANGELOG.md`](../CHANGELOG.md))
- [ ] Zenodo DOI *optional for v1.0.0; target for methods preprint*
- [ ] Send KOL email with live URL + share pack ([`advisor-outreach.md`](advisor-outreach.md))
- [ ] Log launch decision in [`open-questions-resolutions.md`](open-questions-resolutions.md)

---

## Phase 1 gate closure

| Gate | Done when |
|------|-----------|
| Public deploy | URL verified above |
| KOL meeting | First session held with live tool |
| Methods path | Advisor labels `retrieval-eval.json`; expand preprint draft |

---

## Rollback

```bash
fly releases -a vitiligo-evidence-engine
fly deploy --image <previous-image> -a vitiligo-evidence-engine
# DB on volume is unchanged unless re-uploaded
```

---

## Cost sanity check (Fly.io)

- 2 shared CPU, 2 GB RAM, 1 GB volume — review Fly dashboard after first week
- `auto_stop_machines = false` in `fly.toml` — expect always-on cost
