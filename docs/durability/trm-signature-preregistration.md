# Pre-Registration: Tissue-Resident Memory T Cell ($T_{\text{RM}}$) Relapse Signature

**The Vitiligo Initiative | Outcome 3: Last (Durability)**  
**Document ID:** `PREREG-TRM-2026-V1`  
**Status:** Pre-Registered & Computationally Sealed  
**Date:** November 2026  
**Hypothesis ID:** [`trm-il15-relapse`](../mechanisms/README.md)  
**Governing Documents:** [`docs/roadmap.md`](../roadmap.md) (Roadmap Item 3.6), [`docs/durability/README.md`](README.md), [`docs/durability/maintenance-trial-concept.md`](maintenance-trial-concept.md)

---

## 1. Scientific Rationale & Unmet Need

Approved topical and systemic kinase inhibitors (ruxolitinib, baricitinib, upadacitinib, povorcitinib) halt active inflammation and induce facial and body repigmentation. However, withdrawal of treatment leads to a **relapse rate of 34% to 40% within 12 months** (*PMID: 36721299*, *PMID: 42705066*).

### The Biological Engine of Relapse
Depigmentation recurs in the exact same anatomical locations because melanocyte-reactive $\text{CD8}^+$ T cells adopt a tissue-resident memory phenotype ($\text{CD8}^+ \text{CD103}^+ \text{CD69}^+ T_{\text{RM}}$) that remains permanently anchored at the dermal-epidermal junction. These cells are kept viable by keratinocyte-derived **Interleukin-15 ($\text{IL-15}$)** trans-presented via $\text{IL-15R}\alpha$ to the heterodimeric $\text{IL-2R}\beta/\gamma$ receptor on $T_{\text{RM}}$ cells (*Richmond et al., Sci Transl Med 2018, PMID: 30021889*).

### The Objective
To measure the immune memory, not only the pigment: derive a quantitative, reproducible **$T_{\text{RM}}$ Relapse Signature Score ($S_{\text{TRM}}$)** from public human and mouse vitiligo transcriptomes, freeze its exact gene weights prior to analyzing post-withdrawal clinical outcome data, and pre-register its falsifiable prediction rule.

---

## 2. Resolution of GSE203262 Suction Blister Barcodes

In October 2026, analysis of `GSE203262` (suction blister epidermal roofs from 6 stable vitiligo patients: `PtA`, `PtC`, `PtD`, `PtE`, `PtF`, `PtG`; *Shiu et al., JCI Insight 2022, PMC9310536*) was deemed blocked because individual sample matrices were aggregated without obvious barcode labels in the primary paper text.

### The Resolution
Inspection of the official NCBI GEO series matrix metadata header revealed that the depositors explicitly documented the barcoding aggregation convention in `!Sample_description`:
```text
!Sample_description "barcodes appended with '-1' are: non-lesional tissue"
!Sample_description "barcodes appended with '-2' are: lesional tissue"
```

### Orthogonal Biological Verification
We computationally evaluated all 20,550 cells across the 6 patients to verify whether `-1` and `-2` conform to vitiligo pathology:
1. **Interferon Response:** Lesional cells (`-2`) exhibit massive, consistent induction of key IFN-$\gamma$ chemokines compared to non-lesional cells (`-1`):
   - `CXCL9`: **$57.25\times$ enrichment** (mean $0.1935$ in LS vs $0.0034$ in NL).
   - `CXCL10`: **$50.65\times$ enrichment** (mean $0.6434$ in LS vs $0.0127$ in NL).
2. **Niche IL-15 Axis:** Keratinocyte-expressed `IL15` ($2.04\times$) and `IL15RA` ($2.03\times$) are doubled in lesional epidermis.
3. **Stressed Keratinocyte Program:** Markers identified by Shiu et al. (`KRT6A`, `KRT16`, `S100A8`, `S100A9`) show $2\times$ to $43\times$ elevation in `-2` across all patients.
4. **Intraepidermal T Cell Infiltration:** 87 T cells were identified in lesional epidermis compared to 36 in matched non-lesional skin ($2.4\times$ enrichment), with lesional T cells exhibiting marked induction of:
   - `CD69`: **$6.7\times$ elevation** ($0.7471$ vs $0.1111$, $20.7\%$ vs $8.3\%$ positive cells).
   - `ITGAE` (CD103): **$2.3\times$ elevation** ($0.5057$ vs $0.2222$, $31.0\%$ vs $13.9\%$ positive cells).
   - `GZMB` (Granzyme B): **$10.5\times$ elevation** ($0.8736$ vs $0.0833$).
   - `PRF1` (Perforin): **$4.1\times$ elevation** ($0.1149$ vs $0.0278$).
   - `S1PR1` / `CCR7`: **$0.0\%$ detected** (confirming absolute absence of recirculating lymph node homing programs).

---

## 3. Cross-Species Conserved $T_{\text{RM}}$ Gene Panel

