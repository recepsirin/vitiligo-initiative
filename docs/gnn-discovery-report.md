# Relational GNN Curative Discovery Report

> Computational discovery screen using heterogeneous multi-relational graph neural networks
> over 17,685 entities, 62,006 edges, and 58 GEO transcriptomic/perturbation series.
> Cytotoxic oncology chemotherapies are quarantined from primary dermatologic discovery.

## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)

Molecules with high predicted affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse after JAK cessation:

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **sacubitril and valsartan sodium hydrate drug combination** | 2.028 | 88.4% | Repurposed Non-Oncology (Favorable systemic safety profile) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 2 | **itacitinib** | 2.012 | 88.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 3 | **ruxolitinib** | 2.011 | 88.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 4 | **clobetasone butyrate** | 2.007 | 88.1% | Corticosteroid (Well-established dermatologic rescue) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 5 | **lorlatinib** | 1.991 | 88.0% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 6 | **ritlecitinib** | 1.991 | 88.0% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 7 | **fluticasone propionate** | 1.990 | 88.0% | Corticosteroid (Well-established dermatologic rescue) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 8 | **IVARMACITINIB SULFATE** | 1.984 | 87.9% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 9 | **Amifostine** | 1.982 | 87.9% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 10 | **Lenalidomide** | 1.976 | 87.8% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 11 | **fostamatinib** | 1.976 | 87.8% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 12 | **Sunitinib** | 1.976 | 87.8% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 13 | **betamethasone dipropionate, betamethasone sodium phosphate drug combination** | 1.974 | 87.8% | Corticosteroid (Well-established dermatologic rescue) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 14 | **Ondansetron** | 1.973 | 87.8% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 15 | **Formoterol Fumarate** | 1.973 | 87.8% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |

## 2. Top Regeneration & Non-Response Overcomers (Stem Cell Awakening / PDE4B Reversal)

Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`) and reversing the `PDE4B` non-response barrier (+9.09 $\log_2\text{FC}$ in GSE256271):

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **sacubitril and valsartan sodium hydrate drug combination** | 2.072 | 88.8% | Repurposed Non-Oncology (Favorable systemic safety profile) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 2 | **clobetasone butyrate** | 2.061 | 88.7% | Corticosteroid (Well-established dermatologic rescue) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 3 | **betamethasone dipropionate, betamethasone sodium phosphate drug combination** | 2.027 | 88.4% | Corticosteroid (Well-established dermatologic rescue) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 4 | **lorlatinib** | 2.025 | 88.3% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 5 | **Fluticasone** | 2.023 | 88.3% | Corticosteroid (Well-established dermatologic rescue) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 6 | **ruxolitinib** | 2.023 | 88.3% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 7 | **itacitinib** | 2.023 | 88.3% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 8 | **fluticasone propionate** | 2.022 | 88.3% | Corticosteroid (Well-established dermatologic rescue) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 9 | **IVARMACITINIB SULFATE** | 2.013 | 88.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 10 | **ritlecitinib** | 2.009 | 88.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 11 | **Vilazodone Hydrochloride** | 2.009 | 88.2% | Repurposed Non-Oncology (Favorable systemic safety profile) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 12 | **Sunitinib** | 2.007 | 88.1% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 13 | **temsirolimus** | 2.007 | 88.1% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 14 | **Telmisartan** | 2.006 | 88.1% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 15 | **flumequine** | 2.005 | 88.1% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |

## 3. Synergistic Combination Cocktails (Pulsed Curative Regimens)

Rationally paired 2-drug combinations pairing an **Immune Reset** agent with a **Regenerative Adjuvant**:

| Rank | Immune Reset (Memory Disarmer) | Regenerative Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |
|:---:|:---|:---|:---:|:---|:---|
| 1 | **sacubitril and valsartan sodium hydrate drug combination** | **clobetasone butyrate** | 2.045 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 2 | **itacitinib** | **sacubitril and valsartan sodium hydrate drug combination** | 2.042 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 3 | **ruxolitinib** | **sacubitril and valsartan sodium hydrate drug combination** | 2.042 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 4 | **clobetasone butyrate** | **sacubitril and valsartan sodium hydrate drug combination** | 2.039 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 5 | **itacitinib** | **clobetasone butyrate** | 2.037 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 6 | **ruxolitinib** | **clobetasone butyrate** | 2.036 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 7 | **lorlatinib** | **sacubitril and valsartan sodium hydrate drug combination** | 2.031 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 8 | **ritlecitinib** | **sacubitril and valsartan sodium hydrate drug combination** | 2.031 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 9 | **fluticasone propionate** | **sacubitril and valsartan sodium hydrate drug combination** | 2.031 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 10 | **IVARMACITINIB SULFATE** | **sacubitril and valsartan sodium hydrate drug combination** | 2.028 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
