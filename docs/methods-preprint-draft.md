# Methods Preprint — Draft Text

**Status:** Draft v0.2 (May 2026) — Abstract + Introduction written; Methods sections follow [`methods-preprint-outline.md`](methods-preprint-outline.md)  
**Working title:** *An open vitiligo evidence engine: multi-source corpus ingestion, knowledge graph seeding, and cited hypothesis generation*  
**Authors:** [TBD]  
**Word count (this file):** ~1,400 (Abstract + Introduction)

---

## Abstract

**Background.** Vitiligo affects approximately 0.5–2% of the population and is associated with significant quality-of-life burden. Non-segmental vitiligo (NSV) is commonly progressive and autoimmune in nature; segmental vitiligo (SV) follows a different clinical course. Treatment goals combine **arrest of active spread** and **repigmentation**, particularly on visible and functionally important sites. The evidence base spans thousands of PubMed-indexed publications, open-access full-text articles, omics repositories, and multiple clinical trial registries, alongside genetic association data from platforms such as Open Targets. Researchers and clinicians lack an open, vitiligo-specific system that unifies these sources for semantic retrieval, cited synthesis, and mechanistically grounded hypothesis ranking.

**Methods.** We developed the Vitiligo Initiative Evidence Engine, an open-source pipeline (Apache 2.0) comprising: (1) idempotent ingestion from PubMed, PubMed Central Open Access, NCBI GEO DataSets, ClinicalTrials.gov, the EU Clinical Trials Register (CTIS), Open Targets, and optional XML imports from WHO ICTRP and DrugBank; (2) document storage and bookkeeping in SQLite; (3) semantic search using ONNX embeddings (`BAAI/bge-small-en-v1.5`) with rule-based evidence-level tagging; (4) cross-registry trial normalization and structured search; (5) a knowledge graph (v1) seeded deterministically from genetic/pharmacological priors and trial interventions; (6) retrieval-augmented question answering and four-stream therapeutic hypothesis generation using Anthropic Claude, with separate citation channels for papers, trials, priors, and graph relations; and (7) a FastAPI web interface with deployment tooling for EU-region hosting.

**Results.** The May 2026 local corpus contains 14,245 documents (11,356 PubMed, 2,578 PMC, 311 GEO), 14,242 title–abstract embeddings, 344 harmonized trial records, 237 Open Targets priors for vitiligo (EFO_0004208), and a knowledge graph of 1,044 entities and 1,643 edges. Automated invariant checks and a 20-query retrieval evaluation set support expert review. The system is deployable via Docker (and optional Render / VPS hosting) with privacy disclaimers and rate limiting.

**Conclusions.** We release reproducible infrastructure for vitiligo evidence synthesis and hypothesis exploration. The engine is intended for research and education, not clinical decision-making; LLM-generated outputs require expert validation. Future work includes hybrid retrieval, full-text chunk embeddings, omics re-analysis, and prospective evaluation of hypothesis usefulness with vitiligo specialists.

**Availability.** Source code: https://github.com/recepsirin/vitiligo-initiative. Public deployment: [URL pending — DigitalOcean or Render].

---

## 1. Introduction

Vitiligo is an acquired disorder of pigmentation characterized by depigmented macules and patches resulting from loss of epidermal melanocytes. Although often considered cosmetic, vitiligo is associated with psychological distress, stigmatization, and comorbid autoimmune disease. Clinicians and patients face two intertwined objectives: **preventing or halting disease progression**—particularly in NSV, where new lesions may appear over years—and **restoring pigment** on cosmetically and functionally important anatomical sites such as the face and hands. Response varies by subtype, body site, and treatment modality; acral and leukotrichic lesions remain notoriously difficult to repigment.

Over the past decade, mechanistic understanding of NSV has converged on an autoimmune loop involving interferon-γ (IFN-γ) signaling, Janus kinase (JAK)–signal transducer and activator of transcription (STAT) activation, and CXCL10-mediated recruitment of autoreactive CD8⁺ T cells to lesional skin. This framework has translated into clinical development of JAK inhibitors. Topical ruxolitinib cream is approved in the United States for adult and adolescent NSV, and multiple oral and topical JAK-directed agents—including povorcitinib, upadacitinib, and ritlecitinib—are in Phase 2–3 programs with active registration in North American and European trial registries. Narrowband ultraviolet B (NB-UVB) phototherapy and topical anti-inflammatory agents remain widely used first-line approaches, but optimal sequencing, combination strategies, maintenance therapy, and subtype-specific protocols are incompletely defined.

