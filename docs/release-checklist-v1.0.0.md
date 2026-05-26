# Release Checklist — Evidence Engine v1.0.0

**Goal:** Advisor-ready engine with reproducible evidence outputs; public URL deferred.  
**Hosting:** **Local-first** (May 2026). Fly.io deprecated. **DigitalOcean** planned for public deploy.

---

## Pre-release (local)

```bash
./scripts/deploy/prepare-db.sh
./scripts/review/graph-spotcheck.sh
./scripts/review/kol-share-pack.sh
.venv/bin/pytest tests/ -q
.venv/bin/ruff check src tests

# Local UI smoke
vitiligo serve &
./scripts/deploy/verify-local.sh
```

- [ ] `data/vitiligo.db` present (~273 MB, 14k+ docs)
- [ ] Graph spot-check passes
- [ ] KOL pack generated (`exports/kol-share-*.tar.gz`)
- [ ] Candidate report in pack (`candidate-report-v1.md`)
- [ ] 71 tests green
- [ ] Local demo verified (`verify-local.sh`)

---

## Advisor outreach (no public URL required)

```bash
./scripts/review/kol-share-pack.sh
vitiligo serve   # screen-share demo
```

- [ ] KOL email sent with share pack ([`advisor-outreach.md`](advisor-outreach.md))
- [ ] First advisor session scheduled or held
- [ ] `retrieval-eval.json` relevance labels started

---

## Public deploy (deferred — DigitalOcean)

When ready for a public URL, implement DO deploy per [`deploy.md`](deploy.md). **Do not use Fly.io.**

- [ ] DigitalOcean Droplet or App Platform + persistent volume
- [ ] `ANTHROPIC_API_KEY` in host secrets (not in repo)
- [ ] `/api/health` → `"ready": true`, documents > 0, graph stats > 0
- [ ] `/privacy` and `/terms` load
- [ ] `./scripts/deploy/verify-public.sh` against public URL

---

## Post-release

- [ ] Update README with public URL (when DO deploy exists)
- [ ] Git tag `v1.0.0` + GitHub release notes (see [`CHANGELOG.md`](../CHANGELOG.md))
- [ ] Zenodo DOI *optional for v1.0.0; target for methods preprint*
- [ ] Log launch decision in [`open-questions-resolutions.md`](open-questions-resolutions.md)

---

## Phase 1 gate closure

| Gate | Done when |
|------|-----------|
| Advisor-ready engine | KOL pack + local demo verified |
| KOL meeting | First session held |
| Methods path | Advisor labels `retrieval-eval.json`; expand preprint draft |
| Public deploy | DigitalOcean URL live *(deferred)* |

---

## Cost sanity check (when on DigitalOcean)

- Small Droplet + block storage — budget ~$12–24/mo always-on
- Anthropic API usage separate — monitor Ask/Hypothesize volume
