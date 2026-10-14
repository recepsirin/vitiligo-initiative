# Scientific Brief — Vitiligo State of the Art

**Status:** Draft v0.1 (May 2026)  
**Audience:** Advisors, collaborators, funders  
**Purpose:** Current disease biology, treatments and evidence gaps, as the scientific basis for the initiative.

---

## Executive summary

Vitiligo is an autoimmune disease characterized by loss of epidermal melanocytes, leading to depigmented macules and patches. For most patients the priority is twofold: **stop active spread** (especially in non-segmental vitiligo, NSV) and **restore pigment** on cosmetically and functionally important sites (face, hands, genitals).

The field has moved rapidly since ~2020: the **IFN-γ / CXCL10 / JAK–STAT axis** is now the dominant mechanistic frame for NSV, and **topical ruxolitinib** is approved in the US for NSV. Multiple **oral and topical JAK inhibitors** are in Phase 2–3. NB-UVB and topical corticosteroids remain first-line in many guidelines, but sequencing, combination, durability, and segmental vs non-segmental subtypes remain poorly standardized.

The initiative's tools (see the [README](../README.md)) are built to speed up evidence synthesis and hypothesis ranking, not to replace clinical judgment or peer review.

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
7. **Omics → target** — public GEO series exist; no systematic re-analysis yet.  

Durability, combination and sequencing (gaps 1 and 3) are what the JAK atlas, scenario model and sealed forecasts address first.

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