Despite this progress, the **primary evidence remains fragmented**. Published literature resides in PubMed and scattered journals; a subset of full-text open-access articles is available through PubMed Central; transcriptomic and other omics studies are deposited in GEO and related archives; trial protocols and results are distributed across ClinicalTrials.gov, the EU CTIS portal, and national registries aggregated by WHO ICTRP; and genetic and pharmacological priors are curated in resources such as Open Targets and DrugBank. Systematic reviews and narrative updates synthesize slices of this landscape, but they are episodic, manually intensive, and rarely expose a reusable machine-readable graph linking **drugs, targets, trials, and publications** for interactive hypothesis generation.

General-purpose literature tools—including semantic search portals, reference managers with AI assistants, and broad biomedical knowledge graphs—help individual researchers but are not tailored to vitiligo’s subtype heterogeneity, evolving trial pipeline, or the need to combine registry operations data with mechanistic priors. There is no widely available, open, vitiligo-specific engine that (a) rebuilds a auditable corpus from public sources, (b) supports semantic retrieval with explicit evidence-level metadata, (c) answers questions with bracketed citations grounded in retrieved documents, and (d) ranks therapeutic hypotheses using parallel evidence from papers, trials, genetic priors, and a structured knowledge graph.

Here we describe the **Vitiligo Initiative Evidence Engine**, version 1.0, built to address that gap as a non-profit, open-science infrastructure project. Our objectives are: (1) to construct a reproducible, versioned vitiligo corpus with documented ingestion provenance; (2) to enable semantic search and structured trial discovery with evidence-level tagging; (3) to provide retrieval-augmented, citation-constrained question answering over the literature; (4) to generate ranked therapeutic candidate hypotheses with separate attribution to literature, trials, Open Targets priors, and knowledge-graph relations; and (5) to ship deployment and governance tooling suitable for public beta release with explicit “research only” framing.

We emphasize **scope and limits**. This system is not a medical device, diagnostic, or prescribing aid. It does not replace systematic review, meta-analysis, or peer review. Large language model (LLM) synthesis can omit context, misrank evidence, or misstate certainty even when citations are displayed. Accordingly, we deploy the engine with medical disclaimers, privacy and terms pages, rate limiting, and a structured advisor review pathway—including automated knowledge-graph checks, graph JSON export, and a 20-query retrieval evaluation set for expert labeling—before treating outputs as initiative-endorsed recommendations.

The remainder of this manuscript details system architecture and ingestion methods ([Section 2](#2-methods)); corpus and graph statistics ([Section 3](#3-results)); evaluation design and limitations ([Sections 3–4](#3-results)); and data availability ([Section 5](#5-data-and-code-availability)). By releasing code, deployment scripts, and corpus construction methods, we aim to accelerate vitiligo research—whether or not this particular initiative succeeds in translation—while maintaining scientific integrity appropriate to a disease that affects millions of patients worldwide.

---

## 2. Methods

*(Full section text: expand from [`methods-preprint-outline.md`](methods-preprint-outline.md) §2.1–2.10. Subsections below are headings only until evaluation data are collected.)*

### 2.1 System overview

### 2.2 Document corpus

### 2.3 Clinical trial harmonization

### 2.4 Genetic and pharmacological priors

### 2.5 Embeddings and retrieval

### 2.6 Evidence-level classification

### 2.7 Knowledge graph v1

### 2.8 Reasoning layer

### 2.9 Web application and deployment

### 2.10 Evaluation plan

---

## 3. Results

*(Pending: corpus benchmark table, retrieval evaluation after advisor labeling, example Ask/Hypothesize outputs with advisor sign-off.)*

---

## 4. Discussion

*(Pending.)*

---

## 5. Data and code availability

- **Code:** https://github.com/recepsirin/vitiligo-initiative (Apache 2.0)  
- **Documentation:** `docs/engine.md`, `docs/deploy.md`  
- **Graph export:** `vitiligo graph export`  
- **Evaluation queries:** `docs/eval-queries.json`  
- **Public URL:** [pending deploy]

---

## Next writing tasks

- [ ] Fill Methods §2.2–2.9 from outline + `docs/engine.md`  
- [ ] Add corpus ingestion runtime table  
- [ ] Insert architecture figure (Fig 1)  
- [ ] Complete Results after advisor labels `retrieval-eval.json`  
- [ ] Add 30 Ask faithfulness pairs post-KOL meeting  
- [ ] Legal review before submitting URL in Abstract  
