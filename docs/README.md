# Documentation Index

> [!NOTE]
> **Open Translational Research Software & Data.**
> The documentation in this repository spans software engineering architecture, Bayesian trial modeling, and *in silico* translational biology hypotheses. These materials are computational research tools intended to guide preclinical laboratory exploration; they do not constitute validated clinical protocols or medical treatment advice.

---

## Documentation Map

```
docs/
├── Engineering & Systems Architecture       (CLI, ingest pipeline, Docker, API)
├── In Silico Translational Dossiers         (Multi-target GNN hypotheses, synergy matrix, targets)
├── Pre-registrations & Cryptographic Seals  (Frozen model weights, sealed trial forecasts)
├── Domain Modules & Validation Concepts     (Durability, mechanisms, repigmentation, safety)
└── Internal Working Manuscript Drafts       (Engine & forecasting preprint drafts)
```

Interactive exploration of candidate rankings, clinical trial outcomes, and open data exports is hosted live at the **[Vitiligo Translational Discovery Suite](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery)** on Hugging Face Spaces.

---

### 1. Engineering & Systems Architecture

Core technical documentation for developers, bioinformaticians, and system administrators running or extending the platform:

| Document | Purpose & Scope | Primary Commands |
|---|---|---|
| [`architecture.md`](architecture.md) | High-level system design: SQLite corpus, FAISS vector index, relation graph, and FastAPI endpoints. | `vitiligo serve` |
| [`engine.md`](engine.md) | Comprehensive CLI reference, registry ingest crawlers (PubMed, PMC, CT.gov, WHO ICTRP), and local embedding pipeline. | `vitiligo ingest`, `vitiligo search` |
| [`deploy.md`](deploy.md) | Deployment runbook: Docker containerization, local host prerequisites, environment variables, and memory requirements. | `docker-compose up` |
| [`discovery-loop-plan.md`](discovery-loop-plan.md) | Statistical discovery loop: controlling the False Discovery Rate (FDR) at $\le$ 10% across sequential trial claims. | `vitiligo discovery run` |
| [`jak-scenario-model.md`](jak-scenario-model.md) | Hierarchical Bayesian scenario model forecasting arm-level responder rates across drug, dose, and week. | `vitiligo model predict` |
| [`roadmap.md`](roadmap.md) | Development roadmap, milestone tracking, and quality gates across versions. | — |
| [`strategic-plan.md`](strategic-plan.md) | Institutional mission, project phases, and operational non-goals. | — |

---

### 2. In Silico Translational Research Dossiers

Computational pharmacology and graph neural network (GNN) dossiers prioritizing multi-target combination hypotheses for preclinical wet-lab assay validation:

| Dossier | Key Focus | Output Assets |
|---|---|---|
| [`curative-triad-investigator-brief.md`](curative-triad-investigator-brief.md) | **Multi-Target Translational Rationale:** Overcoming the oral kinase plateau (~15% clearance) via concurrent immune shielding, McSC mobilization, and PDE4B barrier suppression. | Executive Dossier |
| [`gnn-reranked-report.md`](gnn-reranked-report.md) | **Stage-2 Dense Cross-Encoder Rankings:** 5-fold cross-validated candidate screening across 893 small molecules (AUROC 0.8980). | `exports/gnn_reranked_candidates.json` |
| [`gnn-discovery-report.md`](gnn-discovery-report.md) | **Relational Knowledge Graph Screen:** 96,073-edge graph embedding results via RGAT-4H + ComplEx Hermitian decoder. | `exports/gnn_candidate_report.json` |
| [`pairwise-synergy-matrix.md`](pairwise-synergy-matrix.md) | **Pairwise Virtual Synergies:** Chou-Talalay Combination Index (CI < 0.70) and Bliss excess matrix across dermatologic compounds. | `exports/gnn_pairwise_synergy_matrix.json` |
| [`reverse-target-screening.md`](reverse-target-screening.md) | **Reverse Bottleneck Screen:** ComplEx decoder link prediction identifying candidates targeting PDE4B, EDNRB, MITF, and IL-15. | `exports/reverse_target_screening.json` |
| [`clinical-validation-and-formulation.md`](clinical-validation-and-formulation.md) | **Translational Synthesis:** Registry trial evidence, topical delivery formulation notes, and 3-stage human tissue assay cascade. | Protocol VAL-DOSSIER-2026-V1 |
| [`scientific-brief.md`](scientific-brief.md) | Disease biology, auto-antigen pathogenesis, and structural evidence gaps in non-segmental vitiligo. | Background Brief |
| [`candidate-report-v1.md`](candidate-report-v1.md) | Initial evidence-scored single-molecule candidates based on PubTator and trial literature. | Historical Baseline |

