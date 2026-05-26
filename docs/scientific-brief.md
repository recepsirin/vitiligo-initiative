# Scientific Brief — Vitiligo State of the Art

**Status:** Draft v0.1 (May 2026)  
**Audience:** Advisors, collaborators, funders  
**Purpose:** Ground the Vitiligo Initiative in current disease biology, treatment landscape, and evidence gaps — and show how the Evidence Engine maps to them.

---

## Executive summary

Vitiligo is an autoimmune disease characterized by loss of epidermal melanocytes, leading to depigmented macules and patches. For most patients the priority is twofold: **stop active spread** (especially in non-segmental vitiligo, NSV) and **restore pigment** on cosmetically and functionally important sites (face, hands, genitals).

The field has moved rapidly since ~2020: the **IFN-γ / CXCL10 / JAK–STAT axis** is now the dominant mechanistic frame for NSV, and **topical ruxolitinib** is approved in the US for NSV. Multiple **oral and topical JAK inhibitors** are in Phase 2–3. NB-UVB and topical corticosteroids remain first-line in many guidelines, but sequencing, combination, durability, and segmental vs non-segmental subtypes remain poorly standardized.

The Vitiligo Initiative Evidence Engine (v1.0) ingests and links this literature and trial landscape: **14,245 documents**, **344 registered trials**, **237 Open Targets priors**, and a **1,044-node knowledge graph** seeded from priors and trials. It is designed to accelerate **evidence synthesis and hypothesis ranking**, not to replace clinical judgment or peer review.

---

## Disease overview

### Subtypes

| Subtype | Approx. share | Course | Notes |
|---------|---------------|--------|-------|
| **Non-segmental vitiligo (NSV)** | ~85–90% | Often progressive, bilateral, autoimmune | Primary target for systemic and topical JAK programs |
| **Segmental vitiligo (SV)** | ~10–15% | Often stable after initial spread | Different pathophysiology (suggested neurogenic / local immune); fewer large trials |
| **Mixed / focal variants** | Minority | Overlap phenotypes | Evidence often pooled in trials — a known limitation |

### Core biology (working model)

1. **Melanocyte stress** → danger signals and antigen release  
2. **Adaptive immunity** → autoreactive CD8⁺ T cells in lesional skin  
3. **IFN-γ signaling** → JAK1/JAK2 → STAT1 → **CXCL10** recruitment loop  
4. **Melanocyte destruction** → clinical depigmentation  

Other axes remain active research areas: innate immunity, oxidative stress, microbiome, neural factors (especially SV), and genetics (PTPN22, NLRP1, etc.).

### What “success” means clinically

- **Spread arrest** — no new lesions / VASI activity score stable or improving  
- **Repigmentation** — often graded by **VASI**, **T-VASI**, **F-VASI**, or **Patient Global Assessment**  
- **Durability** — relapse after treatment stop is common; maintenance strategies are understudied  
- **Site difficulty** — acral (hands/feet) and leukotrichic vitiligo repigment poorly  

The initiative’s design goal aligns with these endpoints: candidates and combinations should be ranked by plausible effect on **spread control** and **repigmentation**, with explicit evidence level.

---

## Current treatment landscape

### Established / guideline-supported

| Modality | Role | Evidence level | Limitations |
|----------|------|----------------|-------------|
| **Topical corticosteroids / calcineurin inhibitors** | First-line topical | RCTs, long use | Skin atrophy, incomplete response, not durable alone |
| **NB-UVB phototherapy** | First-line for widespread NSV | Multiple RCTs | Access, time burden, variable response, acral sites |
| **Combination topical + phototherapy** | Common practice | Mixed RCT / observational | Optimal sequencing not settled |
| **Depigmentation** | Extensive refractory NSV | Established option | Irreversible; niche |

### Emerging / approved (JAK pathway)

| Agent | Route | Stage (vitiligo) | Notes |
|-------|-------|------------------|-------|
| **Ruxolitinib cream** | Topical | **Approved (US)** for NSV | Phase 3 data; EU Phase 3 active in corpus |
| **Povorcitinib** | Oral | Phase 3 | Incyte; NSV programs in EU CTR + CT.gov |
| **Upadacitinib** | Oral | Phase 3 | AbbVie; active EU trials |
| **Ritlecitinib** | Oral | Phase 3 | Pfizer |
| **Topical ruxolitinib variants** | Topical | Multiple trial arms | Dose/formulation comparisons in registry |

