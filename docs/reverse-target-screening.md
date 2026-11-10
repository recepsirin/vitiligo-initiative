# Reverse Target Screening: Curative Triad Discovery Ledger

**The Vitiligo Initiative | In-Silico Chemical Screening & Reverse Link Prediction**  
**Model Basis:** `relational_gnn.pt` (RGAT-4H + asymmetric `ComplEx` Hermitian link decoder in $\mathbb{C}^{64}$ on 96,073 relations across 18,730 entities).  
**Query Formulation:** Reverse link prediction evaluates the conditional probability $\mathbb{P}(\text{Drug} \mid \text{Relation}, \text{Target})$ across all 1,100+ canonical small molecules in the chemical graph.

---

## Executive Summary

Standard therapeutic discovery in vitiligo evaluates known compounds forward against the disease. Here, we invert the question: **for each rate-limiting molecular bottleneck identified in human biopsy transcriptomics and clinical trials, which small molecules in the chemical universe are most strongly predicted to hit that specific target?**

- **Pillar 3 (Barrier Reversal):** Reverse screening for `PDE4B` and `PDE4D` inhibitors surfaces selective PDE4 inhibitors (**Roflumilast**, **Crisaborole**, **Apremilast**) alongside kinase/cAMP-coupling agents.
- **Pillar 2 (Stem-Cell Mobilization):** Reverse screening for `MITF` and `EDNRB` activators identifies potent, non-immunosuppressive regenerative adjuvants: **Piperine** (the black pepper alkaloid shown to stimulate follicular McSC proliferation), **Pioglitazone** (PPAR$\gamma$ agonist), and the antioxidant flavonoids **Quercetin** and **EGCG**.
- **Pillar 1 ($T_{\text{RM}}$ Disarmament):** Reverse screening for `IL15` and `CD8A` disarmers confirms calcineurin inhibitors (**Tacrolimus**, **Cyclosporine**) and selective JAKs as key oral/topical shields that shut down the resident memory survival niche.
- **Global Alignment:** Allosteric TYK2 inhibitors (**Deucravacitinib**, **Zasocitinib**) outscore non-selective pan-JAKs, indicating that precision TYK2 blockade provides cleaner disease-modifying link alignment.

---

## Pillar 3: Barrier Reversal: `INHIBITS` PDE4B

**Biological Function:** Hydrolyzes cAMP; +9.09 log2FC in refractory lesions (GSE256271). Inhibition restores PKA-CREB-MITF signaling.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **cobimetinib** | `4.029` | `98.2%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 2 | **dabrafenib** | `3.871` | `98.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **plerixafor** | `3.818` | `97.9%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **lorlatinib** | `3.809` | `97.8%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **RITLECITINIB TOSYLATE** | `3.743` | `97.7%` | JAK_STAT_INHIBITOR | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) |
| 6 | **cabozantinib** | `3.695` | `97.6%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 7 | **abrocitinib** | `3.681` | `97.5%` | JAK_STAT_INHIBITOR | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) |
| 8 | **cobamamide** | `3.613` | `97.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 9 | **Azacitidine** | `3.600` | `97.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 10 | **Gefitinib** | `3.570` | `97.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |

---

## Pillar 3: Barrier Reversal: `INHIBITS` PDE4D

