# Changelog

All notable changes to the Vitiligo Initiative Evidence Engine are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows [SemVer](https://semver.org/).

## [1.0.0] — 2026-05-26 (pending public deploy)

First public release of the open vitiligo Evidence Engine.

### Added

- **Corpus ingestion** — PubMed, PMC Open Access, GEO DataSets, ClinicalTrials.gov, EU CTR (CTIS), Open Targets, WHO ICTRP (XML), DrugBank (XML)
- **Document store** — SQLite with resumable ingestion runs; ~14,245 documents and ~14,242 embeddings locally
- **Semantic search** — fastembed `BAAI/bge-small-en-v1.5`, evidence-level tagging
- **Clinical trials search** — cross-registry filter (source, status, phase, country, results)
- **RAG Ask** — cited answers over retrieved papers (Anthropic Claude)
- **Hypothesize** — four evidence streams: papers `[n]`, trials `[Tn]`, priors `[Pn]`, graph `[Gn]`
- **Knowledge graph v1** — deterministic seed from priors + trials; CLI + API + Graph tab
- **Web UI** — Search, Ask, Hypothesize, Graph, Trials; beta badge and medical disclaimers
- **Legal pages** — `/privacy`, `/terms`
- **Deploy tooling** — Fly.io (`ams`), Docker, `fly-deploy-all.sh`, `verify-public.sh`, `verify-local.sh`
- **Review tooling** — graph spot-check, KOL share pack, 20-query retrieval evaluation set
- **Planning docs** — scientific brief, governance brief, KOL prep, methods preprint outline, advisor outreach
- **CI** — GitHub Actions (pytest + ruff)

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

- LLM features require server-side `ANTHROPIC_API_KEY`
- PMC full-text chunk embeddings not yet shipped
- No hybrid BM25 + vector retrieval
- Graph v1 is structured seed; full-corpus LLM extraction optional and not default
- Privacy/Terms and contact emails are drafts pending legal review

[1.0.0]: https://github.com/recepsirin/vitiligo-initiative/releases/tag/v1.0.0