*Source in engine:* Open Targets disease `EFO_0004208`, EU CTR, ClinicalTrials.gov — 37 drug-stage priors ingested.

### Repurposing and older candidates in corpus

The priors and trial registry also surface: **methotrexate**, **afamelanotide**, **tacrolimus**, **excimer laser**, **microneedling + topical**, **stem cell / melanocyte transplant** protocols, and numerous device / procedural studies.

---

## Evidence gaps (where the initiative can add value)

1. **Combination and sequencing** — JAK + NB-UVB, JAK + topical steroid, maintenance after induction; ranked by mechanistic rationale + trial readouts.  
2. **Subtype-specific evidence** — SV and mixed vitiligo underrepresented in registrational trials.  
3. **Durability and relapse** — short follow-up in many studies; real-world evidence scarce.  
4. **Biomarkers of response** — transcriptomic signatures (IFN response, melanocyte survival) not yet clinical tools.  
5. **Acral / recalcitrant sites** — high unmet need; few positive Phase 3 readouts.  
6. **Safety tradeoffs** — systemic JAK class effects vs topical; long-term vitiligo-specific safety databases immature.  
7. **Omics → target** — hundreds of GEO series now in corpus (311 vitiligo-linked GSE records); systematic re-analysis not yet published by this initiative.  

These gaps directly feed the **Hypothesize** and future **Candidate Hypothesis Reports** artifacts.

---

## What the Evidence Engine contains (May 2026)

| Layer | Count | Use |
|-------|-------|-----|
| PubMed abstracts | 11,356 | Semantic search, Ask, Hypothesize |
| PMC full text | 2,578 | Deeper methods/results context |
| GEO series metadata | 311 | Omics discovery queue |
| Clinical trials | 344 (CT.gov 320, EU CTR 22, ICTRP 2) | Trial stream in Hypothesize; Trials tab |
| Open Targets priors | 237 drugs/targets | Prior stream; graph seed |
| Embeddings | 14,242 | `BAAI/bge-small-en-v1.5` |
| Knowledge graph | 1,044 entities, 1,643 edges | Graph tab; `[Gn]` citations |

Graph predicates (seed): `treats`, `investigates`, `associated_with`, `tested_in`, `inhibits`, `targets`, etc.

---

## How we use this scientifically

### What the engine does

- Retrieves and cites **primary literature and registry records**  
- Ranks **therapeutic hypotheses** with separate evidence streams (papers, trials, priors, graph)  
- Surfaces **evidence level** (RCT, meta-analysis, preclinical, trial phase)  
- Maintains a **reproducible, versioned corpus** (SQLite + exportable graph JSON)  

### What the engine does not do

- Does not diagnose or prescribe  
- Does not replace systematic review or meta-analysis for regulatory claims  
- Does not guarantee correctness of LLM synthesis — human expert review required before clinical or publication use  
- Has not yet run large-scale LLM graph extraction over full corpus (optional `vitiligo graph extract`; structured seed is current production path)  

### Near-term scientific outputs (Phase 1–2)

1. **Advisor-reviewed graph export** (`exports/graph-review.json`)  
2. **Top 5–10 candidate report** from Hypothesize + manual curation  
3. **Methods preprint** — corpus construction, graph schema, evaluation approach  
4. **GEO re-analysis pilot** — IFN/JAK axis vs responder signatures  

---

## Suggested reading (canonical entry points)

- Harris JE. Vitiligo and alopecia areata: apples and oranges? *Exp Dermatol* — shared JAK–IFN framing.  
- Rashighi M et al. CXCL10 is critical for IFN-γ–mediated autoreactivity in vitiligo. *Sci Transl Med*.  
- Rodrigues et al. Current and emerging therapies for vitiligo — review landscape.  
- FDA approval summary: Opzelura (ruxolitinib cream) for non-segmental vitiligo.  
- Open Targets Platform: vitiligo (`EFO_0004208`) association scores.  

*(Full bibliography to be maintained as a Zotero collection linked from the public site.)*

---

## Open scientific questions for advisors

1. Which **3–5 hypotheses** should we prioritize for first lab validation?  
2. Is **public Evidence Engine launch** acceptable before peer-reviewed methods paper, or should we run a **closed advisor beta** first?  
3. Minimum **graph quality bar** before citing graph relations in external materials?  
4. Preferred **outcome measures** for our first validation proposals (VASI vs activity scores vs transcriptomic surrogates)?  

---

*This brief is a living document. Corrections and additions from KOL review are expected before any external publication.*