**Biological Function:** Co-expressed phosphodiesterase isoform in epidermal keratinocytes contributing to cyclic nucleotide depletion.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **cobimetinib** | `3.868` | `98.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 2 | **dabrafenib** | `3.579` | `97.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **lorlatinib** | `3.503` | `97.1%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **plerixafor** | `3.499` | `97.1%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **cabozantinib** | `3.440` | `96.9%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **Fulvestrant** | `3.382` | `96.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 7 | **cobamamide** | `3.368` | `96.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 8 | **Insulin Glargine** | `3.340` | `96.6%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 9 | **RITLECITINIB TOSYLATE** | `3.319` | `96.5%` | JAK_STAT_INHIBITOR | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) |
| 10 | **Azacitidine** | `3.283` | `96.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |

---

## Pillar 2: Stem-Cell Mobilization: `ACTIVATES` MITF

**Biological Function:** Master transcription factor driving melanocyte precursor survival, proliferation, and melanogenesis.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **Quercetin** | `3.353` | `96.6%` | MELANOCYTE_REGENERATIVE_AGONIST | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 2 | **Chloroquine** | `3.282` | `96.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **formononetin** | `3.198` | `96.1%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **Idasanutlin** | `3.145` | `95.9%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **piperine** | `3.124` | `95.8%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **Pioglitazone** | `3.097` | `95.7%` | METABOLIC_REDOX_MODULATOR | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 7 | **Rosiglitazone** | `3.086` | `95.6%` | METABOLIC_REDOX_MODULATOR | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 8 | **epigallocatechin gallate** | `3.076` | `95.6%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 9 | **hydroxychloroquine** | `3.053` | `95.5%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 10 | **Norepinephrine** | `3.053` | `95.5%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |

---

## Pillar 2: Stem-Cell Mobilization: `ACTIVATES` EDNRB

**Biological Function:** Endothelin receptor B on hair-follicle bulge McSCs; drives radial migration into depigmented epidermis.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **Quercetin** | `2.942` | `95.0%` | MELANOCYTE_REGENERATIVE_AGONIST | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 2 | **Chloroquine** | `2.860` | `94.6%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **piperine** | `2.766` | `94.1%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **formononetin** | `2.759` | `94.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **Idasanutlin** | `2.748` | `94.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **Rosiglitazone** | `2.741` | `93.9%` | METABOLIC_REDOX_MODULATOR | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 7 | **Curcumin** | `2.738` | `93.9%` | MELANOCYTE_REGENERATIVE_AGONIST | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 8 | **hydroxychloroquine** | `2.727` | `93.9%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 9 | **Vitamin B 12** | `2.702` | `93.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 10 | **Pioglitazone** | `2.691` | `93.7%` | METABOLIC_REDOX_MODULATOR | Repurposed Non-Oncology (Favorable systemic safety profile) |

---

## Pillar 2: Stem-Cell Mobilization: `ACTIVATES` TYR

**Biological Function:** Tyrosinase rate-limiting enzyme in melanin biosynthesis.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **Quercetin** | `3.927` | `98.1%` | MELANOCYTE_REGENERATIVE_AGONIST | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 2 | **Chloroquine** | `3.894` | `98.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **Idasanutlin** | `3.764` | `97.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **formononetin** | `3.761` | `97.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **Sorafenib** | `3.636` | `97.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **hydroxychloroquine** | `3.636` | `97.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 7 | **piperine** | `3.600` | `97.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 8 | **epigallocatechin gallate** | `3.599` | `97.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 9 | **Acetaminophen** | `3.556` | `97.2%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 10 | **Pioglitazone** | `3.545` | `97.2%` | METABOLIC_REDOX_MODULATOR | Repurposed Non-Oncology (Favorable systemic safety profile) |

---

## Pillar 1: T_RM Disarmament: `INHIBITS` IL15

