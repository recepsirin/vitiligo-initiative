# Vitiligo Initiative

<p>
  <a href="https://github.com/recepsirin/vitiligo-initiative/actions/workflows/ci.yml"><img src="https://github.com/recepsirin/vitiligo-initiative/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License: Apache 2.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
</p>

> **Open, verifiable evidence for vitiligo research.** Every source is public, every answer is cited, and every forecast is sealed before we look at its results.

Research and education software, not medical advice.

## What is here

| | What it does | Start with |
|---|---|---|
| **Evidence Engine** | One searchable corpus of PubMed, PMC, GEO and the WHO ICTRP network (14,497 documents, 1,064 trials, 684 of them from the sixteen registries that publish no API of their own — CTRI, ChiCTR, IRCT, ITMCTR, JPRN, PACTR, TCTR and the rest). Semantic search with evidence levels, and a trial-results table: what each JAK drug and dose reported at week 24, beside the comparator arm of its own trial. | `vitiligo serve` · `vitiligo search` |
| **JAK-inhibitor atlas** | Every registered vitiligo trial of a JAK-family drug, linked across registries, with posted outcomes, plus one harmonized arm × endpoint × week table and results curated from papers ([`curation/`](curation/)). | `vitiligo report jak` · `vitiligo report jak-arms` |
| **Scenario model** | Bayesian model of responder rates by drug, dose and week, judged only on trials it has not seen. Its forecasts of unreported trials are sealed and scored weekly as results post. | [`docs/jak-scenario-model.md`](docs/jak-scenario-model.md) · [`forecasts/`](forecasts/README.md) |
| **Discovery loop** | Tests claims on held-out trials and controls the false discovery rate at 10% across an open-ended stream; every test is recorded. | [`docs/discovery-loop-plan.md`](docs/discovery-loop-plan.md) |
| **Mechanisms** | Falsifiable hypotheses from biology to clinical outcome, each with its evidence on a causal ladder, the strongest rival explanation, and the test that separates them. | `vitiligo mechanism list` · [`docs/mechanisms/`](docs/mechanisms/README.md) |

**Nothing on the served page is generated.** Every figure it shows is one a trial
posted to a public registry, reproduced with its denominator and a link to its
record, so any number on the page can be checked against its source. Cited Q&A
No model is involved anywhere, which is why that holds without a caveat: there
is no model API client in this repository and no key to configure.

## What the trial-results view will and will not show

The table reports **week 24**, the primary endpoint of every registered JAK trial
in vitiligo and so the only week at which they can be set beside one another. Four
rules decide what reaches it, each of which excludes a figure that would otherwise
read far better than the evidence supports:

- **The largest arm reporting a drug and dose wins** — not the latest week, and not
  the highest rate. A seven-patient arm reporting 85.7% does not outrank a
  222-patient trial reporting 30.9%.
- **An arm must still be reporting the group that was randomised.** One trial reads
  45.5% of 33 at week 24 and 100% of 9 at week 156: the rate climbs because the
  denominator collapses.
- **Where a trial reported both a blinded central reading and the site's own, the
  central one is used.** It is consistently the lower of the two.
- **Facial and whole-body scores never mix**, and a drug given with phototherapy is
  a different intervention from the drug alone.

Figures after week 24 appear in their own column, labelled: these trials put every
patient on the drug once the controlled period ended, so they show one group
improving over time with no comparator and a shrinking denominator.

Adverse events are deliberately absent. They belong in the label and the registry
record, not in a summary table that cannot carry their context.

## Quick start

Python 3.11+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # add ,model for the scenario model and discovery loop
cp .env.example .env               # set NCBI_EMAIL; optional NCBI_API_KEY

vitiligo db init
vitiligo ingest pubmed && vitiligo ingest pmc && vitiligo ingest ctgov
vitiligo embed run && vitiligo graph seed
vitiligo serve                     # http://127.0.0.1:8765
```

The corpus (`data/vitiligo.db`) is built locally and never committed. `./scripts/ingest/sync-engine.sh` runs the full ingest.

```bash
vitiligo search "JAK inhibitor repigmentation in non-segmental vitiligo"
vitiligo report jak-arms --csv exports/jak-arms.csv
vitiligo model predict --agent ritlecitinib --dose 50 --unit mg --week 52 --threshold 75
```

## Documentation

| Doc | Contents |
|---|---|
| [`docs/success.md`](docs/success.md) | **What we are trying to solve:** the outcomes that define success, and the current focus (durability) |
| [`docs/findings.md`](docs/findings.md) | **Start here:** what the JAK work found, and what we need experts to check |
| [`docs/mechanisms/README.md`](docs/mechanisms/README.md) | Mechanistic hypotheses: the claim, its evidence, the rival explanation, and the test |
| [`docs/engine.md`](docs/engine.md) | Setup, every CLI command, adding a source |
| [`docs/architecture.md`](docs/architecture.md) | Modules, data flow, web API |
| [`docs/jak-scenario-model.md`](docs/jak-scenario-model.md) | Scenario model, back-tests, forecasting policy |
| [`docs/discovery-loop-plan.md`](docs/discovery-loop-plan.md) | Discovery loop: guarantees, claim families, phases |
| [`docs/deploy.md`](docs/deploy.md) | Docker, what a host needs, environment variables |
| [`docs/roadmap.md`](docs/roadmap.md) | **What comes next:** the order of work, what each step needs, and the gates |
| [`docs/strategic-plan.md`](docs/strategic-plan.md) | Mission, phases, non-goals |
| [`docs/scientific-brief.md`](docs/scientific-brief.md) | Disease biology, treatments, evidence gaps |
| [`docs/candidate-report-v1.md`](docs/candidate-report-v1.md) | Evidence-scored therapeutic candidates |

[CONTRIBUTING](CONTRIBUTING.md) · [SECURITY](SECURITY.md) (no public issues for vulnerabilities) · [CHANGELOG](CHANGELOG.md)

## Status

v1.0.0 is tagged and runs local-first; a public URL is not live yet. The test suite is the quality gate: CI runs everything that needs no local corpus, and `./scripts/audit/smoke-all.sh` runs the full local gate.

## Community and citation

Questions and ideas: [Discussions](https://github.com/recepsirin/vitiligo-initiative/discussions). Bugs: [Issues](https://github.com/recepsirin/vitiligo-initiative/issues). Support: [GitHub Sponsors](https://github.com/sponsors/recepsirin). Licensed [Apache 2.0](LICENSE) ([NOTICE](NOTICE)).

If you use this software in research, cite the repository. Two preprints are in preparation: the engine ([`docs/methods-preprint-draft.md`](docs/methods-preprint-draft.md)) and the sealed-forecast work ([`docs/forecasting-preprint-draft.md`](docs/forecasting-preprint-draft.md)).
