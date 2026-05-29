# Methods Preprint — Outline

**Status:** Draft outline v0.1 (May 2026)  
**Working title:** *An open vitiligo evidence engine: multi-source corpus ingestion, knowledge graph seeding, and cited hypothesis generation*  
**Target venues:** medRxiv / bioRxiv (methods-first); journal targets: *npj Digital Medicine*, *JAMIA Open*, *Briefings in Bioinformatics*  
**License intent:** CC-BY for text; Apache 2.0 for code; Zenodo DOI for corpus snapshot metadata  

---

## One-sentence contribution

We describe and release an open, reproducible pipeline that unifies vitiligo literature, trial registries, genetic priors, and a structured knowledge graph to support semantic search, cited Q&A, and multi-stream therapeutic hypothesis generation — with explicit evidence-level tagging and public deployment tooling.

---

## Abstract (bullet draft)

- **Background:** Vitiligo evidence is fragmented across PubMed, full-text archives, trial registries, genetics platforms, and omics repositories; manual synthesis is slow and rarely links trials to mechanisms systematically.  
- **Methods:** We built the Vitiligo Initiative Evidence Engine: idempotent ingestion into SQLite, ONNX embeddings (`BAAI/bge-small-en-v1.5`), cross-registry trial normalization, Open Targets / DrugBank priors, deterministic knowledge-graph seeding from priors + trials, RAG-based Q&A, and four-stream hypothesis generation (papers, trials, priors, graph) via Claude.  
- **Corpus (May 2026):** 14,245 documents (11,356 PubMed, 2,578 PMC OA, 311 GEO); 14,242 embeddings; 344 trials (CT.gov, EU CTR, ICTRP); 237 priors; 1,044 graph entities / 1,643 edges.  
- **Availability:** Apache-2.0 code, CLI + FastAPI UI, Fly.io deploy scripts, graph JSON export, GitHub Actions CI.  
- **Conclusion:** Open infrastructure for vitiligo evidence synthesis; not a clinical decision system — expert validation required before therapeutic claims.

---

## 1. Introduction (~800 words)

### 1.1 Clinical and research context
- NSV vs SV; spread arrest + repigmentation as dual goals  
- Recent JAK-pathway trials and approved topical ruxolitinib (US)  
- Gap: no open, vitiligo-specific system linking **papers + trials + genetics + graph** for ranked hypotheses  

### 1.2 Related work (to cite / compare)
- General RAG literature tools (Semantic Scholar, Elicit, Research Rabbit — not disease-specific pipelines)  
- Open Targets Platform, ClinicalTrials.gov API consumers  
- Vitiligo-specific reviews and trial landscapes (narrative, not executable engines)  
- Knowledge graphs in drug repurposing (general; rarely vitiligo-focused + trial-linked)  

### 1.3 Objectives
1. Reproducible multi-source vitiligo corpus  
2. Semantic retrieval with evidence-level metadata  
3. Cited Q&A constrained to retrieved documents  
4. Hypothesis reports integrating four evidence streams  
5. Public deployability (EU-aware hosting) with governance guardrails  

### 1.4 Non-claims
- Not SaMD / not diagnostic  
- Not a substitute for systematic review  
- LLM outputs require human expert review  

---

## 2. Methods (~2,500 words)

### 2.1 System overview
- Reference architecture diagram from [`architecture.md`](architecture.md)  
- Design principles: small swappable layers, idempotent ingestion, source-agnostic schema, open licenses  

### 2.2 Document corpus

| Source | Module | Identifier | Records (local) |
|--------|--------|------------|-----------------|
| PubMed | `vitiligo.sources.pubmed` | PMID | 11,356 |
| PMC OA | `vitiligo.sources.pmc` | PMCID | 2,578 |
| GEO DataSets | `vitiligo.sources.geo` | GSE | 311 |

- Query strategy for PubMed (vitiligo MeSH + text; year-bisection for >9,999 cap)  
- PMC JATS section parsing  
- GEO esearch + esummary metadata fields stored  
- `ingestion_runs` audit table  

### 2.3 Clinical trial harmonization

| Registry | Module | Records |
|----------|--------|---------|
| ClinicalTrials.gov v2 | `ctgov` | 320 |
| EU CTR (CTIS) | `euctr` | 22 |
| WHO ICTRP (XML) | `ictrp` | 2 |

- Canonical status / phase normalization  
- Dedup across registries by NCT / cross-refs  
- Trial schema: interventions, sponsors, countries, eligibility, outcomes  

### 2.4 Genetic and pharmacological priors

- Open Targets GraphQL (`EFO_0004208`): 237 drug/target priors  
- DrugBank XML (academic license): mechanism enrichment, vitiligo text filter  
- `priors` table schema  

### 2.5 Embeddings and retrieval

- Model: `BAAI/bge-small-en-v1.5` via fastembed (ONNX)  
- Scope: `title_abstract` (14,242 vectors)  
- Brute-force cosine over normalized vectors — latency acceptable at current scale  
- Future: hybrid BM25 + vector (acknowledge in limitations)  

### 2.6 Evidence-level classification

- Rule-based classifier on PubMed publication types, MeSH, title cues  
- Trial study_type → clinical_trial vs observational  
- Surfaced in search, API, UI, and LLM prompts  

### 2.7 Knowledge graph v1

