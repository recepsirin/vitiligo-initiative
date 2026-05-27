# Changelog

All notable changes to the Vitiligo Initiative Evidence Engine are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [SemVer](https://semver.org/).

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
