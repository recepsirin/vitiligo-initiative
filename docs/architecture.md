# Architecture

How the software fits together. Commands are in [`engine.md`](engine.md); hosting is in [`deploy.md`](deploy.md).

## Data flow

```mermaid
flowchart TB
  subgraph sources [Public sources]
    S1[PubMed · PMC · GEO]
    S2[ClinicalTrials.gov · EU CTR · WHO ICTRP]
    S3[Open Targets · DrugBank]
  end

  DB[(SQLite corpus<br/>documents · trials · priors · graph · embeddings)]

  subgraph engine [Evidence Engine]
    SEARCH[Semantic search + evidence levels]
    GRAPH[Knowledge graph]
    REASON[Ask · Hypothesize<br/>Anthropic API]
    CAND[Candidate report]
  end

  subgraph jak [JAK evidence]
    ATLAS[Atlas · arm table]
    MODEL[Scenario model<br/>PyMC]
    LOOP[Discovery loop · forecasts]
    LEDGER[(Ledger SQLite)]
  end

  sources -->|vitiligo ingest| DB
  DB -->|embed run · graph seed| SEARCH & GRAPH
  SEARCH & GRAPH --> REASON & CAND
  DB --> ATLAS --> MODEL --> LOOP --> LEDGER
  SEARCH & REASON & CAND --> UI[FastAPI web UI · CLI]
```

Typical order: `db init` → `ingest …` → `embed run` → `graph seed` → `serve`. Ingest does not embed or build the graph; those are separate steps. The LLM is optional and powers only Ask, Hypothesize and graph extraction. Everything else is deterministic.

## Modules

| Package | Responsibility |
|---|---|
| `vitiligo.sources` | Fetch and parse each public source into a source-agnostic schema; raw responses kept in `raw_metadata` |
| `vitiligo.ingest` | Idempotent upserts by `(source, source_id)`; `ingestion_runs` audit trail; `db repair` |
| `vitiligo.storage` | SQLModel schema: documents, embeddings, trials, priors, graph |
| `vitiligo.embed` | fastembed ONNX embeddings (`BAAI/bge-small-en-v1.5`), brute-force cosine search. Two indexes: one vector per document over title and abstract, and one per passage of a paper's body (`chunking.py`, `full_text.py`), where a document scores as its best passage |
| `vitiligo.evidence` | Evidence levels for papers and trials; search down-ranks mouse (−0.08) and in-vitro (−0.05) studies |
| `vitiligo.graph` | `graph seed` from priors and trials (deterministic); `graph extract` from abstracts (optional LLM) |
| `vitiligo.trials`, `vitiligo.priors` | Query helpers over the store |
| `vitiligo.reasoning` | Ask (RAG with citations) and Hypothesize (four evidence streams) |
| `vitiligo.reports` | Candidate report (deterministic); JAK atlas (`jak.py`); harmonized arm table (`jak_arms.py`); curated paper results (`paper_results.py`) |
| `vitiligo.models` | Scenario model (`jak_mbma.py`); needs the `[model]` extra |
| `vitiligo.mechanisms` | Mechanistic hypothesis records (`curation/mechanisms.json`): the chain, the causal ladder, and the gate (`verify.py`) |
| `vitiligo.discovery` | e-values and e-LOND (`evidence.py`), ledger, policy, loop, forecasts of unreported trials |
| `vitiligo.web` | FastAPI app, static UI, rate limiting, LLM budget, proxy headers |
| `vitiligo.cli` | Typer CLI over all of the above |

## Hypothesize

Four retrieval streams feed one Claude call that returns structured JSON. Citations are kept separate: paper `[n]`, trial `[Tn]`, prior `[Pn]`, graph `[Gn]`. Without embeddings, Hypothesize fails with `CorpusUnavailable`, and candidate reports lose their literature scores.

```mermaid
flowchart LR
  Intent --> Papers[semantic_search]
  Intent --> Trials[retrieve_relevant_trials]
  Intent --> Graph[graph edges, re-ranked by intent]
  EFO[EFO_0004208] --> Priors[drug + target priors]
  Papers & Trials & Graph & Priors --> LLM[Claude] --> Out[Ranked candidates]
```

## Web API

| Method | Path | LLM |
|---|---|---|
| GET | `/`, `/privacy`, `/terms` | — |
| GET | `/api/health`, `/api/stats` | — |
| POST | `/api/search` | — |
| POST | `/api/ask`, `/api/hypothesize` | Yes |
| GET | `/api/report/candidates` (cached until the corpus changes) | — |
| POST | `/api/trials/search` | — |
| GET | `/api/trials/stats` | — |
| GET | `/api/graph/stats`, `/api/graph/search`, `/api/graph/neighbors`, `/api/graph/export` | — |

POST routes are rate-limited per client. Ask and Hypothesize also draw on a global LLM budget ([`deploy.md`](deploy.md)).