To ensure that the signature reflects durable resident memory biology rather than transient transcriptional noise, the human vitiligo data were cross-referenced against mouse melanoma-associated vitiligo $T_{\text{RM}}$ single-cell sequencing (`GSE169238`, *Molodtsov et al., Sci Immunol 2021*), where 1,150 skin-clonotypic TCRs were tracked into draining lymph nodes:
- Mouse skin-clonotypic memory T cells express identical core retention markers: `Itgae` ($11.8\%$), `Cd69` ($55.8\%$), `Cxcr6` ($38.6\%$), `Il2rb` ($66.7\%$), and `Runx3` ($35.6\%$).

### The Sealed Gene Sets

#### A. Core $T_{\text{RM}}$ Retention and Effector Panel ($G_{\text{TRM}}^{+}$)
1. `CD8A` — Cytotoxic T lineage co-receptor $\alpha$
2. `CD8B` — Cytotoxic T lineage co-receptor $\beta$
3. `ITGAE` (CD103) — Integrin $\alpha_{\text{E}}$, anchors to E-cadherin on basal keratinocytes
4. `CD69` — Functional antagonist of S1PR1, blocks epidermal egress
5. `CXCR6` — Chemokine receptor for epidermal CXCL16
6. `IL2RB` (CD122) — $\beta$ chain of IL-15/IL-2 receptor (therapeutic antibody target)
7. `IL15RA` — IL-15 receptor $\alpha$, required for membrane trans-presentation
8. `GZMB` — Granzyme B cytolytic protease
9. `PRF1` — Perforin membrane pore-forming protein
10. `CXCL9` — IFN-$\gamma$ inducible chemokine recruiting CXCR3+ T cells
11. `CXCL10` — IFN-$\gamma$ inducible chemokine maintaining perilesional gradient

#### B. Circulating & Egress Panel ($G_{\text{circ}}^{-}$)
1. `CCR7` — Directs homing to lymph node T zones
2. `SELL` (CD62L) — L-selectin, peripheral lymph node homing
3. `S1PR1` — Sphingosine-1-phosphate receptor 1, required for tissue egress

#### C. Housekeeping Normalizers ($G_{\text{norm}}$)
1. `ACTB` — $\beta$-actin
2. `GAPDH` — Glyceraldehyde-3-phosphate dehydrogenase
3. `RPLP0` — Ribosomal protein lateral stalk subunit P0

---

## 4. Mathematical Formulation of the $T_{\text{RM}}$ Relapse Index ($S_{\text{TRM}}$)

For any skin biopsy, 1 mm punch biopsy, or bulk/pseudobulk RNA sequencing profile with expression values $E(g)$:

$$\bar{E}_{\text{TRM}} = \frac{1}{|G_{\text{TRM}}^{+}|} \sum_{g \in G_{\text{TRM}}^{+}} E(g)$$

$$\bar{E}_{\text{circ}} = \frac{1}{|G_{\text{circ}}^{-}|} \sum_{g \in G_{\text{circ}}^{-}} E(g)$$

$$\bar{E}_{\text{norm}} = \frac{1}{|G_{\text{norm}}|} \sum_{g \in G_{\text{norm}}} E(g)$$

The raw resident memory score is defined as:

$$S_{\text{raw}} = \log_2(1 + \bar{E}_{\text{TRM}}) - \log_2(1 + \bar{E}_{\text{circ}})$$

And the housekeeping-normalized Relapse Index is:

$$S_{\text{TRM}} = \frac{S_{\text{raw}}}{\max(\log_2(1 + \bar{E}_{\text{norm}}), \epsilon)}$$

*(where $\epsilon = 10^{-6}$ prevents zero-denominator artifacts).*

---

## 5. In-Sample Benchmark on GSE203262

Applying the locked formula across paired pseudobulk biopsies from all 6 patients in `GSE203262`:

| Patient | Non-Lesional Score $S_{\text{TRM}}(\text{NL})$ | Lesional Score $S_{\text{TRM}}(\text{LS})$ | $\Delta S_{\text{TRM}}$ (LS $-$ NL) | Outcome |
|---|---|---|---|---|
| **PtA** | 0.0068 | 0.0136 | $+0.0068$ | **LS > NL ($2.0\times$)** |
| **PtC** | 0.0108 | 0.0132 | $+0.0024$ | **LS > NL ($1.2\times$)** |
| **PtD** | 0.0147 | 0.0159 | $+0.0012$ | **LS > NL ($1.1\times$)** |
| **PtE** | 0.0217 | 0.0952 | $+0.0735$ | **LS > NL ($4.4\times$)** |
| **PtF** | 0.0054 | 0.0109 | $+0.0055$ | **LS > NL ($2.0\times$)** |
| **PtG** | 0.0078 | 0.0118 | $+0.0040$ | **LS > NL ($1.5\times$)** |

