# Changelog

All notable changes to the Vitiligo Initiative Evidence Engine are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- **JAK-inhibitor atlas and arm table** (`vitiligo report jak`, `report jak-arms [--with-papers]`): every vitiligo trial of a JAK-family drug, linked across registries, with posted outcomes and adverse events; one harmonized row per arm × endpoint × week.
- **Curated paper results** (`curation/`, `vitiligo papers tables|verify`): results only papers report, each tied to its printed table cell and tagged with its analysis population; public phase 3 toplines with sources.
- **Scenario model** (`vitiligo model predict|backtest`, `[model]` extra): v0.2 is the default; v0.3 and v0.5 are opt-in (`FitSettings(version=...)`). Model changes are pre-registered and their seals checked by `scripts/model/verify_preregistrations.py`.
- **Sealed forecasts and scoring** (`vitiligo discover forecast-pending --public-results-check`, `discover resolve`, `discover check-forecasts`, weekly workflow): 15 v0.2 forecasts (3 prospective) and challengers v0.4 and v0.5 for 7 targets. Scoreboard: `forecasts/README.md`.
- **Value-of-information core** (`discovery/voi.py`, `scripts/model/voi_core.py`): scores how much evidence would move an answer or separate models before it is seen. It passed its pre-registered retrospective gate (narrowly). A bug found afterwards (arms of one trial were integrated separately) is fixed; post-hoc, the gate's correlation rises from 0.53 to 0.68. T-VASI values remain upper bounds (`forecasts/voi/`).
- **Povorcitinib phase 3 check** (`forecasts/povorcitinib-phase3/`): v0.2, v0.4 and v0.5 against STOP-V1/V2 F-VASI75 at week 52, post hoc; v0.4 and v0.5 beat v0.2 by about 1.5 nats. T-VASI50, whose numbers are not yet public, is sealed under all three models.
- **Weekly watch** (`vitiligo discover watch`, in the forecast-check workflow): ranks pending results by how much they would tell us about which model is right, and lists new Europe PMC papers and preprints, JAK vitiligo trials registered or updated on ClinicalTrials.gov, and SEC 8-K/6-K filings mentioning vitiligo (optional `SEC_USER_AGENT`).
- **First watch leads triaged** (`forecasts/watch-triage.md`): povorcitinib's phase 3 in China (NCT07865312, not yet recruiting) sealed under v0.2, v0.4 and v0.5; zasocitinib waits for its doses; delgocitinib's single-arm study cannot be forecast against a control. Registry parsing now reads a dose stated only on an arm's own intervention.
- **Success definition and durability** (`docs/success.md`, `docs/durability/`): four outcomes that define success, with today's best results and the current focus, durability. Includes an evidence map (TRuE-V randomized withdrawal, extracted from the registry) and the first sealed durability forecast: stopping ritlecitinib in Tranquillo LTE (pre-registered; scored by `discovery/durability.py`).
- **Safety and access** (`docs/safety-access/`): outcome 4. Two years of cream safety; oral evidence covers months, not years; US price and NICE TA1140 (funded for facial vitiligo after first-line topicals).
- **Stopping spread** (`docs/spread/`): evidence map for outcome 1. It is rarely measured (15 of 320 registered trials measure it directly), with no placebo-controlled results in active disease, and the success definition now asks for it in active disease. Also corrects the durability page: IL-15 blockade was tried in a phase 2a (AMG 714, missed its primary endpoint).
- **Durability next steps** (`docs/durability/`): evidence across treatments (NB-UVB, tacrolimus maintenance), strategies aimed at relapse, a drafted patient-level data request (TRuE-V), how informative the sealed forecast's test is, and a trial concept (stop vs twice-weekly maintenance, event-driven, sized by `scripts/durability/maintenance_trial_size.py`).
- **Ranking of pending evidence** (`forecasts/voi/ranking/`, `voi_core.py rank|rank-mc|rank-score`): pre-registered value-of-information ranking of 7 pending randomized trials, with a post-hoc check of simulation noise and a prospective test of the engine as results become public. New `predict_trial_draws` simulates a new trial with any number of arms.
- **Sealing records the code**: forecasts now carry the git commit, and sealing refuses uncommitted model code. The 2026-10-14 forecasts, sealed before their code was committed, reproduce within 1.4 points (`scripts/model/reproduce_sealed.py`).
- **Discovery loop** (`vitiligo discover run|ledger|import-forecasts`): claims tested on held-out trials under online false-discovery-rate control, recorded in a ledger.
- **Simulator trial run** (`lab/simulator/`): pre-registered; stopped after failing its locked exam.
- **Findings page** (`docs/findings.md`); the review pack now includes the JAK materials.
- **`vitiligo db repair [--apply]`**: fixes v1.0.0 corpora in place (truncated PubMed titles, GEO sample records).

### Fixed

- **Candidate report counted evidence twice.** Every graph edge is seeded from the priors and trials the score already counts, so the graph component scored them again; a paper in both PubMed and PMC counted twice under literature. Only graph edges extracted from papers now count (none yet), and each paper counts once. Totals fell by 20–26 points. The global top 10 kept its order; three of the five per-intent tables reordered below the leaders. The report now states that it measures evidence maturity, not therapeutic potential; report and validation proposals regenerated.
- **Model comparison counted targets sealed after the pre-registration.** Only the 7 pre-registered targets can now decide the default model; later targets are reported separately.
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
- **Docs** rewritten for brevity: one home per fact (findings page, forecasts scoreboard, model doc), one architecture diagram, one CLI reference, and the methods-preprint outline merged into the draft.

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
