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

# 7. Inspect what we have
vitiligo db stats
vitiligo embed stats
vitiligo db sample -n 3
```

For smoke testing, every ingest command supports `--limit N`.

---

## Architecture

Three layers, kept deliberately small:

```
┌────────────────┐    ┌────────────────┐    ┌────────────────┐    ┌─────────────┐
│ External       │ ─► │ Ingestion      │ ─► │ Document       │ ─► │ Embeddings  │
│ sources        │    │ pipeline       │    │ store          │    │ + semantic  │
│ (PubMed, PMC,  │    │ + bookkeeping  │    │ (SQLite via    │    │ search      │
│  CT.gov, OT…)  │    │                │    │  SQLModel)     │    │ (fastembed) │
└────────────────┘    └────────────────┘    └────────────────┘    └─────────────┘
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

1. **ClinicalTrials.gov ingestion** — vitiligo trials with full metadata.
2. **Open Targets + DrugBank ingestion** — drugs, targets, pathways for repurposing analysis.
3. **Full-text embedding scope** — embed PMC body sections, not just title + abstract.
4. **Hybrid retrieval** — combine BM25 over MeSH/keywords with semantic vectors.
5. **Knowledge graph extraction** — entities (drugs, targets, pathways, subtypes) and relations, LLM-assisted.
6. **RAG with citations + evidence levels** — the Evidence Engine answer layer.
7. **Hypothesis generation agent** — ranked candidate reports for spread arrest and repigmentation.
8. **Web UI** — public Evidence Engine deployment.