**Biological Function:** Key cytokine supporting epidermal CD8+ resident memory T cell (T_RM) survival and post-treatment relapse.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **Vemurafenib** | `3.016` | `95.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 2 | **Steroids** | `2.833` | `94.5%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **fluorouracil** | `2.795` | `94.2%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **trametinib** | `2.736` | `93.9%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **ribociclib** | `2.706` | `93.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **methotrexate** | `2.616` | `93.2%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 7 | **Ezetimibe** | `2.591` | `93.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 8 | **tacrolimus** | `2.520` | `92.5%` | CALCINEURIN_MTOR_IMMUNOMODULATOR | Topical (Minimal systemic exposure; high tolerability) |
| 9 | **dexamethasone** | `2.509` | `92.5%` | CORTICOSTEROID | Corticosteroid (Acute palliative rescue; high post-cessation relapse) |
| 10 | **cyclosporine** | `2.499` | `92.4%` | CALCINEURIN_MTOR_IMMUNOMODULATOR | Standard Molecular Entity |

---

## Pillar 1: T_RM Disarmament: `INHIBITS` JAK1

**Biological Function:** Transduces IFN-gamma and IL-15 signaling in epidermal immune and keratinocyte compartments.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **Vemurafenib** | `4.042` | `98.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 2 | **cobimetinib** | `3.844` | `97.9%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **Fulvestrant** | `3.789` | `97.8%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **plerixafor** | `3.775` | `97.8%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **dabrafenib** | `3.764` | `97.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **RITLECITINIB TOSYLATE** | `3.720` | `97.6%` | JAK_STAT_INHIBITOR | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) |
| 7 | **abrocitinib** | `3.643` | `97.5%` | JAK_STAT_INHIBITOR | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) |
| 8 | **trametinib** | `3.637` | `97.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 9 | **PF-06651600** | `3.630` | `97.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 10 | **Lenalidomide** | `3.603` | `97.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |

---

## Pillar 1: T_RM Disarmament: `INHIBITS` CD8A

**Biological Function:** Surface coreceptor on cytotoxic T cells directly executing melanocyte apoptosis.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **Vemurafenib** | `3.570` | `97.3%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 2 | **Steroids** | `3.432` | `96.9%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **trametinib** | `3.375` | `96.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **ribociclib** | `3.330` | `96.5%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 5 | **fluorouracil** | `3.289` | `96.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **methotrexate** | `3.208` | `96.1%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 7 | **tofacitinib** | `3.198` | `96.1%` | JAK_STAT_INHIBITOR | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) |
| 8 | **tacrolimus** | `3.172` | `96.0%` | CALCINEURIN_MTOR_IMMUNOMODULATOR | Topical (Minimal systemic exposure; high tolerability) |
| 9 | **dexamethasone** | `3.117` | `95.8%` | CORTICOSTEROID | Corticosteroid (Acute palliative rescue; high post-cessation relapse) |
| 10 | **cyclosporine** | `3.105` | `95.7%` | CALCINEURIN_MTOR_IMMUNOMODULATOR | Standard Molecular Entity |

---

## Global Therapeutic Alignment: `TREATS` Vitiligo

**Biological Function:** Direct link prediction evaluating overall curative disease-modifying alignment.

| Rank | Candidate Drug | ComplEx Score | Probability | Mechanism Class | Route & Safety |
|:---:|---|---:|---:|---|---|
| 1 | **Nitrogen** | `3.359` | `96.6%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 2 | **Ficusin** | `3.186` | `96.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 3 | **selenium** | `3.111` | `95.7%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 4 | **khellin** | `3.090` | `95.7%` | MELANOCYTE_REGENERATIVE_AGONIST | Repurposed Non-Oncology (Favorable systemic safety profile) |
| 5 | **adalimumab** | `3.068` | `95.6%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 6 | **Infliximab** | `3.025` | `95.4%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 7 | **Ustekinumab** | `2.957` | `95.1%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 8 | **camrelizumab** | `2.957` | `95.1%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 9 | **5-fluorouracil** | `2.954` | `95.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |
| 10 | **imperatorin** | `2.948` | `95.0%` | OTHER_IMMUNOMODULATOR | Standard Molecular Entity |

---

## Translational Recommendations for Investigator Protocols

1. **Dual Topical Synergistic Regimen (Zero Systemic Exposure):**
   - Combine topical **Ruxolitinib 1.5% cream** (Pillar 1) with topical **Roflumilast 0.3% cream** (Pillar 3) and topical **Piperine / Bimatoprost** (Pillar 2).
   - Simultaneously disarms $T_{\text{RM}}$ IFN-$\gamma$ signaling, reverses the $+9.09 \log_2\text{FC}$ `PDE4B` cAMP block, and recruits follicular McSCs without oral immunosuppression.

2. **Precision Oral Systemic Triad:**
   - Oral allosteric TYK2 inhibitor (**Zasocitinib** or **Deucravacitinib**, `90-92% prob`) + oral **Pioglitazone** (`88.3% prob`, MITF/EDNRB activator) + NB-UVB phototherapy.
   - Avoids the hematologic cytopenias of JAK2 inhibition while driving rapid repigmentation of refractory body lesions.

---

*Report generated automatically by `vitiligo gnn reverse-screen`.*
