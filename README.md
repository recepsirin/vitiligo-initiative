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
| **Knowledge graph** | 17,685 drugs, genes, diseases, adverse events, trials and interventions linked by 62,006 relations, each with its evidence: the paper, trial record or database entry, and the sentence where its licence allows. Half the relations are measurements: what trials posted to ClinicalTrials.gov or printed in their papers, each beside its comparator, and the genes lesional skin expresses differently in three GEO cohorts. Released openly on Hugging Face (CC BY 4.0; ICTRP-derived relations under WHO's terms). | [Dataset card](https://huggingface.co/datasets/re-cep/vitiligo-knowledge-graph) · `vitiligo graph release` |
| **Relation extractor** | A BiomedBERT model fine-tuned to read which drugs, diseases and genes a paper relates, and how. It fills the knowledge graph from the full texts PubTator does not read, and every edge it adds cites its sentence. BioRED test F1 0.687 for the related pair, 0.540 with its type; 75% of the relations it loads were correct when checked by hand. | [Model card](https://huggingface.co/re-cep/vitiligo-relation-extractor) · `vitiligo relations evaluate` |
| **Relational GNN & Reranker** | A 1,924-D multimodal Relational GNN (`FastRGCN` + asymmetric `ComplEx` Hermitian decoder) and Stage-2 Dense Cross-Encoder (94% accuracy). Screens 893 canonical molecules across multi-target pathways: $T_{\text{RM}}$ disarmament, stem cell regeneration, and GSE256271 `PDE4B` non-responder barrier suppression. | [Model card](https://huggingface.co/re-cep/vitiligo-relational-gnn) · `vitiligo gnn rerank` · [`docs/gnn-reranked-report.md`](docs/gnn-reranked-report.md) |
| **Translational Discovery Suite** | Interactive public web application on Hugging Face Spaces: explores in silico multi-target synergies, the 2,257-trial clinical pipeline explorer, head-to-head outcomes benchmarks, the pre-registered $T_{\text{RM}}$ Relapse Index ($S_{\text{TRM}}$), maintenance pharmacoeconomics, and open research data downloads. | [Live Space](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · [`docs/curative-triad-investigator-brief.md`](docs/curative-triad-investigator-brief.md) |

**Nothing on the served page is generated.** Every figure it shows is one a trial
posted to a public registry, reproduced with its denominator and a link to its
record, so any number on the page can be checked against its source. That holds
without a caveat because nothing here generates text: there is no model API
client in this repository and no key to configure. The only models are two
local readers: the embeddings behind search and the relation extractor above.

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
vitiligo gnn rerank --top-stage1 60 --top-final 20
```

## Documentation

Comprehensive guides, specifications, and *in silico* research dossiers are organized in **[`docs/`](docs/README.md)**:

| Category | Description | Key Documents |
|---|---|---|
| **Architecture & Systems** | Engineering specifications, CLI commands, ingest pipeline, Docker, and FastAPI backend. | [`architecture.md`](docs/architecture.md) · [`engine.md`](docs/engine.md) · [`deploy.md`](docs/deploy.md) · [`discovery-loop-plan.md`](docs/discovery-loop-plan.md) |
| **Translational Hypotheses** | *In silico* multi-target synergy screening, GNN link prediction, and preclinical assay protocols. | [`curative-triad-investigator-brief.md`](docs/curative-triad-investigator-brief.md) · [`gnn-reranked-report.md`](docs/gnn-reranked-report.md) · [`pairwise-synergy-matrix.md`](docs/pairwise-synergy-matrix.md) |
| **Pre-registrations & Seals** | Frozen prior distributions and cryptographic hashes sealing models before outcome unblinding. | [`durability/trm-signature-preregistration.md`](docs/durability/trm-signature-preregistration.md) (Seal `2c102804`) · [`model-v0.5-preregistration.md`](docs/model-v0.5-preregistration.md) |
| **Clinical Concepts & Health Econ** | Resident memory T-cell ($T_{\text{RM}}$) durability models, mechanisms causal ladders, and HEOR maintenance cost comparisons. | [`durability/`](docs/durability/README.md) · [`mechanisms/`](docs/mechanisms/README.md) · [`safety-access/`](docs/safety-access/README.md) |
| **Working Manuscripts** | Internal drafts detailing data ingest methodology and sealed prospective Bayesian forecasting. | [`methods-preprint-draft.md`](docs/methods-preprint-draft.md) · [`forecasting-preprint-draft.md`](docs/forecasting-preprint-draft.md) |

See the complete index and table of contents in **[`docs/README.md`](docs/README.md)**.

[CONTRIBUTING](CONTRIBUTING.md) · [SECURITY](SECURITY.md) (no public issues for vulnerabilities) · [CHANGELOG](CHANGELOG.md)

## Status

v1.0.0 is tagged and runs local-first; a public URL is not live yet. The test suite is the quality gate: CI runs everything that needs no local corpus, and `./scripts/audit/smoke-all.sh` runs the full local gate.

## Community and citation

Questions and ideas: [Discussions](https://github.com/recepsirin/vitiligo-initiative/discussions). Bugs: [Issues](https://github.com/recepsirin/vitiligo-initiative/issues). Support: [GitHub Sponsors](https://github.com/sponsors/recepsirin). Licensed [Apache 2.0](LICENSE) ([NOTICE](NOTICE)).

If you use this software in research, cite the repository. Two preprints are in preparation: the engine ([`docs/methods-preprint-draft.md`](docs/methods-preprint-draft.md)) and the sealed-forecast work ([`docs/forecasting-preprint-draft.md`](docs/forecasting-preprint-draft.md)).