---

### 3. Pre-registrations & Cryptographic Seals

To eliminate post-hoc data fitting, all model priors and forecast evaluation rules are pre-registered and cryptographically hashed before outcome unblinding:

| Pre-registration | Registered Scope | Cryptographic Verification |
|---|---|---|
| [`model-v0.3-preregistration.md`](model-v0.3-preregistration.md) | Initial Bayesian prior distributions for JAK-inhibitor F-VASI and T-VASI endpoints. | Sealed v0.3 |
| [`model-v0.4-preregistration.md`](model-v0.4-preregistration.md) | Prior updates incorporating week 24 to week 52 extension trials and background phototherapy. | Sealed v0.4 |
| [`model-v0.5-preregistration.md`](model-v0.5-preregistration.md) | Integration of pediatric cohorts and topical formulation bioavailability adjustments. | Sealed v0.5 |
| [`durability-forecast-preregistration.md`](durability-forecast-preregistration.md) | Prospective relapse hazard evaluation rules following treatment cessation. | Sealed Durability |
| [`durability/trm-signature-preregistration.md`](durability/trm-signature-preregistration.md) | **$T_{\text{RM}}$ Relapse Index ($S_{\text{TRM}}$):** 10-gene blister roof RNA-seq scoring coefficients (HR > 1.0). | **Seal `2c102804`** |
| [`voi-preregistration.md`](voi-preregistration.md) | Value-of-Information (VoI) acquisition function for prioritizing evidence collection. | Sealed VoI |
| [`voi-ranking-preregistration.md`](voi-ranking-preregistration.md) | Frozen trial ranking criteria based on expected epistemic uncertainty reduction. | Sealed Ranking |

---

### 4. Domain Subdirectories & Clinical Protocols

Specialized submodules containing domain-specific concept notes, trial bridges, and health-economics analyses:

* **[`validation-proposals/`](validation-proposals/):**
  * `curative-triad-preclinical-dossier.md` — Experimental protocol for validating 3-pillar synergy in human organotypic skin models.
  * `ruxolitinib-nb-uvb-combination.md` — Protocol concept for topical JAK + targeted phototherapy synchronization.
  * `povorcitinib-phase3-bridge.md` — Mechanistic bridging analysis for oral JAK1 non-responder phenotypes.
  * `upadacitinib-extensive-nsv.md` — Strategic trial design for extensive non-segmental vitiligo.
* **[`durability/`](durability/README.md):** Resident memory T-cell ($T_{\text{RM}}$) biology, suction blister RNA-seq protocols, and low-dose maintenance trial concepts.
* **[`mechanisms/`](mechanisms/README.md):** Falsifiable mechanistic claims structured on a causal ladder with testable hypotheses.
* **[`safety-access/`](safety-access/README.md):** Pharmacoeconomic models evaluating continuous biologics ($27k/yr) versus step-down maintenance regimens.
* **[`repigmentation/`](repigmentation/README.md):** Follicular melanocyte stem-cell (McSC) activation biology and anatomical response kinetics.
* **[`spread/`](spread/README.md):** Active lesion boundary dynamics and depigmentation spreading rates.

---

### 5. Working Manuscript Drafts

Internal working drafts documenting the underlying methodology:

* **[`methods-preprint-draft.md`](methods-preprint-draft.md):** Technical manuscript draft describing the multi-registry evidence extraction engine and relation graph construction.
* **[`forecasting-preprint-draft.md`](forecasting-preprint-draft.md):** Methodological draft detailing sealed Bayesian forecasting and prospective registry evaluation.

---

### 6. Public Exploration & Data Downloads

All datasets generated by these analyses are released under open licenses (**CC BY 4.0** and **MIT**):
* **Live Discovery Space:** [https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery)
* **Knowledge Graph Dataset:** [https://huggingface.co/datasets/re-cep/vitiligo-knowledge-graph](https://huggingface.co/datasets/re-cep/vitiligo-knowledge-graph)
* **GNN & Relation Extractor Models:** [https://huggingface.co/re-cep/vitiligo-relational-gnn](https://huggingface.co/re-cep/vitiligo-relational-gnn)
