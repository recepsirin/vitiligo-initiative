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
```

For smoke testing, every ingest command supports `--limit N`.

---

## Architecture

Five layers, all deliberately small and swappable:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ External │ ─► │ Ingestion│ ─► │ Document │ ─► │ Embeddings│ ─► │ Reasoning│
│ sources  │    │ pipeline │    │ store    │    │ + semantic│    │ (RAG +   │
│ (PubMed, │    │ +        │    │ (SQLite) │    │ search    │    │ hypothesis│
│  PMC, …) │    │ bookkeep │    │          │    │ fastembed)│    │ Anthropic)│
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                      │
                                                                      ▼
                                                              ┌──────────────┐
                                                              │ FastAPI web  │
                                                              │ + HTML UI    │
                                                              └──────────────┘
```

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

Planned (in priority order):

| Source | Why | Notes |
|---|---|---|
| ClinicalTrials.gov | Trial designs, endpoints, outcomes | REST v2 API |
| Open Targets | Disease–gene–drug associations | GraphQL |
| DrugBank (open subset) | Drug mechanisms, repurposing | XML download |
| GEO / ArrayExpress | Public omics datasets | E-utilities + REST |

### Storage (`vitiligo.storage`)

- One canonical `documents` table, keyed by `(source, source_id)`.
- Common normalized fields (title, abstract, year, doi, mesh_terms, etc.).
- `raw_metadata` JSON field preserves source-specific data.
- `ingestion_runs` table tracks every fetch: source, query, counts, status, errors.

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
- `generate_hypotheses(intent)` — retrieves a wider net of papers and asks Claude to extract ranked therapeutic candidates (drugs / combinations / targets / mechanisms / biomarkers) with mechanism, rationale, evidence strength, risks, and citations. Returns structured JSON the UI consumes directly.

Both default to `claude-sonnet-4-5` via the `anthropic` SDK. The model is configurable via `ANTHROPIC_MODEL`. If `ANTHROPIC_API_KEY` is not set, the calls raise `LLMUnavailable` with a clear message — no silent degraded mode. Search itself works without an API key.

### Web service (`vitiligo.web`)

A small FastAPI app exposing four endpoints plus a static HTML UI:

| Method | Path | What |
|---|---|---|
| GET | `/` | Evidence Engine UI (single HTML page) |
| GET | `/api/health` | `{status, version}` |
| POST | `/api/search` | Semantic search results |
| POST | `/api/ask` | RAG with citations (requires `ANTHROPIC_API_KEY`) |
| POST | `/api/hypothesize` | Ranked candidates (requires `ANTHROPIC_API_KEY`) |

The UI is intentionally a single static HTML file with vanilla CSS/JS — no build step, no framework, fast to iterate on, easy to deploy. CORS is open by default; this is a research tool, run it locally or behind your own auth.

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

# Embeddings
vitiligo embed run                                  # encode every unembedded document
vitiligo embed stats                                # coverage by model + scope

# Semantic search
vitiligo search "IFN-gamma CXCL10 axis in vitiligo" --top-k 10 --show-abstract

# Reasoning (requires ANTHROPIC_API_KEY)
vitiligo ask "What is the evidence for ruxolitinib + NB-UVB combinations?" -k 8
vitiligo hypothesize "stop spread of active non-segmental vitiligo" -k 25

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
5. Add parser tests in `tests/test_<name>_parser.py` (offline, using a
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

1. **ClinicalTrials.gov + EU CTR + WHO ICTRP ingestion** — vitiligo trials with structured endpoints, outcomes, eligibility (EU-aware from day one).
2. **Open Targets + DrugBank ingestion** — drugs, targets, pathways for repurposing analysis.
3. **Full-text embedding scope** — embed PMC body sections, not just title + abstract; chunked retrieval.
4. **Hybrid retrieval** — BM25 over MeSH/keywords combined with semantic vectors; reranker layer.
5. **Knowledge graph extraction** — LLM-assisted entities + relations across the corpus, persisted as a queryable graph.
6. **Better citation discipline** — evidence-level tagging per source (RCT / cohort / case series / mouse / review), surfaced in answers.
7. **Hypothesis-generation v2** — uses structured drug/target priors from Open Targets + trial outcomes, not just literature.
8. **Public deployment** — host the Evidence Engine somewhere reachable (Fly.io / Render) with rate limiting + telemetry.
9. **Authentication + tiered access** — public free read, controlled access for downloadable datasets.
