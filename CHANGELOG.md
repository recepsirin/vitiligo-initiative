# Changelog

All notable changes to the Vitiligo Initiative Evidence Engine are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- **JAK-inhibitor atlas** (`vitiligo report jak`): every vitiligo trial of a JAK-family drug, linked across registries, with posted outcomes, adverse events, publications and Open Targets stage. JSON, Markdown and CSV.
- **Harmonized arm table** (`vitiligo report jak-arms`): one row per arm × responder endpoint × week, with parsed dose, regimen and review flags; raw values kept beside parsed ones.
- **Scenario model v0.2** (`vitiligo model predict|backtest`, `[model]` extra): Bayesian ordered-probit meta-analysis with held-out back-tests, convergence-gated predictions and SHA-256-sealed forecasts. See `docs/jak-scenario-model.md`.
- **Sealed forecasts**: 4 for ritlecitinib Tranquillo (`forecasts/2026-10-14-tranquillo/`) and 11 for other unreported trials (`forecasts/2026-10-14-auto/`), all frozen without consulting results. A topline check found 12 had public toplines before sealing, so only 3 are prospective (`forecasts/TOPLINE-CHECK-2026-10-14.md`).
- **Discovery loop v1** (`vitiligo discover run|ledger|import-forecasts`): claims tested on held-out trials with mixture e-values under e-LOND false-discovery-rate control, in three families (superiority, regimen contrast, dose retention). Every test is kept in a separate ledger. See `docs/discovery-loop-plan.md`.
- **Forecast automation**: `vitiligo discover forecast-pending` seals forecasts for every unreported trial the registry describes well enough. Sealing now requires `--public-results-check`, recording where already-public results were searched for. `vitiligo discover resolve` (ledger) and `vitiligo discover check-forecasts` (sealed files, no corpus) score them once results post; `.github/workflows/forecast-check.yml` runs the check weekly and only reports.
- **Simulator trial run** (`lab/simulator/`): a pre-registered search over mechanistic repigmentation models. It beat the scenario model on search data but failed its locked exam, so it was stopped; the write-up explains why.
- **Curated paper results** (`curation/paper-results.json`, `vitiligo papers tables|verify`, `report jak-arms --with-papers`): results from open-access papers that registries lack, each tied to its printed table cell and tagged with its analysis population. First batch: 41 numbers from the upadacitinib and ruxolitinib phase 2 reports; all match their cells, and the 12 also in the registry agree exactly.
- **Findings page** (`docs/findings.md`): what the JAK work found and the questions for expert reviewers. The review pack (`scripts/review/kol-share-pack.sh`) now includes the atlas, arm table, model docs, forecasts and curated data.
- **Scenario model v0.3, pre-registered** (`docs/model-v0.3-preregistration.md`, `scripts/model/evaluate_v03.py`): adds a trial-by-treatment effect, a phase 3 shift per route, curated paper rows and public phase 3 toplines (`curation/topline-results.json`). It is opt-in (`FitSettings(version="v0.3")`); v0.2 stays the default and is unchanged. **Not adopted:** on the held-out phase 3 toplines it scored −54.29 vs v0.2's −54.13. A pre-registered challenger, v0.4 (trained on the toplines), has sealed forecasts for the same 7 targets as v0.2 (`forecasts/v0.4/`); they are compared as results post. A second challenger, v0.5 (`FitSettings(version="v0.5")`: separate baseline means for oral-placebo and topical-vehicle trials), has sealed forecasts for the same targets (`forecasts/v0.5/`). `discover check-forecasts` now shows each forecast's model and compares the models' summed log scores on targets every model has scored.
- **`vitiligo db repair [--apply]`**: fixes v1.0.0 corpora in place (truncated PubMed titles, GEO sample records) and drops affected embeddings for `embed run`.

### Fixed

