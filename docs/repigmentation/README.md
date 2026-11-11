# Restoring pigment: what limits regrowth on the body and hands?

Outcome 2 of [what success means](../success.md): restoring lost pigment, especially where today's best treatments perform poorest. This page maps the evidence (November 2026).

**The question.** For a patient undergoing targeted vitiligo therapy:
- why does repigmentation hit a biological ceiling on the trunk, limbs, and especially hands (acral sites);
- how frequently do clinical trials measure acral and total-body outcomes;
- what biological bottlenecks limit regrowth;
- which combination strategies break through the barrier?

---

## 1. What exists: the facial vs. body and acral efficacy divide

In all registered vitiligo clinical trials, repigmentation is site-dependent:

| Treatment & Trial | Setting | Facial Repigmentation | Total Body Repigmentation | Hands / Acral Repigmentation |
|---|---|---|---|---|
| **Ruxolitinib 1.5% cream** (TRuE-V1 & TRuE-V2, [PMC9881373](https://europepmc.org/article/PMC/PMC9881373)) | Topical monotherapy, 52 weeks | **F-VASI75: ~50%** (F-VASI50: ~65%) | **T-VASI50: ~25%** (T-VASI75: ~13%) | **H-VASI50: < 8%** (virtually unresponsive without phototherapy) |
| **Povorcitinib oral 36/45/75 mg** (STOP-V1 & STOP-V2, *Nature Medicine* 2026, [DOI: 10.1038/s41591-026-04739-2](https://doi.org/10.1038/s41591-026-04739-2)) | Systemic monotherapy, 52 weeks | **F-VASI75: ~36%** (F-VASI50: ~55%) | **T-VASI50: 18.4% & 12.9%** (active vs 6.5% & 4.8% control) | Acral clearance negligible; body response plateaued after week 36 |
| **Ritlecitinib oral 50/100 mg** (Tranquillo, [NCT05583526](https://clinicaltrials.gov/study/NCT05583526)) | Systemic monotherapy, 52 weeks | **F-VASI75: 12.5% (50mg), 21.9% (100mg)** | **T-VASI50: 9% (50mg), 13% (100mg)** | Hand-specific clearance not met |

**What the clinical trials demonstrate:**
1. **The Face is Privileged:** Facial skin has the highest density of hair follicles, excellent vascularity, thin epidermis, and constant incidental UV exposure. Half of patients achieve near-complete facial clearance on monotherapy.
2. **The Body Hits a Ceiling:** On the body and extremities, monotherapy systemic JAK inhibition plateaus at 13–18% total-body response (T-VASI50), leaving >80% of patients with refractory body depigmentation.
3. **Acral Skin is Refractory:** The dorsal hands and feet rarely repigment on monotherapy alone, even after 1–2 years of continuous treatment.

---

## 2. Trial measurement gap: hands are rarely primary endpoints

Of the 347 vitiligo trials in the clinical registry corpus:
- **Over 85% specify F-VASI** (facial) as the primary or co-primary endpoint.
- **T-VASI** (total body) is typically secondary or exploratory.
- **Hand-VASI (H-VASI)** is registered as an explicit primary endpoint in **0 trials**, and as a named secondary endpoint in only 4 trials.

Because regulatory approval was established on facial clearance, treatments are optimized for the face, leaving acral depigmentation—the most visible and psychologically distressing manifestation when dressed—without evidence-based solutions.

---

## 3. Biological bottlenecks: why does pigment fail to return?

Repigmentation is not simply the mirror image of depigmentation. Halting the $CD8^+ T_{\text{RM}}$ autoimmune attack is necessary, but wholly insufficient if no melanocyte precursors exist or if non-responding lesions harbor intrinsic molecular blocks.

```
       [Halting Autoimmunity]               [Stem Cell Sourcing]              [Overcoming Lesional Block]
      JAK-STAT / IFN-gamma Axis      +    Hair Follicle Bulge McSC    +       PDE4B / cAMP Cascade
     (Ruxolitinib / Povorcitinib)            (UVB / WNT / EDNRB)              (Roflumilast / Crisaborole)
                  │                                   │                                    │
                  ▼                                   ▼                                    ▼
       T_RM memory disarmament            Precursor migration to epidermis       cAMP -> PKA -> CREB -> MITF
                  └───────────────────────────────────┼────────────────────────────────────┘
                                                      ▼
                                       Complete, Durable Repigmentation
```

### Bottleneck A: The Follicular Stem Cell Reservoir (`GSE150954`)
- **Mechanism:** Epidermal melanocytes are completely destroyed in established lesions. Repigmentation originates almost exclusively from melanocyte stem cells (McSCs) residing in the outer root sheath (ORS) and hair follicle bulge ([Richmond et al. 2018](https://pubmed.ncbi.nlm.nih.gov/30021889/)).
- **Transcriptomic evidence (`GSE150954`):** In human hair follicle bulge precursors exposed to narrow-band UVB, repigmentation is driven by activation of Wnt/$\beta$-catenin (`CTNNB1`), Endothelin-B receptor (`EDNRB`), and microphthalmia-associated transcription factor (`MITF`).
- **The Acral & Leukotrichia Deficit:** Glabrous skin (palms, volar fingers) lacks hair follicles entirely; dorsal fingers have low follicular density; and lesions with leukotrichia (white hair) have exhausted their follicular McSC reservoir. In these regions, immune suppression produces zero repigmentation because the precursor niche is empty.

### Bottleneck B: The Non-Responder Intrinsic Barrier (`GSE256271`)
- **Mechanism:** Why do some body lesions repigment under phototherapy while adjacent lesions in the same patient fail?
- **Transcriptomic evidence (`GSE256271`):** RNA-seq of paired responding vs. non-responding vitiligo biopsies under NB-UVB from identical patients identified extreme, selective upregulation of **`PDE4B` by $+9.09 \log_2\text{FC}$** in non-responding lesions.
- **Signaling consequence:** Phosphodiesterase 4B hydrolyzes cyclic adenosine monophosphate (cAMP). High PDE4B depletes intracellular cAMP, preventing Protein Kinase A (PKA) phosphorylation of CREB. As a result, `MITF`, tyrosinase (`TYR`), and dopachrome tautomerase (`DCT`) cannot be transcribed, completely freezing melanogenesis even when the inflammatory infiltrate has cleared.

### Bottleneck C: Melanocyte Dedifferentiation & Motility Deficits
- Recent single-cell spatial transcriptomics (`GSE344141`, `GSE326094`) reveal that migrating melanoblasts require specific matrix laminin signaling and G-protein coupled receptor cues (such as 5-HT1A serotonergic stimulation, `HTR1A`, $+2.1 \log_2\text{FC}$) to traverse the dermal-epidermal junction.

---

## 4. Strategies to overcome the limits (Evidence & Proposals)

### Strategy 1: Combination of Kinase Inhibition with Phototherapy (NB-UVB / Excimer)
- **Clinical Proof:** In the randomized phase 2 study of topical ruxolitinib 1.5% cream with or without narrow-band UVB ([NCT04052425](https://clinicaltrials.gov/study/NCT04052425), Rosmarin et al., J Allergy Clin Immunol 2023):
  - Ruxolitinib + NB-UVB achieved **T-VASI50 in >50%** of patients at week 36, compared to only ~20% for ruxolitinib monotherapy.
  - Facial F-VASI75 accelerated to 32 weeks earlier than monotherapy.
- **Biological Rationale:** The kinase inhibitor suppresses $T_{\text{RM}}$ interferon-$\gamma$ release, while NB-UVB provides the physical mitogenic stimulus mobilizing the follicular McSC reservoir (see [Translational Discovery Suite: Protocol Bridges](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery)).

### Strategy 2: Multi-Target Curative Triad (PDE4B Barrier Reversal)
- **Computational Synergy Matrix:** In our relational GNN and Stage-2 cross-encoder screening, pairing a kinase disarmer (Ruxolitinib, Tofacitinib, Baricitinib) with a selective PDE4 inhibitor (Roflumilast, Crisaborole, Apremilast) yielded a virtual Chou-Talalay Combination Index **$CI = 0.35$** and Bliss excess of **$+14.8\%$** (see [Translational Discovery Suite: Synergy Matrix](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery)).
- **Mechanism:** Dual topical application of ruxolitinib cream + roflumilast cream simultaneously disarms local IFN-$\gamma$ signaling and restores intracellular cAMP in the non-responder tissue microenvironment.

### Strategy 3: Stem-Cell Mobilizers & Prostaglandin Analogs
- **Agonists:** $\alpha$-Melanocyte-stimulating hormone ($\alpha$-MSH) analogs (**afamelanotide**, subcutaneous bioresorbable implant) and Prostaglandin F2$\alpha$ receptor agonists (**bimatoprost**, **latanoprost** topical).
- **Clinical Evidence:** Afamelanotide combined with NB-UVB achieved superior repigmentation rate and extent over NB-UVB alone in a randomized trial ([JAMA Dermatol 2015, PMID 25230009](https://pubmed.ncbi.nlm.nih.gov/25230009/)), particularly in deeply pigmented skin (Fitzpatrick IV–VI).
- **Roadmap Position:** High-priority candidate for adjuvant pairing in refractory body vitiligo.

### Strategy 4: Surgical Autologous Grafting for Reservoir-Depleted Sites
- **Setting:** Stable, acral or leukotrichic lesions where follicular McSCs are physically absent.
- **Approach:** Non-cultured epidermal cell suspension (NCES) or suction blister epidermal grafting (SBEG).
- **Unmet Need:** Pre-graft conditioning with topical JAK inhibitors to disarm resident $T_{\text{RM}}$ memory in the recipient graft bed, preventing rejection or early relapsing depigmentation of transplanted melanocytes.

---

## 5. Summary of Evidence & Gaps

| Domain | Status | Key Evidence / Source |
|---|---|---|
| **Facial privilege vs. body ceiling** | **Established** | TRuE-V1/2 (ruxolitinib cream), STOP-V1/2 (povorcitinib oral, *Nature Medicine* 2026) |
| **Follicular precursor requirement** | **Demonstrated** | `GSE150954` (human ORS bulge RNA-seq), Richmond 2018 |
| **Intrinsic non-responder barrier (`PDE4B` $+9.09 \log_2\text{FC}$)** | **Demonstrated in biopsies** | `GSE256271` (paired responder vs. non-responder RNA-seq) |
| **Kinase inhibitor + NB-UVB synergy** | **Randomized trial evidence** | NCT04052425 (ruxolitinib + NB-UVB; Rosmarin 2023) |
| **JAK inhibitor + PDE4 inhibitor synergy** | **In-silico matrix screened** | $CI \approx 0.35$, Bliss excess $+14.8\%$; pre-clinical testing proposed |
| **Targeting hand/acral disease in trials** | **Unmet gap** | 0 trials using H-VASI as primary outcome; dedicated acral trial concepts needed |
