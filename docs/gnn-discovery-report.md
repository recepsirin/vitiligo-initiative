# Relational GNN Curative Discovery Report

> Computational discovery screen using heterogeneous multi-relational graph neural networks (`RGAT-4H + ComplEx`)
> over 18,494 entities, 92,361 edges, and 58 GEO transcriptomic/perturbation series.
> Cytotoxic oncology chemotherapies and non-dermatologic comorbidity confounders are quarantined.
> Verified Knowledge Graph mechanisms (ChEMBL / DrugCentral / Literature) are marked with `*`.

## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)

Molecules with high predicted and verified affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse:

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **ruxolitinib** | 3.607 | 97.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, IL15*, CD8A*, JAK3*, STAT3* |
| 2 | **tofacitinib** | 3.552 | 97.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, IL15*, CD8A*, CD69*, JAK3* |
| 3 | **baricitinib** | 3.230 | 96.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, CD8A*, JAK3*, STAT3*, STAT1* |
| 4 | **delgocitinib** | 3.229 | 96.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, STAT3*, JAK3* |
| 5 | **CERDULATINIB** | 3.177 | 96.0% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A, IL15, CD69 |
| 6 | **peficitinib** | 3.118 | 95.8% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3* |
| 7 | **abrocitinib** | 3.045 | 95.5% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3* |
| 8 | **itacitinib** | 3.030 | 95.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3 |
| 9 | **RITLECITINIB TOSYLATE** | 2.998 | 95.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK3*, JAK1, CD69 |
| 10 | **Deucravacitinib** | 2.995 | 95.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, STAT1*, STAT3* |
| 11 | **peoniflorin** | 2.950 | 95.0% | Standard Molecular Entity | CD8A*, CD69*, STAT1*, JAK1, IL15 |
| 12 | **methotrexate** | 2.879 | 94.7% | Standard Molecular Entity | JAK1*, CD69*, CD8A, IL15, ITGAE* |
| 13 | **momelotinib** | 2.761 | 94.1% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3* |
| 14 | **simvastatin** | 2.753 | 94.0% | Repurposed Non-Oncology (Favorable systemic safety profile) | CD8A*, STAT1*, JAK1, IL15, CD69 |
| 15 | **cyclosporine** | 2.736 | 93.9% | Standard Molecular Entity | CD8A* |

## 2. Top Regeneration & Non-Response Overcomers (Stem Cell Awakening / PDE4B Reversal)

Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`, `TYR`) and reversing the `PDE4B` non-response barrier (+9.09 $\log_2\text{FC}$ in GSE256271):

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **Roflumilast** | 4.219 | 98.6% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | PDE4A (Inh*), PDE4D (Inh*), PDE4B (Inh*) |
| 2 | **crisaborole** | 3.832 | 97.9% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*), PDE4A (Inh*), PDE4D (Inh*), PDE4B (Inh*) |
| 3 | **Vilazodone Hydrochloride** | 3.826 | 97.9% | Repurposed Non-Oncology (Favorable systemic safety profile) | HTR1A (Act*), PDE4A (Inh), PDE4D (Inh), TYR (Act), PDE4B (Inh) |
| 4 | **apremilast** | 3.695 | 97.6% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | PDE4A (Inh*), PDE4D (Inh*), PDE4B (Inh*) |
| 5 | **Rosiglitazone** | 3.551 | 97.2% | Repurposed Non-Oncology (Favorable systemic safety profile) | EDNRB (Act*), MITF (Act), DCT (Act), TYR (Act), PDE4A (Inh) |
| 6 | **fluoxetine** | 3.546 | 97.2% | Repurposed Non-Oncology (Favorable systemic safety profile) | HTR1A (Act*), MITF (Act), TYR (Act), DCT (Act), PDE4D (Inh) |
| 7 | **bimatoprost** | 3.529 | 97.2% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*), PDE4B (Inh) |
| 8 | **methoxsalen** | 3.381 | 96.7% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), DCT (Act), CTNNB1 (Act), EDNRB (Act), HTR1A (Act) |
| 9 | **5-Methoxypsoralen** | 3.366 | 96.7% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), CTNNB1 (Act), HTR1A (Act) |
| 10 | **Resveratrol** | 3.325 | 96.5% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), CTNNB1 (Act), EDNRB (Act) |
| 11 | **Alitretinoin** | 3.314 | 96.5% | Topical (Minimal systemic exposure; high tolerability) | MITF (Act*), TYR (Act*) |
| 12 | **psoralen** | 3.284 | 96.4% | Repurposed Non-Oncology (Favorable systemic safety profile) | MITF (Act), TYR (Act), DCT (Act), CTNNB1 (Act), HTR1A (Act) |
| 13 | **Quercetin** | 3.262 | 96.3% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), PDE4D (Inh), PDE4B (Inh) |
| 14 | **Pioglitazone** | 3.255 | 96.3% | Repurposed Non-Oncology (Favorable systemic safety profile) | MITF (Act), DCT (Act), TYR (Act), PDE4B (Inh), CTNNB1 (Act) |
| 15 | **cholecalciferol** | 3.248 | 96.3% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*) |

## 3. Synergistic Combination Cocktails (Mechanistically Orthogonal Regimens)

Rationally paired 2-drug combinations pairing an **Immune Reset ($T_{RM}$ Disarmer)** with a **Mechanistically Orthogonal Regenerative / PDE4B Barrier Adjuvant**:

| Rank | Immune Reset (Memory Disarmer) | Regenerative / Barrier Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |
|:---:|:---|:---|:---:|:---|:---|
| 1 | **ruxolitinib** | **Roflumilast** | 3.913 | JAK1*, IL15*, CD8A* + PDE4A (Inh*), PDE4D (Inh*), PDE4B (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 2 | **tofacitinib** | **Roflumilast** | 3.885 | JAK1*, IL15*, CD8A* + PDE4A (Inh*), PDE4D (Inh*), PDE4B (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 3 | **ruxolitinib** | **crisaborole** | 3.719 | JAK1*, IL15*, CD8A* + TYR (Act*), PDE4A (Inh*), PDE4D (Inh*) | Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation. |
| 4 | **tofacitinib** | **crisaborole** | 3.692 | JAK1*, IL15*, CD8A* + TYR (Act*), PDE4A (Inh*), PDE4D (Inh*) | Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation. |
| 5 | **baricitinib** | **Vilazodone Hydrochloride** | 3.528 | JAK1*, CD8A*, JAK3* + HTR1A (Act*), PDE4A (Inh), PDE4D (Inh) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 6 | **delgocitinib** | **Vilazodone Hydrochloride** | 3.527 | JAK1*, STAT3*, JAK3* + HTR1A (Act*), PDE4A (Inh), PDE4D (Inh) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 7 | **baricitinib** | **apremilast** | 3.463 | JAK1*, CD8A*, JAK3* + PDE4A (Inh*), PDE4D (Inh*), PDE4B (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 8 | **delgocitinib** | **apremilast** | 3.462 | JAK1*, STAT3*, JAK3* + PDE4A (Inh*), PDE4D (Inh*), PDE4B (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 9 | **CERDULATINIB** | **Rosiglitazone** | 3.364 | JAK1*, JAK3*, CD8A + EDNRB (Act*), MITF (Act), DCT (Act) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 10 | **CERDULATINIB** | **fluoxetine** | 3.362 | JAK1*, JAK3*, CD8A + HTR1A (Act*), MITF (Act), TYR (Act) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