- **Security: rate-limit bypass.** The POST limiter trusted the client-controlled `X-Forwarded-For`. Clients are now keyed by the TCP peer; behind proxies set `VITILIGO_TRUSTED_PROXY_HOPS` (Render: `1`). New global Ask/Hypothesize caps: `VITILIGO_LLM_REQUESTS_PER_MINUTE`, `VITILIGO_LLM_DAILY_TOKEN_BUDGET`.
- **Hypothesize returned no trials** for natural-language intents (matched as one literal phrase). Intents are now tokenized and weighted by rarity and field.
- **Approved drugs dropped from Hypothesize priors** (stages sorted as text). Stages now sort by rank.
- **Candidate report**: trial phases never matched the rubric; salt forms could downgrade a drug's stage; literature retrieval ran once per drug (~92 s → ~4 s).
- **`/api/report/candidates` failed in Docker and wheels**: the intents file now ships as package data.
- **Corpus parsing**: PubMed titles truncated at inline markup (199 records), GEO sample records ingested as series (257 of 311), duplicated text in PMC abstracts, and stale embeddings after re-ingest. Run `vitiligo db repair --apply`, `vitiligo ingest pmc`, then `vitiligo embed run`.
- **Docs**: `vitiligo ingest ictrp|drugbank` take the file as an argument, not `--file`.

### Changed

- **Candidate report trial score** uses the best trial evidence instead of a sum (still 0–35); the report and validation proposals were regenerated.
- **`GET /api/report/candidates`** is cached until the corpus changes.
- **Docs** rewritten for brevity: one architecture diagram, one CLI reference, a shorter README and strategic plan, and the methods-preprint outline merged into the draft.

## [1.0.0] — 2026-05-26

First **local-first, advisor-ready** release of the open vitiligo Evidence Engine. Public URL deploy is deferred (DigitalOcean planned); this release ships reproducible evidence outputs, review tooling, and a CI quality gate.

### Added

- **Corpus ingestion** — PubMed, PMC Open Access, GEO DataSets, ClinicalTrials.gov, EU CTR (CTIS), Open Targets, WHO ICTRP (XML), DrugBank (XML)
- **Document store** — SQLite with resumable ingestion runs; ~14,245 documents and ~14,242 embeddings locally
- **Semantic search** — fastembed `BAAI/bge-small-en-v1.5`, evidence-level tagging, evidence-adjusted ranking (mouse −0.08, in-vitro −0.05 after cosine similarity)
- **Clinical trials search** — cross-registry filter (source, status, phase, country, results)
- **RAG Ask** — cited answers over retrieved papers (Anthropic Claude)
- **Hypothesize** — four evidence streams: papers `[n]`, trials `[Tn]`, priors `[Pn]`, graph `[Gn]`
- **Knowledge graph v1** — deterministic seed from priors + trials; CLI + API + Graph tab
- **Web UI** — Search, Ask, Hypothesize, Graph, Trials; beta badge and medical disclaimers
- **Legal pages** — `/privacy`, `/terms`
- **Deploy tooling** — Docker, `verify-public.sh`, `verify-local.sh`, `prepare-db.sh`
- **Review tooling** — graph spot-check, KOL share pack, 20-query retrieval evaluation set, advisor promote script (`promote-eval-to-manifest.py`)
- **Test suite (244 tests)** — unit / integration / API / confidence / corpus / smoke pyramid; `./scripts/audit/smoke-all.sh` local release gate
- **Confidence regression gate (CI)** — manifest-driven retrieval, trials, candidates, Ask/Hypothesize plumbing on minimal regression corpus (~76 tests)
- **Planning docs** — scientific brief, governance brief, KOL prep, methods preprint outline, advisor outreach
- **CI** — GitHub Actions (ruff + fast pytest + confidence regression)

### Corpus snapshot (local build)

| Source | Records |
|--------|---------|
| PubMed | 11,356 |
| PMC | 2,578 |
| GEO | 311 |
| Trials | 344 |
| Open Targets priors | 237 |
| Graph entities / edges | 1,044 / 1,643 |

### Known limitations

- **Local-first v1.0.0** — no public production URL in this release; advisors use KOL share pack + local demo
- LLM features require server-side `ANTHROPIC_API_KEY`
- PMC full-text chunk embeddings not yet shipped
- No hybrid BM25 + vector retrieval
- Graph v1 is structured seed; full-corpus LLM extraction optional and not default
- Privacy/Terms and contact emails are drafts pending legal review
- Confidence gate runs on a 26-paper regression slice; full-corpus ranking drift requires local `smoke-all.sh`

[1.0.0]: https://github.com/recepsirin/vitiligo-initiative/releases/tag/v1.0.0
