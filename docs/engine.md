# Engine — Developer Guide

This document covers the engineering side of the initiative: how the
ingestion pipeline is built, how to run it locally, and how to add new
data sources. For mission and strategy, see the [README](../README.md).

---

## Quickstart

```bash
# 1. Create a virtualenv (Python 3.11+)
python3.13 -m venv .venv
source .venv/bin/activate

# 2. Install the package + dev tools
pip install -e ".[dev]"

# 3. (Optional but recommended) configure NCBI identity
cp .env.example .env
# Edit .env and set NCBI_EMAIL (and optionally NCBI_API_KEY)

# 4. Initialize the local SQLite store
vitiligo db init

# 5. Ingest the full vitiligo corpus
vitiligo ingest pubmed             # ~11,000 papers (abstracts + metadata)
vitiligo ingest pmc                # ~2,500 Open Access articles (full text)
vitiligo ingest ctgov              # ~320 vitiligo trials from ClinicalTrials.gov
vitiligo ingest euctr              # ~22 EU vitiligo trials from EU CTR (CTIS)
vitiligo ingest opentargets        # ~37 drugs + 200 targets for vitiligo (EFO_0004208)
vitiligo ingest geo                # ~311 vitiligo-linked GEO series (GSE metadata)
vitiligo ingest ictrp --file export.xml   # WHO ICTRP XML export (see trialsearch.who.int)
vitiligo ingest drugbank --file full_database.xml   # DrugBank academic XML export

# 6. Embed the corpus and run semantic search
vitiligo embed run                 # ~10-20 min on CPU; fastembed downloads model on first run
vitiligo search "JAK inhibitors and repigmentation in segmental vitiligo" --show-abstract

# 7. (Optional) configure the LLM for ask/hypothesize
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
vitiligo ask "What is the evidence for combining ruxolitinib with NB-UVB?"
vitiligo hypothesize "stop spread of active non-segmental vitiligo"

# 8. Run the Evidence Engine web UI
vitiligo serve   # open http://127.0.0.1:8765

# 9. Inspect what we have
vitiligo db stats
vitiligo embed stats
vitiligo db sample -n 3
vitiligo trials stats
vitiligo trials search --status RECRUITING --phase PHASE2
vitiligo priors stats
vitiligo priors sample --kind drug -l 5

# 10. Release gate + advisor pack (local-first v1.0.0)
./scripts/audit/smoke-all.sh
./scripts/review/kol-share-pack.sh          # exports/kol-share-YYYYMMDD.tar.gz
vitiligo serve &
./scripts/deploy/verify-local.sh
```

For smoke testing, every ingest command supports `--limit N`.

**GitHub releases:** push an annotated `v*` tag (see [`.github/workflows/release.yml`](../.github/workflows/release.yml)) or `./scripts/release/create-github-release.sh vX.Y.Z`.

---

## Architecture

Five layers, all deliberately small and swappable. **Diagrams (Mermaid):** [`architecture.md`](architecture.md) — high-level data flow, layer stack, hypothesize streams, deployment.

### Source clients (`vitiligo.sources`)

One submodule per external source. Each client:

- Owns the source-specific protocol (REST, XML, JSON, FTP, etc.).
- Handles auth, rate limiting, retries, pagination.
- Parses raw responses into `Document` instances using a **source-agnostic schema**.
- Preserves the raw response in `Document.raw_metadata` for auditability and re-parsing.

Currently shipped:

| Module | Source | Identifier | Notes |
|---|---|---|---|
| `vitiligo.sources.pubmed` | NCBI PubMed via E-utilities | PMID | Auto-splits queries by year when total > 9,999 (NCBI hard cap) |
| `vitiligo.sources.pmc` | PubMed Central Open Access | PMCID | JATS XML → structured sections (intro / methods / results / discussion) |
| `vitiligo.sources.geo` | NCBI GEO DataSets (`db=gds`) | GSE accession | Series metadata via esearch + esummary (title, summary, organism, sample count) |
| `vitiligo.sources.ctgov` | ClinicalTrials.gov v2 REST API | NCT id | JSON; status, phase, conditions, interventions, sponsors, locations, eligibility, outcomes |
| `vitiligo.sources.euctr` | EU CTR (CTIS) public JSON API (EMA) | EU CT number | Search + retrieve; phases normalized into the canonical PHASE1..PHASE4 set; eligibility + objective parsed from nested protocol structure |
| `vitiligo.sources.opentargets` | Open Targets Platform GraphQL v4 | ChEMBL id (drugs) / Ensembl id (targets) | Disease resolution + drug candidates + associated targets; mechanism-of-action enrichment per drug |
| `vitiligo.sources.ictrp` | WHO ICTRP search portal (XML export) | ICTRP TrialID | File import from https://trialsearch.who.int/; skips ctgov/euctr duplicates |
| `vitiligo.sources.drugbank` | DrugBank full database (XML export) | DB id | File import from academic download; vitiligo text filter + Open Targets name seeding |

Planned (in priority order):

