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

To keep the repository clean and developer-focused, the computational pharmacology dossiers and dynamic GNN screening datasets have been migrated into the **[Translational Discovery Suite](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery)** on Hugging Face Spaces. Researchers can explore them interactively and download the full Markdown dossiers and raw CSV tables:

| Dossier / Asset | Key Focus | Live Space Location & Downloads |
|---|---|---|
| **Multi-Target Investigator Brief** | Overcoming the oral kinase plateau (~15% clearance) via concurrent immune shielding, McSC mobilization, and PDE4B barrier suppression. | [Space Tab 6: Executive Dossiers](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · 1-click MD |
| **Preclinical Assay Cascade (VAL-DOSSIER-2026-V1)** | Three-stage experimental assay pipeline: in vitro HEM rescue, ex vivo organotypic skin explants, and suction blister roof flow cytometry. | [Space Tab 6: Executive Dossiers](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · 1-click MD |
| **Dual-Action Formulation & Delivery Guide** | Physicochemical logP matching, Franz cell diffusion testing, vehicle bases, and follicular reservoir accumulation. | [Space Tab 6: Open Data Downloads](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · 1-click MD |
| **Clinical Protocol Bridges & Trial Concepts** | Synchronized NB-UVB phototherapy, overcoming the +9.09 log2FC PDE4B block, and step-down maintenance design. | [Space Tab 6: Open Data Downloads](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · 1-click MD |
| **Stage-2 Reranked Candidate Ledger** | 5-fold cross-validated candidate screening across 893 small molecules (AUROC 0.8980). | [Space Tab 1: View 2](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · 1-click CSV |
| **Pairwise Virtual Synergies Matrix** | Chou-Talalay Combination Index (CI < 0.70) and Bliss excess matrix across dermatologic compounds. | [Space Tab 1: View 1](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · 1-click CSV |
| **Reverse Target Screening Ledger** | ComplEx decoder link prediction identifying candidates targeting PDE4B, EDNRB, MITF, and IL-15. | [Space Tab 1: View 3](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery) · 1-click CSV |
| [`scientific-brief.md`](scientific-brief.md) | Disease biology, auto-antigen pathogenesis, and structural evidence gaps in non-segmental vitiligo. | In-repo background brief |
| [`governance-ethics-brief.md`](governance-ethics-brief.md) | Governance principles, patient safety guardrails, transparency, and data privacy framework. | In-repo policy document |

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

### 4. Domain Subdirectories

Specialized submodules containing domain-specific concept notes and health-economics analyses:

* **[`durability/`](durability/README.md):** Resident memory T-cell ($T_{\text{RM}}$) biology, suction blister RNA-seq protocols, and low-dose maintenance trial concepts.
* **[`mechanisms/`](mechanisms/README.md):** Falsifiable mechanistic claims structured on a causal ladder with testable hypotheses.
* **[`safety-access/`](safety-access/README.md):** Pharmacoeconomic models evaluating continuous biologics ($27k/yr) versus step-down maintenance regimens.
* **[`repigmentation/`](repigmentation/README.md):** Follicular melanocyte stem-cell (McSC) activation biology and anatomical response kinetics.
* **[`spread/`](spread/README.md):** Active lesion boundary dynamics and depigmentation spreading rates.
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
