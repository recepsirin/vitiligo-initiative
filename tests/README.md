# Test suite

## Layout

| Directory | Role |
|-----------|------|
| `unit/` | Pure logic, parsers, reasoning stubs, manifest validation |
| `unit/parsers/` | Offline parser fixtures |
| `integration/` | Seeded temp SQLite, ingestion roundtrip |
| `api/` | FastAPI routes, validation, rate limits |
| `confidence/` | Curated regression scenarios (CI quality gate) |
| `corpus/` | Full local `data/vitiligo.db` only |
| `smoke/` | Thin end-to-end over full corpus |
| `fixtures/` | Shared JSON/XML samples and regression corpus inputs |
| `helpers/` | Shared paths (`tests.helpers.paths`) |

Property-based checks live in `unit/test_properties_normalize.py` and
`integration/test_properties_trials.py` (Hypothesis).

HTTP confidence: `confidence/test_confidence_api.py` (`POST /api/search`, `POST /api/trials/search`).

Graph API confidence: `confidence/test_confidence_graph_api.py` (`GET /api/graph/*` on regression corpus).

Direct and API retrieval share assertions via `tests/helpers/retrieval_expectations.py`.

Semantic search applies a small evidence-level penalty (mouse/in-vitro) after cosine similarity.

## Advisor → manifest workflow

```bash
./scripts/review/run-eval-retrieval.sh -o exports/retrieval-eval.json
# Label advisor_relevance (1-5) on each promoted hit in the export JSON.
python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json        # dry-run
python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json --apply          # add new
python scripts/review/promote-eval-to-manifest.py exports/retrieval-eval.json --update --apply # refresh existing
python scripts/test/build_regression_db.py
pytest -m confidence
```

## Pyramid

| Marker | What it proves | Where it runs |
|--------|----------------|---------------|
| *(none)* | Pure logic, parsers, API validation | CI |
| `integration` | Real SQLite on seeded temp data | CI |
| `confidence` | **Right papers, trials, graph API, Ask citations** for curated queries | CI + local |
| `model` | Scenario-model fits (needs the `[model]` extra; skipped without PyMC/SciPy) | Local |
| `corpus` | Full `data/vitiligo.db` (candidate rankings, ICTRP, retrieval guards) | Local only |
| `smoke` | Thin end-to-end over full corpus | Local release audit |

## Commands

```bash
# CI-equivalent (fast; matches .github/workflows/ci.yml)
pytest -m "not corpus and not smoke and not confidence"
ruff check src tests && ruff format --check src tests

# Confidence regression (builds minimal corpus if needed)
python scripts/test/build_regression_db.py
pytest -m confidence

# Full local release gate
./scripts/audit/smoke-all.sh
```

## Confidence tests

**These are the quality gate.** They read `tests/fixtures/regression_expectations.json` and assert:

- Known PMIDs appear in semantic search top-K for expert queries
- Known NCT/EUCTR trials are findable (including intervention-only regression)
- Clinical queries do not rank animal models at the top

Fixtures live in `tests/fixtures/regression/`:

- `documents.json`, `trials.json` — papers and registry rows
- `priors.json`, `graph.json` — seed data for candidate ranking in CI
- `regression_expectations.json` — expected outcomes (one retrieval case per `docs/eval-queries.json` query)

Rebuild the SQLite corpus after changing fixtures:

```bash
python scripts/test/build_regression_db.py
```

Candidate ranking confidence runs in CI on the regression corpus (`test_confidence_regression.py`).
Graph density checks still require the full local corpus (`test_confidence_corpus.py`).

## Adding a regression case

1. Fix a bug or get advisor validation on a query
2. Add the case to `regression_expectations.json` (`retrieval`, `trials`, `ask`, `graph`, …) with `eval_query_id` when tied to `docs/eval-queries.json`
3. If new papers/trials are needed, add rows to `tests/fixtures/regression/*.json`
4. Rebuild: `python scripts/test/build_regression_db.py`
5. Run: `pytest -m confidence`

Every production bug in search/trials/graph API should add a confidence case. Ask cases should reuse PMIDs already proven in matching `retrieval` rows.