- **Empirical Consistency:** 6 of 6 patients exhibit $S_{\text{TRM}}(\text{LS}) > S_{\text{TRM}}(\text{NL})$.
- **Sign Test:** $P = 0.5^6 = 0.0156$ (statistically significant).
- **Wilcoxon Signed-Rank Test:** $W = 21.0, P = 0.03125$.

---

## 6. Pre-Registered Falsification Rules (The Prospective Test)

The signature $S_{\text{TRM}}$ is sealed and locked. It will be tested without modification against future clinical samples:

### The Experimental Context
- **Tissue:** 1 mm punch biopsies or suction blister roofs taken from **repigmented skin** at the exact moment treatment (topical ruxolitinib or oral JAKi) is stopped or tapered.
- **Trial Setting:** E.g., randomized stop-or-step-down maintenance trial (`docs/durability/maintenance-trial-concept.md`) or future public datasets sampling post-treatment withdrawal skin.

### Prediction & Decision Criteria
1. **If Correct (Hypothesis Supported):**
   - Higher $S_{\text{TRM}}$ at treatment cessation predicts **accelerated disease relapse** within 52 weeks:
     $$\text{Hazard Ratio per standard deviation } \text{HR}_{\text{SD}} > 1.0 \quad (\alpha = 0.05)$$
   - The memory hypothesis stands, supporting targeted IL-15 / CD122 consolidation therapies.
2. **If Incorrect (Hypothesis Refuted / Dropped):**
   - $\text{HR}_{\text{SD}} \le 1.0$ or no statistically significant association ($P \ge 0.05$).
   - If melanocyte density/stem cell exhaustion markers in the same biopsy predict relapse while $S_{\text{TRM}}$ does not, the memory hypothesis is formally refuted and dropped in favor of the melanocyte fragility model.

### Code & Reproduction
- Implementation: [`src/vitiligo/models/trm_score.py`](../../src/vitiligo/models/trm_score.py)
- Unit tests: [`tests/unit/test_trm_score.py`](../../tests/unit/test_trm_score.py)

---

## Amendments

1. **Correction, 2026-11-12, before any post-withdrawal sample has been scored.** The table in section 5 was not computed with the formula in section 4. Its twelve values are reproduced exactly by $\log_2(1 + \bar{E}_{\text{TRM}}) \,/\, \log_2(1 + \bar{E}_{\text{norm}})$ with $\bar{E}_{\text{norm}}$ taken over `ACTB` and `GAPDH` alone: the circulating term is missing, and `RPLP0` is left out of the normalizer. No committed version of [`trm_score.py`](../../src/vitiligo/models/trm_score.py) computes that; it has computed the formula in section 4 since it was first committed. The gene sets, the formula and the falsification rules are unchanged. This amendment corrects the figures, not the score.

   **What the sealed formula gives.**

   | Patient | Non-lesional | Lesional | Lesional / non-lesional | Section 5 reported |
   |---|---|---|---|---|
   | PtA | 0.0054 | 0.0122 | $2.2\times$ | 0.0068, 0.0136 ($2.0\times$) |
   | PtC | 0.0092 | 0.0114 | $1.2\times$ | 0.0108, 0.0132 ($1.2\times$) |
   | PtD | 0.0133 | 0.0136 | $1.0\times$ | 0.0147, 0.0159 ($1.1\times$) |
   | PtE | 0.0157 | 0.0744 | $4.8\times$ | 0.0217, 0.0952 ($4.4\times$) |
   | PtF | 0.0044 | 0.0101 | $2.3\times$ | 0.0054, 0.0109 ($2.0\times$) |
   | PtG | 0.0060 | 0.0093 | $1.6\times$ | 0.0078, 0.0118 ($1.5\times$) |

   **What stands.** Lesional skin scores higher in 6 of 6 patients. The sign test ($P = 0.0156$) and the Wilcoxon signed-rank test ($W = 21$, $P = 0.03125$) are as reported, because both depend only on all six differences being positive.

   **What weakens.** PtD's lesional score is 2.7% above its non-lesional score, where section 5 showed 8%. One of the six pairs is close to a tie.

   **Cell count.** Section 2 says 20,550 cells. The six archives hold 19,550: 8,903 non-lesional and 10,647 lesional. The means quoted there for `CXCL9` and `CXCL10`, and the ratios for `IL15` and `IL15RA`, are reproduced from those cells.

   **How to check.** `python scripts/durability/trm_reference.py` scores the archives with the implementation and writes [`data/trm-signature-reference.json`](data/trm-signature-reference.json), which holds the mean expression of every panel gene for each sample. Both columns of the table above can be recomputed from that file.

   **Effect on the seal.** None. Seal `2c102804` is the hash of the hypothesis record [`trm-il15-relapse`](../mechanisms/README.md): its claim, its context and its test. The record quotes no figure from section 5, and the seal still verifies.
