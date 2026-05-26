# Test suite

## Pyramid

| Marker | What it proves | Where it runs |
|--------|----------------|---------------|
| *(none)* | Pure logic, parsers, API validation | CI |
| `integration` | Real SQLite on seeded temp data | CI |
| `confidence` | **Right papers and trials** for curated queries | CI + local |
| `corpus` | Full `data/vitiligo.db` (candidate rankings, ICTRP) | Local only |
| `smoke` | Thin end-to-end over full corpus | Local release audit |

## Commands

```bash
# CI-equivalent (fast)
pytest -m "not corpus and not smoke and not confidence"

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

Fixtures live in `tests/fixtures/regression/documents.json` and `trials.json`.  
Rebuild the SQLite corpus after changing fixtures:

```bash
python scripts/test/build_regression_db.py
```

Candidate ranking confidence (`test_confidence_corpus.py`) still requires the full local corpus because it needs priors, graph, and trial breadth.

## Adding a regression case

1. Fix a bug or get advisor validation on a query
2. Add the case to `regression_expectations.json` with `must_include_source_ids`
3. If new papers/trials are needed, add rows to `tests/fixtures/regression/*.json`
4. Rebuild: `python scripts/test/build_regression_db.py`
5. Run: `pytest -m confidence`

Every production bug in search/trials should add a confidence case.