- Entity kinds: disease, drug, target, intervention, trial  
- Predicates: `treats`, `investigates`, `associated_with`, `tested_in`, `inhibits`, …  
- **Seed path (production):** deterministic edges from priors + trial interventions → vitiligo  
- **Optional enrichment:** LLM extraction from abstracts (`vitiligo graph extract`) — not used for v1 production stats  
- Export: JSON snapshot for expert review (`vitiligo graph export`)  
- Automated invariant checks: `scripts/review/graph-spotcheck.sh`  

### 2.8 Reasoning layer

**Ask (RAG):**
- Retrieve top-K papers → prompt Claude with excerpts only  
- Bracketed numeric citations; refuse when evidence thin  

**Hypothesize:**
- Parallel retrieval: papers, trials, priors, graph neighbors  
- Structured JSON output: candidates with mechanism, evidence strength, risks, four citation streams `[n]`, `[Tn]`, `[Pn]`, `[Gn]`  
- Model: `claude-sonnet-4-5` (configurable)  

### 2.9 Web application and deployment

- FastAPI + static UI (Search / Ask / Hypothesize / Graph / Trials)  
- Rate limiting; health endpoint with corpus stats  
- Privacy / Terms / disclaimer (beta)  
- Fly.io Amsterdam region; persistent volume for SQLite  
- Docker image; `scripts/deploy/fly-deploy-all.sh`  

### 2.10 Evaluation plan (to execute before submission)

| Evaluation | Description | Status |
|------------|-------------|--------|
| **Corpus completeness** | Compare trial count vs manual CT.gov search | Planned |
| **Retrieval precision@K** | 20 expert-written queries; manual relevance labels | Planned |
| **Ask faithfulness** | Citation support score on 30 Q&A pairs (advisor-labeled) | Planned |
| **Hypothesize usefulness** | Advisor rates top-5 candidates for 5 intents (1–5 Likert) | Planned |
| **Graph precision** | Advisor flags incorrect edges in export sample | In progress (spot-check script) |
| **Reproducibility** | Fresh ingest + embed from public APIs on clean machine | Planned |

---

## 3. Results (~1,000 words)

### 3.1 Corpus statistics
- Table from Section 2 (documents, embeddings, trials, priors, graph)  
- Ingestion runtime benchmarks (CPU, approximate wall clock per source)  

### 3.2 Example queries (illustrative, not cherry-picked without advisor sign-off)
1. Search: *JAK inhibitors repigmentation non-segmental vitiligo*  
2. Ask: *Evidence for ruxolitinib + NB-UVB combination?*  
3. Hypothesize: *Stop spread of active non-segmental vitiligo*  
4. Graph: ruxolitinib → vitiligo neighborhood  

### 3.3 Graph seed quality
- Spot-check script results  
- Advisor review summary (after KOL meeting)  

### 3.4 Limitations
- Abstract-heavy retrieval (PMC full-text chunk embeddings pending)  
- No hybrid BM25 yet  
- LLM synthesis risk; English-centric corpus  
- DrugBank / ICTRP require manual XML exports  
- Graph seed reflects structured priors/trials, not full literature extraction  

---

## 4. Discussion (~600 words)

- Utility for researchers vs clinicians (research tool framing)  
- Comparison to manual systematic review workflow  
- Roadmap: GEO re-analysis, validation partnerships, registry IRB  
- Ethical deployment: disclaimers, advisor gate, open licensing  

---

## 5. Data and code availability

- GitHub: `recepsirin/vitiligo-initiative` (Apache 2.0)  
- Public URL: `https://vitiligo-evidence-engine.fly.dev` (post-deploy)  
- Graph export + ingestion run logs (no patient data)  
- Zenodo DOI: *to mint at first release*  
- Anthropic API required for Ask/Hypothesize (not bundled)  

---

## 6. Author contributions (template)

| Author | Contribution |
|--------|--------------|
| [Founder] | Concept, engineering, corpus curation |
| [Advisor] | Clinical validation, graph review |
| … | … |

---

## 7. Competing interests / funding

- TBD; advisor COI statements collected per [`governance-ethics-brief.md`](governance-ethics-brief.md)  

---

## Figures (planned)

1. **Fig 1** — System architecture (five layers + web UI)  
2. **Fig 2** — Hypothesize four-stream evidence flow  
3. **Fig 3** — Knowledge graph schema + example neighborhood (ruxolitinib / JAK1 / vitiligo)  
4. **Fig 4** — Screenshot montage: Search, Ask citations, Hypothesize output, Trials filter  

---

## Tables (planned)

1. Corpus sources and record counts  
2. Graph entity kinds and edge predicates  
3. Evidence-level taxonomy  
4. Evaluation metrics (post-advisor study)  

---

## Timeline to submission

| Week | Milestone |
|------|-----------|
| W0 | Public deploy live; advisor meeting |
| W1–2 | Advisor graph review + 30-query evaluation set |
| W3 | Draft full methods text from this outline |
| W4 | Internal read-through; Zenodo snapshot |
| W5 | medRxiv preprint + GitHub release tag `v1.0.0-paper` |

---

## Immediate writing tasks

- [ ] Finalize author list and affiliations  
- [ ] Run evaluation set (retrieval + Ask faithfulness)  
- [ ] Export Fig 1 from Mermaid in [`architecture.md`](architecture.md) for preprint (GitHub renders in-repo)  
- [ ] Add 2–3 paragraphs on EU CTR vitiligo Phase 3 trials (ruxolitinib, povorcitinib, upadacitinib) as motivating example  
- [ ] Legal review of Privacy/Terms before citing public URL in preprint  

---

*Outline for internal use. Expand into full manuscript after KOL feedback and deploy verification.*
