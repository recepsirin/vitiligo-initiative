# Release Checklist — Evidence Engine v1.0.0

**Goal:** Advisor-ready engine with reproducible evidence outputs; public URL deferred.  
**Hosting:** **Local-first** (May 2026). **DigitalOcean** planned for public deploy.

---

## Pre-release (local)

```bash
./scripts/deploy/prepare-db.sh
./scripts/review/graph-spotcheck.sh
./scripts/review/kol-share-pack.sh
.venv/bin/pytest tests/ -q
.venv/bin/ruff check src tests

# Local release gate (full corpus + smoke)
./scripts/audit/smoke-all.sh

# Local UI smoke
vitiligo serve &
./scripts/deploy/verify-local.sh
```

- [x] `data/vitiligo.db` present (~273 MB, 14k+ docs)
- [x] Graph spot-check passes
- [x] KOL pack generated (`exports/kol-share-*.tar.gz`)
- [x] Candidate report in pack (`candidate-report-v1.md`)
- [x] 250 tests green (CI: ~158 fast + ~76 confidence; corpus (11) and smoke (5) local-only)
- [x] Local demo verified (`verify-local.sh`)

---

## Advisor outreach (no public URL required)

```bash
./scripts/review/kol-share-pack.sh
vitiligo serve   # screen-share demo
```

- [ ] KOL email sent with share pack ([`advisor-outreach.md`](advisor-outreach.md))
- [ ] First advisor session scheduled or held
- [x] `retrieval-eval.json` exported (label with `advisor_relevance` 1-5, then `promote-eval-to-manifest.py --update --apply` → `build_regression_db.py` → `pytest -m confidence`)

Semantic search applies evidence-adjusted scores after cosine similarity (mouse -0.08, in-vitro -0.05); `/api/search` returns the adjusted score.

---

## Public deploy (deferred — DigitalOcean)

When ready for a public URL, implement DO deploy per [`deploy.md`](deploy.md).

- [ ] DigitalOcean Droplet or App Platform + persistent volume
- [ ] `ANTHROPIC_API_KEY` in host secrets (not in repo)
- [ ] `/api/health` → `"ready": true`, documents > 0, graph stats > 0
- [ ] `/privacy` and `/terms` load
- [ ] `BASE_URL=https://your-host.example ./scripts/deploy/verify-public.sh`

---

## Post-release

- [ ] Update README with public URL (when DO deploy exists)
- [x] Git tag `v1.0.0` pushed (GitHub Release: push future `v*` tags or run [`scripts/release/create-github-release.sh`](../scripts/release/create-github-release.sh); workflow [`.github/workflows/release.yml`](../.github/workflows/release.yml))
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
