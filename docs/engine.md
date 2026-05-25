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

# 5. Smoke-test ingestion (fetches 5 vitiligo papers from PubMed)
vitiligo ingest pubmed --limit 5

# 6. Inspect what we have
vitiligo db stats
vitiligo db sample -n 3
```

---

## Architecture

Two layers, kept deliberately small:

```
┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐
│  External sources  │ ───► │  Ingestion         │ ───► │  Document store    │
│  (PubMed, PMC,     │      │  pipeline          │      │  (SQLite via       │
│   ClinicalTrials,  │      │  + bookkeeping     │      │   SQLModel)        │
│   Open Targets…)   │      │                    │      │                    │
└────────────────────┘      └────────────────────┘      └────────────────────┘
```

### Source clients (`vitiligo.sources`)

One submodule per external source. Each client:

- Owns the source-specific protocol (REST, XML, JSON, FTP, etc.).
- Handles auth, rate limiting, retries, pagination.
- Parses raw responses into `Document` instances using a **source-agnostic schema**.
- Preserves the raw response in `Document.raw_metadata` for auditability and re-parsing.

Currently shipped:

| Module | Source | Identifier |
|---|---|---|
| `vitiligo.sources.pubmed` | NCBI PubMed via E-utilities | PMID |

Planned (in priority order):

| Source | Why | Notes |
|---|---|---|
| PMC OA | Full-text articles (~30% of vitiligo lit) | Same E-utilities, different db |
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

### CLI (`vitiligo.cli`)

Built on Typer. Commands:

```bash
vitiligo version

vitiligo db init
vitiligo db stats
vitiligo db sample -n 5

vitiligo ingest pubmed                         # full ingestion
vitiligo ingest pubmed --limit 100             # smoke test
vitiligo ingest pubmed --query 'vitiligo AND JAK'   # custom query
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

1. **PMC Open Access ingestion** — full text where available.
2. **ClinicalTrials.gov ingestion** — vitiligo trials with full metadata.
3. **Embeddings + vector store** — for semantic retrieval over abstracts and full text.
4. **Knowledge graph extraction** — entities (drugs, targets, pathways, subtypes) and relations.
5. **RAG layer + LLM reasoning** — cited Q&A over the corpus.
6. **Hypothesis generation agent** — ranked candidate reports.
7. **Web UI** — public Evidence Engine deployment.
