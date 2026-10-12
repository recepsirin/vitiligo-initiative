# Changelog

All notable changes to the Vitiligo Initiative Evidence Engine are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- **JAK inhibitor evidence atlas** — `vitiligo report jak` builds an open dataset of every vitiligo trial testing a JAK-family inhibitor (names, brands, development codes), with cross-registry study linking (CT.gov ↔ CTIS), verbatim ClinicalTrials.gov posted outcomes and adverse-event counts, registry-linked publications, and Open Targets stage/mechanisms. Outputs JSON, Markdown, and CSV.

### Fixed

- **Hypothesize trial evidence** — `retrieve_relevant_trials` matched a multi-word intent as one literal phrase, so natural-language intents returned no trials. Intents are now tokenized; tokens match at word starts ("active" no longer matches "inactive"), weighted by rarity (smoothed IDF) and by field (titles, conditions, keywords, intervention names count fully; summary prose counts half).
- **Approved drugs dropped from Hypothesize priors** — drug priors were sorted by clinical-stage *text*, so `APPROVAL` sorted last and was cut by the limit (e.g. ruxolitinib). Stages now sort by ordinal rank, and the drug filter is Phase 2+ as documented.
- **Candidate report trial scoring** — registry phases (`PHASE3`) never matched the rubric's labels (`PHASE_3`), so the Phase 2+ trial bonus never applied and trial-derived stages were always unknown. Phase 1/2 and 2/3 trials now map to `PHASE_1_2` (credited as Phase 1) / `PHASE_2_3`.
- **Candidate report stage downgrade** — a salt-form prior (e.g. `RITLECITINIB TOSYLATE`, Phase 2) could overwrite its parent drug (Phase 3); the most advanced stage is now kept.
- **Candidate report speed** — literature retrieval runs once per intent instead of once per drug × intent (~92 s → ~4 s on the full corpus).

### Changed

- **Candidate report trial component** — scores the best trial evidence instead of summing per trial: top phase (Phase 3/4: 15, Phase 2 or 2/3: 10, earlier: 3), posted results (Phase 2+: 10, other: 5), an active trial (5), breadth (+1 per extra trial, max 5). Still 0–35; previously most top candidates hit the cap. `docs/candidate-report-v1.md` is regenerated and the validation proposals' rank/score references updated (upadacitinib #2 → 101; povorcitinib #4 → #3, 91), with their broken links to the report fixed.

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