| Source | Why | Notes |
|---|---|---|
| GEO / ArrayExpress | Public omics datasets | E-utilities + REST |

### Storage (`vitiligo.storage`)

- `documents` table for papers and any other text-centric records, keyed by `(source, source_id)`.
- `embeddings` table mapping `(document_id, model, scope)` → L2-normalized vector bytes.
- `trials` table for clinical-trial registry records — separate from `documents` because their structure is operational (status / phase / locations / eligibility) rather than narrative. Keyed by `(source, source_id)` where source is `ctgov | euctr | ictrp`.
- `priors` table for drug and target priors (Open Targets + DrugBank). Keyed by `(source, kind, source_id, disease_id)`.
- `raw_metadata` JSON field on `documents`, `trials`, and `priors` preserves source-specific data, so we can re-derive structured fields without re-fetching.
- `ingestion_runs` table tracks every fetch (papers and trials alike): source, query, counts, status, errors.

Why SQLite for now: zero ops, single file, fast for read-heavy analytics
at this scale (millions of rows is fine). Move to Postgres / DuckDB when
we have a reason — not before.

### Ingestion pipeline (`vitiligo.ingest`)

- Orchestrates source → upsert → bookkeeping.
- Upserts by `(source, source_id)` so re-runs are idempotent.
- Records every run in `ingestion_runs` for auditability and resume.
- Commits in batches (default every 100 records) so a Ctrl-C doesn't lose work.

### Embeddings + search (`vitiligo.embed`)

