# Engine: developer guide

Setup, every CLI command, and how to add a data source. Module layout and the web API are in [`architecture.md`](architecture.md).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -e ".[dev]"                                  # ".[dev,model]" for the scenario model
cp .env.example .env                                     # NCBI_EMAIL; optional NCBI_API_KEY
vitiligo db init
```

Every ingest command accepts `--limit N` for smoke tests. `./scripts/ingest/sync-engine.sh` runs the full ingest.

## CLI reference

```bash
# Storage
vitiligo db stats   # documents, other stores, and what is cached on disk
vitiligo db sample -n 5
vitiligo db repair [--apply]                  # fix truncated titles and GEO non-series rows; then: embed run

# Ingestion (approximate sizes, May 2026)
vitiligo ingest pubmed                        # ~11,000 abstracts; --query to customize
vitiligo ingest pmc                           # ~2,600 open-access full texts
vitiligo ingest geo                           # ~50 GEO series (GSE metadata)
vitiligo ingest ctgov                         # ~347 ClinicalTrials.gov trials
vitiligo ingest euctr                         # ~25 EU CTR (CTIS) trials
vitiligo ingest isrctn                        # ISRCTN (UK and international); keeps only vitiligo trials
vitiligo ingest opentargets                   # drug and target priors (EFO_0004208)
vitiligo ingest gwas                          # vitiligo variants from the GWAS Catalog (157 associations)
vitiligo ingest reporter                      # NIH-funded vitiligo projects (who is working on what)
vitiligo ingest ictrp-search                  # WHO ICTRP search: ~1,020 vitiligo trials
vitiligo ingest ictrp-ids --cited             # WHO ICTRP by id, for a trial a paper cites
vitiligo ingest ictrp export.xml              # WHO ICTRP bulk XML export
vitiligo ingest drugbank db.xml               # your own licensed DrugBank export (.xml or .zip)

# Search and reasoning
vitiligo embed run                            # ~10–20 min on CPU
vitiligo embed full-text                     # chunk and embed paper bodies (PMC full text)
vitiligo search "..." --full-text             # search those passages, with the quote that matched
vitiligo embed stats
vitiligo search "IFN-gamma CXCL10 axis" --top-k 10 --show-abstract
vitiligo trials stats
vitiligo trials search --status RECRUITING --phase PHASE2
vitiligo priors stats
vitiligo priors sample --kind target -l 10

# Knowledge graph
vitiligo graph seed                           # deterministic, from priors + trials
vitiligo graph seed-evidence                 # edges from GWAS, trial results and mechanism records
vitiligo graph stats
vitiligo graph search ruxolitinib
vitiligo graph neighbors vitiligo
vitiligo graph export -o exports/graph-review.json

# Reports (deterministic)
vitiligo report candidates --json exports/candidate-report.json --markdown exports/candidate-report.md
vitiligo report cited-trials                 # trials named in papers that no registry we read holds
vitiligo report funding --since 2024          # who holds NIH funding on vitiligo now
vitiligo report jak --json exports/jak-atlas.json --markdown exports/jak-atlas.md --csv-dir exports/jak-atlas
vitiligo report jak-arms --csv exports/jak-arms.csv --json exports/jak-arms.json [--with-papers]

# Results from open-access papers (curation/README.md)
vitiligo papers tables PMC11169949           # print an article's tables while curating
vitiligo papers verify                       # check every curated number against its printed cell

# Mechanistic hypotheses (docs/mechanisms/README.md)
vitiligo mechanism list                      # every hypothesis and what its support reaches
vitiligo mechanism show trm-il15-relapse     # chain, evidence, competing explanations, test
vitiligo mechanism verify                    # the gate: chain, falsifiability, citations, seals
vitiligo mechanism seal <id>                 # freeze the claim, context and test (evidence may still grow)

# Scenario model ([model] extra; docs/jak-scenario-model.md)
vitiligo model backtest --instrument F-VASI --out exports/model/backtest-F-VASI.json
vitiligo model predict --agent ritlecitinib --dose 50 --unit mg --week 52 --threshold 75
#   sealing also needs: --freeze PATH --public-results-check "press releases, EADV/AAD abstracts, PubMed: none"
#   and committed model code (the commit is sealed into the record)

# Discovery loop ([model] extra; docs/discovery-loop-plan.md)
vitiligo discover run                         # held-out tests under e-LOND FDR control
vitiligo discover ledger
vitiligo discover import-forecasts forecasts/2026-10-14-tranquillo
vitiligo discover forecast-pending --out forecasts/<date>-auto --backtest-dir exports/model \
  --public-results-check "..." [--skip NCT...]   # seal forecasts for unreported trials
vitiligo discover resolve                     # score ledger forecasts after a corpus refresh
vitiligo discover check-forecasts forecasts   # score sealed files straight from ClinicalTrials.gov (no corpus)
vitiligo discover watch forecasts --days 8    # rank pending results by what they would tell us; list new papers, trials, SEC filings

# Web UI
vitiligo serve [--host 0.0.0.0 --port 8080]   # http://127.0.0.1:8765
```

## Adding a source

1. Create `src/vitiligo/sources/<name>.py` with a client (rate limits, retries) and a parser that yields `Document` instances.
2. Add the source to `SourceKind` in `vitiligo.storage.models`.
3. Add a pipeline function in `vitiligo.ingest.pipeline`, modelled on `run_pubmed_ingestion`.
4. Add a CLI subcommand under `vitiligo ingest`.
5. Add offline parser tests in `tests/unit/parsers/test_<name>_parser.py` using a captured response.

Source clients stay independent: they share only `storage` and `config`.

## Data licensing

- The repository ships no corpus, no DrugBank export and no DrugBank-derived data.
- DrugBank import is optional and local. Use only an export you are licensed for, and publish derived records only if your license allows it. Parser tests use a synthetic DrugBank-shaped fixture.

## Operations

- **NCBI rate limits:** 3 requests/s without a key, 10/s with one ([get a key](https://www.ncbi.nlm.nih.gov/account/)). NCBI requires `NCBI_EMAIL`.
- **Storage:** `data/vitiligo.db` by default (gitignored); override with `VITILIGO_DB_PATH`. SQLite is enough at this scale.
- **Logs:** `rich`; set `LOG_LEVEL` or `--log-level`.
- **Releases:** push an annotated `v*` tag ([`release.yml`](../.github/workflows/release.yml)) or run `./scripts/release/create-github-release.sh vX.Y.Z`.
