# Evidence Engine — Architecture

Canonical diagrams for the **software** stack (ingestion → storage → search → reasoning → web). For mission-level strategy loops and artifact maps, see the Mermaid diagrams in the [README](../README.md). For commands and module detail, see [`engine.md`](engine.md).

---

## System architecture (five layers)

The stack is five **data/processing** layers, deliberately small and swappable. **Serving** (CLI + FastAPI) is not a sixth data layer — it exposes layers 1–5. Batch jobs (`ingest`, `embed run`, `graph seed`) run on a developer machine or CI; `vitiligo serve` is read-heavy plus optional LLM POSTs.

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ External │ ─► │ Ingestion│ ─► │ Document │ ─► │ Embeddings│ ─► │ Reasoning│
│ sources  │    │ pipeline │    │ store    │    │ + semantic│    │ (RAG +   │
│ (PubMed, │    │ +        │    │ (SQLite) │    │ search    │    │ hypothesis│
│  PMC, …) │    │ bookkeep │    │          │    │ fastembed)│    │ Anthropic)│
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                     │               │                               │
                     │               │ graph seed (priors + trials)  │
                     │               │ graph extract (docs, opt. LLM)│
                     │               └───────────────────────────────┘
                     ▼
              ┌──────────────┐    ┌──────────────┐
              │ vitiligo CLI │    │ FastAPI web  │
              │ (operator)   │    │ + HTML UI    │
              └──────────────┘    └──────────────┘
```

Same stack as Mermaid (renders on GitHub):

```mermaid
flowchart TB
  subgraph L1 [1 — External sources]
    E1[PubMed / PMC / GEO]
    E2[CT.gov / EU CTR / ICTRP]
    E3[Open Targets / DrugBank]
  end

  subgraph L2 [2 — Ingestion]
    I1[vitiligo.sources.*]
    I2[vitiligo.ingest.pipeline]
  end

  subgraph L3 [3 — Document store]
    DB[(SQLite vitiligo.db)]
    T1[documents · trials · priors]
    T2[graph_entities · graph_edges]
    T3[ingestion_runs]
  end

  subgraph L3b [3b — Graph build CLI]
    G1[graph seed — priors + trials]
    G2[graph extract — optional LLM on abstracts — ANTHROPIC_API_KEY]
  end

  subgraph L4 [4 — Embeddings]
    M1[vitiligo embed run]
    M2[fastembed ONNX]
    M3[semantic_search + evidence penalties]
  end

  subgraph L5 [5 — Reasoning]
    R1[ask_with_citations]
    R2[generate_hypotheses]
    R3[build_candidate_report — no LLM]
    R4[Anthropic API]
  end

  subgraph L6 [Serving — not a data layer]
    W1[FastAPI + static UI]
    C1[vitiligo CLI]
  end

  E1 & E2 & E3 --> I1 --> I2 --> T1
  T1 --> DB
  T1 --> M1 --> M2 --> T1
  M2 --> M3
  T1 --> G1 --> T2
  T1 --> G2 --> T2
  T2 --> DB
  M3 --> R1 & R2 & R3
  T1 & T2 --> R2 & R3
  R1 & R2 --> R4
  M3 & R1 & R2 & R3 --> W1
  I2 & M1 & G1 & G2 & W1 --> C1
```

| Layer | Package | Responsibility |
|-------|---------|----------------|
| Sources | `vitiligo.sources` | Fetch and parse PubMed, PMC, registries, Open Targets, DrugBank, GEO, ICTRP |
| Ingestion | `vitiligo.ingest` | Upsert by `(source, source_id)`; `ingestion_runs` audit trail |
| Storage | `vitiligo.storage` | SQLModel schema: documents, embeddings, trials, priors, graph |
| Graph build | `vitiligo.graph` | `graph seed` (deterministic); `graph extract` (optional LLM) — **not** part of ingest |
| Embeddings | `vitiligo.embed` | `embed run` indexes documents; `semantic_search`; model `BAAI/bge-small-en-v1.5` |
| Evidence | `vitiligo.evidence` | Paper/trial tiers; score penalties in search (mouse −0.08, in vitro −0.05) |
| Reasoning | `vitiligo.reasoning` | RAG Ask and Hypothesize (requires `ANTHROPIC_API_KEY`) |
| Reports | `vitiligo.reports` | Deterministic candidate rankings (`report candidates`, `/api/report/candidates`) |
| Web | `vitiligo.web` | FastAPI JSON API + vanilla static UI |
| CLI | `vitiligo.cli` | Operator console: ingest, embed, graph, serve — same engine as the API |

Query helpers on storage (no separate layer): `vitiligo.trials`, `vitiligo.priors`, `vitiligo.graph.query`.

---

## High-level data flow

End-to-end runtime path. **Ingest does not embed documents or build the graph** — those are separate CLI steps after the corpus is loaded.

```mermaid
flowchart TB
  subgraph external [External sources]
    PubMed[PubMed / PMC / GEO]
    Registries[CT.gov / EU CTR / ICTRP]
    OT[Open Targets / DrugBank]
  end

  subgraph batch [Batch jobs — CLI / CI]
    Ingest[vitiligo ingest.*]
    EmbedRun[vitiligo embed run]
    GraphSeed[vitiligo graph seed]
    GraphExtract[vitiligo graph extract — optional, may use Anthropic]
  end

  subgraph store [SQLite — vitiligo.db]
    Docs[documents]
    EmbTbl[embeddings]
    TrialTbl[trials]
    Priors[priors]
    GraphTbl[graph_entities / edges]
  end

  subgraph index [Search index]
    Fastembed[fastembed ONNX]
    Cache[in-process embedding matrix cache]
    Search[semantic_search + vitiligo.evidence]
  end
  EmbTbl --> Cache
  Cache --> Search
  Fastembed --> Search

  subgraph reason [Reasoning]
    RAG[ask_with_citations]
    Hypo[generate_hypotheses]
    Reports[build_candidate_report]
    Claude[Anthropic API]
  end

  subgraph serve [Serving]
    CLI[vitiligo CLI]
    API[FastAPI + static HTML]
  end

  external --> Ingest
  Ingest --> Docs & TrialTbl & Priors
  Docs --> EmbedRun --> Fastembed --> EmbTbl
  Priors & TrialTbl --> GraphSeed --> GraphTbl
  Docs --> GraphExtract --> GraphTbl
  Docs --> Search
  Search --> RAG
  Search --> Hypo
  TrialTbl --> Hypo
  Priors --> Hypo
  GraphTbl --> Hypo
  Search --> Reports
  TrialTbl & Priors & GraphTbl --> Reports
  RAG --> Claude
  Hypo --> Claude
  Search & RAG & Hypo & Reports --> API
  Ingest & EmbedRun & GraphSeed & API --> CLI
