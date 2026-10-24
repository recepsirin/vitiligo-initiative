# Changelog

All notable changes to the Vitiligo Initiative Evidence Engine are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- **What the trials reported, for a clinician** (`vitiligo serve` → Trial results, `GET /api/evidence`): the arm table holds 830 rows and most of them should not be shown to someone deciding whether to prescribe. This collapses it to one row per drug, route, dose, loading dose and endpoint at **week 24** — the primary endpoint of every registered JAK trial in vitiligo, and so the only week at which they compare — beside the comparator arm of the same trial, with the open-label continuation in its own labelled column. Four rules decide what reaches it, and each one was written against a figure the first version printed: ranking by rate let NCT05247489's seven patients (85.7% F-VASI75) outrank TRuE-V2's 222 (30.9%), so the largest arm wins; ranking by week preferred NCT03099304's 100% of 9 at week 156 over 45.5% of 33 at week 24, so an arm must still report the group it randomised (80% retention, per assessor — pooling central and local reads made ritlecitinib's central 52 look like a loss from the local 67); a blinded central read beats the site's own, which ran 7.0% against 18.4% for ritlecitinib 10 mg; and facial and whole-body scores never mix, nor does ruxolitinib with NB-UVB (76.5%, uncontrolled) with ruxolitinib alone (51.4%). Ritlecitinib 50 mg QD was three arms, not one — plain, after 100 mg, after 200 mg, reaching 7.7%, 8.5% and 12.1% — and merging them reported whichever enrolled one patient more. Where two trials report the same drug and dose they are shown together, because the agreement is the finding: TRuE-V1 and TRuE-V2 read 29.8% of 221 and 30.9% of 222 at F-VASI75. Adverse events are deliberately absent; they belong in the label and the registry record.
- **The served page no longer generates anything** (`/api/ask` and `/api/hypothesize` removed; `vitiligo ask` and `vitiligo hypothesize` unchanged): a page aimed at clinicians should state what a trial reported and where to read it, not what a model infers from it, and an endpoint taking a visitor's API key is a key-handling surface a reference page does not need. The LLM-faithfulness tests now run against the library the CLI calls, so what they cover still exists. Edge evidence from sources whose licence forbids redistribution is filtered from the graph export; Open Targets (CC0) and ChEMBL (CC-BY-SA) are served as before.

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
- **Whether a hypothesis can be tested yet** (`vitiligo mechanism list|show`): the question a ranking engine is meant to answer, asked directly. The datasets a test names are read off the record and checked against the corpus; whether it needs samples nobody has collected is declared in the record, since no corpus knows that, and the gate refuses a declaration without a reason. Both records hold every dataset they name and so read "testable now" until the requirement was declared — both actually wait on data that does not exist.
- **The graph now says what it knows, and how** (`vitiligo graph seed-evidence`): every edge carries `claim` — `asserted` when a database or registry states the relation, `observed` when a measurement was made — and an observed edge carries the rung of the causal ladder it reached. All 1,643 existing edges were seeded from Open Targets and registry listings and are labelled `asserted`, which is what they are: `methotrexate treats vitiligo` came from a registry listing a trial, not from evidence that it works. 126 new or upgraded edges rest on measurements — 103 GWAS associations with a p-value and named cohort, 21 posted trial responder rates, 2 from mechanism records at the rung their own evidence reaches. Four node types the structured seed could not express are populated from real curated content: cell types, phenotypes, pathways and trial outcomes. Provenance stays on all 1,726 edges and now travels in the graph export.
- **Trials named in papers but held by no registry we read** (`vitiligo report cited-trials`): India, China and Iran run most vitiligo trials and their registries publish no API, so those trials were invisible. Papers that report them print the registration number, and the corpus holds 2,587 full texts: scanning them recovers 34 leads (12 CTRI, 9 ChiCTR, 8 IRCT, plus Thailand, Africa and Germany), each with the paper and the sentence around it. Proximity is what makes it work — a review of cell-sheet therapies cited 16 Japanese trial numbers while mentioning vitiligo twice in passing, and all 16 are correctly dropped.
- **More trials** (`vitiligo ingest isrctn`): trial coverage was five months stale and missed a registry entirely. Refreshing ClinicalTrials.gov added 27 and CTIS 3; a new ISRCTN source added 8, among them a within-patient randomised comparison of NB-UVB against excimer laser after mini-grafting that no other registry we read carries. 344 trials to 382. ISRCTN matches the word anywhere, so 57 of its 65 hits only mention vitiligo in their exclusion criteria and are dropped. Investigator names, telephone numbers, site street addresses and emails — including those sponsors write into summary prose — are removed before storage; recruitment countries are kept.
- **Raw source payloads kept locally** (`data/raw/`, shown by `vitiligo db stats`): an ingest parsed its payload and discarded it, so it could not be reproduced or re-run while a source was down — which Europe PMC was on 2026-10-24. GWAS Catalog and NIH RePORTER now keep what they used, with URL, size, SHA-256 and time, and fall back to it when the source is unreachable (verified by simulating an outage). The GWAS cache keeps the matching rows and the release's fingerprint rather than the whole release: 0.22 MB instead of 73 MB for the same 157 rows.
- **Funded research** (`vitiligo ingest reporter`, `vitiligo report funding`, `research_projects` table): 735 NIH-funded vitiligo projects, 1985 to 2026, with investigator, institution, award and dates. Grants are kept out of `documents` on purpose — a plan is not literature, and counting it would inflate every evidence count. It answers the question the roadmap's slowest items actually wait on: who works on this today. Since FY2024, 25 vitiligo-centred projects across 10 investigators, two of them funded on precisely the questions the mechanism records ask.
- **Human genetics** (`vitiligo ingest gwas`, `genetic_associations` table): 157 vitiligo associations from 18 GWAS Catalog studies, with variant, mapped gene, p-value, effect size and cohort. Mechanism records can cite one as `gwas:<accession>`, which makes the causal ladder's `human_genetics` rung reachable for the first time. What it shows: the genome-wide significant genes are immune tolerance (PTPN22, CTLA4, CD80, IL2RA, BACH2, HLA-DRB1) and pigment biology (TYR, MC1R, IRF4). No IL-15 or JAK pathway gene is among the mapped genes, which bounds the resident-memory hypothesis without opposing it, since inherited risk speaks to who develops vitiligo rather than what maintains it. A fifth of the significant variants carry no gene mapping; checked against Ensembl coordinates none lies within 500 kb of JAK1, JAK2, JAK3, TYK2, IL15, IL15RA, IL2RB or IFNG, the nearest being 405 kb from IL2RB.
- **Full-text search** (`vitiligo embed full-text`, `vitiligo search --full-text`): PMC bodies were ingested but never searchable, so a result reported only in a paper's Results section could not be found. Bodies are now cut into overlapping passages at paragraph boundaries, one vector each in a new `document_chunks` table, and a document scores as its best passage. Passage text is not duplicated: offsets locate it in the source, and a recorded hash of that source replaces a paper's passages when its text changes. Hits carry the section and a quote.
- **Corpus refreshed** (2026-10-23): +3 GEO series (including GSE311770, 105 biopsies), +321 PubMed and +177 PMC records, re-embedded. Checking the first dataset the mechanism work needs found that **GSE203262 is not usable as deposited**: each patient's lesional and non-lesional samples are merged into one matrix with no record of which barcode suffix is which, and melanocyte markers order the two groups inconsistently across patients.
- **Simple baselines for the scenario model** (`models/baseline.py`, `scripts/model/baseline_compare.py`, `exports/model/baseline-comparison-*.json`): a pooled-rate and a placebo-anchored baseline, scored on exactly the points the leave-one-trial-out back-test scored. On the face the model beats both (4.3 pp mean error against 15.6 and 16.9); on the body the crudest baseline was slightly better (3.6 pp against 4.0). Differences are bootstrapped over trials, not points, and the subsets hold only 4-5 trials, so they are directions rather than tests. A time-course baseline was barely estimable: outside the two oral trials every control arm in the corpus reports week 24 only. Post hoc; the prospective version is to seal a baseline beside each forecast.
- **Mechanistic hypotheses** (`vitiligo mechanism list|show|verify|seal`, `curation/mechanisms.json`, [`docs/mechanisms/`](docs/mechanisms/README.md)): the layer from biological state to clinical outcome. Each record states the chain, its evidence on a causal ladder (association → human genetics → perturbation in vitro, in animals, in people), the strongest competing explanation and how to tell it apart, and what we expect if the claim is right and if it is wrong. What the supporting evidence reaches is computed, never curated, and the gate rejects a claim the corpus contradicts (a mouse study cannot carry a claim of perturbation in people), a citation that does not resolve, or a record that cannot fail. Seals cover the claim, context and test; evidence may still grow. Two records: resident memory and relapse (outcome 3, roadmap 3.6), and the follicular reservoir and repigmentation (outcome 2).
- **Research roadmap** (`docs/roadmap.md`): the order of work to mid-2027, tagged by what each step needs (public data, reviewer, biostatistician, lab, clinic), with dated external events and stop-or-continue gates. Adds a sealed resident-memory relapse signature (derived from public single-cell data, tested on later data or a 1 mm biopsy in the maintenance trial) and a repigmentation evidence map to the plan. The strategic plan's next moves now point here.
- **Ranking of pending evidence** (`forecasts/voi/ranking/`, `voi_core.py rank|rank-mc|rank-score`): pre-registered value-of-information ranking of 7 pending randomized trials, with a post-hoc check of simulation noise and a prospective test of the engine as results become public. New `predict_trial_draws` simulates a new trial with any number of arms.
- **Sealing records the code**: forecasts now carry the git commit, and sealing refuses uncommitted model code. The 2026-10-14 forecasts, sealed before their code was committed, reproduce within 1.4 points (`scripts/model/reproduce_sealed.py`).
- **Discovery loop** (`vitiligo discover run|ledger|import-forecasts`): claims tested on held-out trials under online false-discovery-rate control, recorded in a ledger.
- **Simulator trial run** (`lab/simulator/`): pre-registered; stopped after failing its locked exam.
- **Findings page** (`docs/findings.md`); the review pack now includes the JAK materials.
- **`vitiligo db repair [--apply]`**: fixes v1.0.0 corpora in place (truncated PubMed titles, GEO sample records).

### Fixed

- **Search loaded the whole corpus on every query.** Ranking applies a penalty to animal and in-vitro papers, and every document was fetched from SQLite to find out which deserved one: 736 ms of the 1,087 ms a query took. Since the penalty only lowers a score, and never by more than 0.08, anything below the k-th raw score minus that cannot overtake it; ranking that shortlist is identical to ranking everything. Queries now take 19 ms, with results verified byte-identical across six queries, and the equivalence is tested on random scores and penalties.
- **Candidate report counted evidence twice.** Every graph edge is seeded from the priors and trials the score already counts, so the graph component scored them again; a paper in both PubMed and PMC counted twice under literature. Only graph edges extracted from papers now count (none yet), and each paper counts once. Totals fell by 20–26 points. The global top 10 kept its order; three of the five per-intent tables reordered below the leaders. The report now states that it measures evidence maturity, not therapeutic potential; report and validation proposals regenerated.
- **Scenario model doc:** the back-tests helped choose the model (v0.1 fixed v0's back-test failures), so only sealed forecasts are clean tests. Now disclosed.
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