- Wraps [fastembed](https://github.com/qdrant/fastembed) (ONNX runtime, no torch dependency).
- Default model: `BAAI/bge-small-en-v1.5` (384 dims, ~80 MB, strong general-purpose).
- Vectors are L2-normalized at write time, so cosine reduces to a dot product.
- Stored as `bytes` blobs in the `embeddings` table, keyed by `(document_id, model, scope)`.
- `scope` lets us embed multiple views of the same document (e.g. `title_abstract`, `full_text`, `section:methods`) and pick the right one at query time.

Brute-force cosine search is fine at this scale (a single matmul over <100k vectors). We move to a proper ANN index only when we outgrow it.

### Reasoning layer (`vitiligo.reasoning`)

Two LLM-backed pipelines built on top of search:

- `ask_with_citations(question)` — RAG: retrieves the top-K papers and asks Claude to answer using only those, with bracketed numeric citations and explicit "evidence insufficient" handling.
- `generate_hypotheses(intent)` — retrieves papers, relevant trials, Open Targets priors, and vitiligo-connected knowledge-graph edges, then asks Claude to extract ranked therapeutic candidates (drugs / combinations / targets / mechanisms / biomarkers) with mechanism, rationale, evidence strength, risks, and four citation streams: paper `[n]`, trial `[Tn]`, prior `[Pn]`, graph `[Gn]`. Returns structured JSON the UI consumes directly.

Both default to `claude-sonnet-4-5` via the `anthropic` SDK. The model is configurable via `ANTHROPIC_MODEL`. If `ANTHROPIC_API_KEY` is not set, the calls raise `LLMUnavailable` with a clear message — no silent degraded mode. Search itself works without an API key.

### Evidence levels (`vitiligo.evidence`)

Each retrieved paper and trial is tagged with an evidence tier derived from existing metadata (no re-ingestion):

- **Papers** — PubMed `publication_types`, MeSH terms, and title/abstract cues → RCT, meta-analysis, systematic review, cohort, case report, mouse/animal, in vitro, etc.
- **Trials** — registry `study_type` → clinical trial vs cohort/observational.

Tags surface in semantic search, Ask/Hypothesize prompts, API responses, and the web UI.

### Knowledge graph (`vitiligo.graph`)

A persisted entity–relation graph for vitiligo, grounded in structured sources first and optionally enriched by LLM extraction:

- **Entities** — drugs, targets, diseases, trials, interventions, pathways, mechanisms, biomarkers (`graph_entities` table).
- **Edges** — directed relations (`treats`, `targets`, `inhibits`, `activates`, `associated_with`, `tested_in`, `investigates`) with confidence scores and provenance (`graph_edges` table).
- **Seeding** — `vitiligo graph seed` builds the graph deterministically from Open Targets priors and clinical trials (no hallucination risk).
- **LLM extraction** — `vitiligo graph extract` parses paper abstracts into entities/relations; progress tracked in `graph_extractions`.
- **Query** — search entities, traverse neighbors, retrieve vitiligo-connected edges for Hypothesize.

On the local corpus (May 2026): **1,044 entities**, **1,643 edges** after structured seed.

### Web service (`vitiligo.web`)

A small FastAPI app exposing JSON endpoints plus a static HTML UI:

| Method | Path | What |
|---|---|---|
| GET | `/` | Evidence Engine UI (single HTML page) |
| GET | `/api/health` | Readiness + corpus counts + LLM configured |
| GET | `/api/stats` | Corpus and trial breakdown for monitoring |
| POST | `/api/search` | Semantic search results (`score` = evidence-adjusted cosine; mouse −0.08, in-vitro −0.05) |
| POST | `/api/ask` | RAG with citations (requires `ANTHROPIC_API_KEY`) |
| POST | `/api/hypothesize` | Ranked candidates (requires `ANTHROPIC_API_KEY`) |
| POST | `/api/trials/search` | Structured trial search |
| GET | `/api/trials/stats` | Trial registry breakdown |
| GET | `/api/graph/stats` | Knowledge graph breakdown |
| GET | `/api/graph/search?q=` | Entity search |
| GET | `/api/graph/neighbors?name=` | Adjacent edges |

The UI includes a **Graph** tab for entity search and neighbor browsing (spot-checking the knowledge graph without the CLI).

Production deployment: see [`deploy.md`](deploy.md) and [`architecture.md`](architecture.md#deployment-and-runtime) (Docker, rate limiting, persistent volume for `vitiligo.db`).

The UI is intentionally a single static HTML file with vanilla CSS/JS — no build step, no framework, fast to iterate on, easy to deploy. CORS is open by default; POST endpoints are rate-limited per IP in production.

### CLI (`vitiligo.cli`)

Built on Typer. Commands:

```bash
vitiligo version

# Storage
vitiligo db init
vitiligo db stats
vitiligo db sample -n 5

# Ingestion
vitiligo ingest pubmed                              # full ingestion
vitiligo ingest pubmed --limit 100                  # smoke test
vitiligo ingest pubmed --query 'vitiligo AND JAK'   # custom query
vitiligo ingest pmc                                 # PMC Open Access full text
vitiligo ingest geo                                 # NCBI GEO series metadata (GSE)
vitiligo ingest opentargets                         # Open Targets drug + target priors
vitiligo ingest ictrp --file export.xml              # WHO ICTRP XML export
vitiligo ingest drugbank --file full_database.xml    # DrugBank academic XML (.zip ok)
vitiligo ingest opentargets --target-limit 50       # smoke test (fewer targets)

# Embeddings
vitiligo embed run                                  # encode every unembedded document
vitiligo embed stats                                # coverage by model + scope

# Semantic search
vitiligo search "IFN-gamma CXCL10 axis in vitiligo" --top-k 10 --show-abstract

# Reasoning (requires ANTHROPIC_API_KEY)
vitiligo ask "What is the evidence for ruxolitinib + NB-UVB combinations?" -k 8
vitiligo hypothesize "stop spread of active non-segmental vitiligo" -k 25

# Priors (Open Targets)
vitiligo priors stats
vitiligo priors sample --kind target -l 10

# Knowledge graph
vitiligo graph seed                                  # deterministic seed from priors + trials
vitiligo graph extract --limit 50                    # LLM extraction (requires API key)
vitiligo graph build --extract --extract-limit 50    # seed + extract
vitiligo graph stats
vitiligo graph export -o exports/graph-review.json    # JSON for expert spot-check
vitiligo graph search ruxolitinib
vitiligo graph neighbors vitiligo

# Web UI (Evidence Engine)
vitiligo serve                                      # http://127.0.0.1:8765
vitiligo serve --host 0.0.0.0 --port 8080           # bind to all interfaces
```

---

## Adding a new source

1. Create `src/vitiligo/sources/<name>.py` with:
   - A client class (with rate limiting + retries).
   - A parser that yields `Document` instances.
2. Add the source value to `SourceKind` in `vitiligo.storage.models`.
3. Add a pipeline function in `vitiligo.ingest.pipeline` modeled on
   `run_pubmed_ingestion`.
4. Add a CLI subcommand under `vitiligo ingest`.
5. Add parser tests in `tests/unit/parsers/test_<name>_parser.py` (offline, using a
   captured sample response).

Keep new source clients **independent**: they should not import each
other or share state beyond `storage` and `config`.

---

## Operational notes

### NCBI rate limits
- 3 requests/sec without an API key, 10/sec with one.
- The client respects whichever applies, with a safety margin.
- Get a free key at https://www.ncbi.nlm.nih.gov/account/ and set
  `NCBI_API_KEY` in `.env`.
- NCBI requires `tool` and `email` parameters on programmatic requests.
  Set `NCBI_EMAIL` in `.env`.

### Storage location
- Default: `data/vitiligo.db` (gitignored).
- Override with `VITILIGO_DB_PATH` in `.env`.

### Logs
- Structured via `rich`. Override level with `LOG_LEVEL` or `--log-level`.

---

## What's next on the engine side

In rough priority order:

1. **Public deploy** — `fly deploy` with corpus volume (see [`deploy.md`](deploy.md)).
2. **Knowledge graph LLM enrichment** — run `vitiligo graph extract` on the full abstract corpus; expert spot-check.
3. **Better citation discipline** — evidence-level tagging per source (RCT / cohort / case series / mouse / review), surfaced in answers.
4. **Full-text embedding scope** — embed PMC body sections, not just title + abstract; chunked retrieval.
5. **Hybrid retrieval** — BM25 over MeSH/keywords combined with semantic vectors; reranker layer.
6. **Authentication + tiered access** — public free read, controlled access for downloadable datasets.