```

**Operational order (typical):** `db init` → `ingest *` → `embed run` → `graph seed` → (`graph extract`) → `serve`.

**Coupling note:** `generate_hypotheses` and `build_candidate_report` both require embeddings (`semantic_search`). If the index is empty, hypothesize fails entirely; candidate reports lack literature scores.

---

## Hypothesize evidence streams

`generate_hypotheses` combines four retrieval streams, then one Claude call for structured JSON.

```mermaid
flowchart LR
  Intent[Research intent]
  Intent --> Papers[semantic_search — papers]
  Intent --> Trials[retrieve_relevant_trials — text + phase filter]
  Intent --> Graph[retrieve_graph_for_hypothesize — vitiligo edges, intent re-rank]
  EFO[Vitiligo EFO disease id] --> Priors[retrieve_priors_for_hypothesize — drugs + targets]
  Papers --> Gate{embeddings exist?}
  Gate -->|no| Fail[CorpusUnavailable]
  Gate -->|yes| LLM[Claude structured JSON]
  Trials --> LLM
  Priors --> LLM
  Graph --> LLM
  LLM --> Out[Ranked candidates]
```

Citation conventions: paper `[n]`, trial `[Tn]`, prior `[Pn]`, graph `[Gn]`.

---

## Candidate reports (deterministic)

Parallel to Hypothesize — scoring is **deterministic** (no Claude for rankings). Requires **`embed run`** like search/Hypothesize, because literature evidence uses `semantic_search`. Optional LLM narrative synthesis is available in the CLI when `ANTHROPIC_API_KEY` is set (`include_llm=True`).

```mermaid
flowchart LR
  Intents[candidate-intents.json]
  Intents --> Report[build_candidate_report]
  Report --> Score[Weighted score: priors + trials + graph + literature]
  Score --> Out[Ranked candidates + score breakdown]
```

Exposed as `vitiligo report candidates` and `GET /api/report/candidates` (web endpoint is always deterministic).

---

## Deployment and runtime

Default posture is **local-first** (`vitiligo serve` + `data/vitiligo.db`). Optional public hosting uses Docker with a persistent volume for the corpus and embedding cache. **`fly.toml` exists but Fly.io is deprecated** — see [`deploy.md`](deploy.md).

```mermaid
flowchart LR
  subgraph local [Default — local-first]
    Dev[Developer machine]
    DB[(data/vitiligo.db)]
    Dev --> DB
    Dev --> Serve[vitiligo serve :8765]
  end

  subgraph optional [Optional public hosting]
    Docker[Dockerfile + uvicorn]
    Vol[Persistent volume — DB + fastembed cache]
    Render[Render blueprint]
    DO[DigitalOcean — planned]
  end

  Docker --> Vol
  Render --> Docker
  DO -.-> Docker
```

---

## Web API surface

| Method | Path | LLM required |
|--------|------|----------------|
| GET | `/`, `/privacy`, `/terms` | No |
| GET | `/api/health`, `/api/stats` | No |
| POST | `/api/search` | No |
| POST | `/api/ask` | Yes |
| POST | `/api/hypothesize` | Yes |
| GET | `/api/report/candidates` | No |
| POST | `/api/trials/search` | No |
| GET | `/api/trials/stats` | No |
| GET | `/api/graph/stats` | No |
| GET | `/api/graph/search` | No |
| GET | `/api/graph/neighbors` | No |
| GET | `/api/graph/export` | No |

POST routes under `/api/*` are rate-limited per IP in production (`VITILIGO_RATE_LIMIT_POST_PER_MINUTE`).

---

## Related docs

- [`engine.md`](engine.md) — quickstart, source modules, CLI reference
- [`deploy.md`](deploy.md) — hosting posture and env vars
- [README](../README.md) — mission, strategic logic, artifact map (non-software diagrams)
