# Relational GNN Curative Discovery Report

> Computational discovery screen using heterogeneous multi-relational graph neural networks (`RGAT-4H + ComplEx`)
> over 18,730 entities, 96,073 edges, and 58 GEO transcriptomic/perturbation series.
> Cytotoxic oncology chemotherapies and non-dermatologic comorbidity confounders are quarantined.
> Verified Knowledge Graph mechanisms (ChEMBL / DrugCentral / Literature) are marked with `*`.

## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)

Molecules with high predicted and verified affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse:

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **tofacitinib** | 3.282 | 96.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CD8A*, JAK1*, JAK3*, IL15*, CD69* |
| 2 | **ruxolitinib** | 3.278 | 96.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A*, IL15*, STAT3* |
| 3 | **delgocitinib** | 3.275 | 96.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, STAT3*, CD8A, STAT1 |
| 4 | **Deucravacitinib** | 3.262 | 96.3% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, STAT1*, STAT3* |
| 5 | **abrocitinib** | 3.218 | 96.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A, STAT1, IL15 |
| 6 | **upadacitinib** | 3.143 | 95.9% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CD8A*, JAK1*, JAK3*, IL15, CD69 |
| 7 | **baricitinib** | 3.118 | 95.8% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A*, STAT1*, STAT3* |
| 8 | **peficitinib** | 3.075 | 95.6% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A, IL15 |
| 9 | **momelotinib** | 3.041 | 95.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A, IL15, CD69 |
| 10 | **RITLECITINIB TOSYLATE** | 3.024 | 95.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK3*, JAK1, CD8A, IL15, STAT1 |
| 11 | **CERDULATINIB** | 2.968 | 95.1% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A, IL15 |
| 12 | **methotrexate** | 2.948 | 95.0% | Standard Molecular Entity | JAK1*, CD8A*, CD69*, IL15, JAK3 |
| 13 | **SIROLIMUS** | 2.892 | 94.7% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CD8A*, JAK1, STAT1, STAT3, IL15 |
| 14 | **itacitinib** | 2.857 | 94.6% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3 |
| 15 | **PF-06651600** | 2.847 | 94.5% | Standard Molecular Entity | JAK1*, CD8A*, JAK3*, IL15*, STAT3* |

## 2. Top Regeneration & Non-Response Overcomers (Stem Cell Awakening / PDE4B Reversal)

Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`, `TYR`) and reversing the `PDE4B` non-response barrier (+9.09 $\log_2\text{FC}$ in GSE256271):

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **Roflumilast** | 4.652 | 99.1% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*), TYR (Act), MITF (Act) |
| 2 | **apremilast** | 4.081 | 98.3% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) |
| 3 | **crisaborole** | 3.978 | 98.2% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*), PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*), EDNRB (Act) |
| 4 | **Quercetin** | 3.883 | 98.0% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), EDNRB (Act), KIT (Act) |
| 5 | **Vilazodone Hydrochloride** | 3.794 | 97.8% | Repurposed Non-Oncology (Favorable systemic safety profile) | HTR1A (Act*), PDE4A (Inh), PDE4B (Inh), PDE4D (Inh) |
| 6 | **fluoxetine** | 3.768 | 97.7% | Repurposed Non-Oncology (Favorable systemic safety profile) | HTR1A (Act*), TYR (Act), MITF (Act), DCT (Act), KIT (Act) |
| 7 | **Resveratrol** | 3.764 | 97.7% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), EDNRB (Act), KIT (Act) |
| 8 | **Rosiglitazone** | 3.741 | 97.7% | Repurposed Non-Oncology (Favorable systemic safety profile) | EDNRB (Act*), TYR (Act), MITF (Act), DCT (Act), KIT (Act) |
| 9 | **methoxsalen** | 3.720 | 97.6% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act*), EDN3 (Act) |
| 10 | **bimatoprost** | 3.647 | 97.5% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*) |
| 11 | **cholecalciferol** | 3.619 | 97.4% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), EDNRB (Act), CTNNB1 (Act) |
| 12 | **Alitretinoin** | 3.617 | 97.4% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*), MITF (Act*), DCT (Act), EDNRB (Act), CTNNB1 (Act) |
| 13 | **5-Methoxypsoralen** | 3.609 | 97.4% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), EDNRB (Act), CTNNB1 (Act) |
| 14 | **Curcumin** | 3.573 | 97.3% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act), MITF (Act), DCT (Act), EDNRB (Act), KIT (Act) |
| 15 | **travoprost** | 3.547 | 97.2% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*) |

## 3. Synergistic Combination Cocktails (Mechanistically Orthogonal Regimens)

Rationally paired 2-drug combinations pairing an **Immune Reset ($T_{RM}$ Disarmer)** with a **Mechanistically Orthogonal Regenerative / PDE4B Barrier Adjuvant**:

| Rank | Immune Reset (Memory Disarmer) | Regenerative / Barrier Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |
|:---:|:---|:---|:---:|:---|:---|
| 1 | **tofacitinib** | **Roflumilast** | 3.967 | CD8A*, JAK1*, JAK3* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 2 | **ruxolitinib** | **Roflumilast** | 3.965 | JAK1*, JAK3*, CD8A* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 3 | **tofacitinib** | **apremilast** | 3.681 | CD8A*, JAK1*, JAK3* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 4 | **ruxolitinib** | **apremilast** | 3.679 | JAK1*, JAK3*, CD8A* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 5 | **delgocitinib** | **crisaborole** | 3.626 | JAK1*, JAK3*, STAT3* + TYR (Act*), PDE4A (Inh*), PDE4B (Inh*) | Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation. |
| 6 | **Deucravacitinib** | **crisaborole** | 3.620 | JAK1*, JAK3*, STAT1* + TYR (Act*), PDE4A (Inh*), PDE4B (Inh*) | Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation. |
| 7 | **delgocitinib** | **Quercetin** | 3.579 | JAK1*, JAK3*, STAT3* + TYR (Act*), MITF (Act), DCT (Act) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 8 | **Deucravacitinib** | **Quercetin** | 3.573 | JAK1*, JAK3*, STAT1* + TYR (Act*), MITF (Act), DCT (Act) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 9 | **abrocitinib** | **Vilazodone Hydrochloride** | 3.506 | JAK1*, JAK3*, CD8A + HTR1A (Act*), PDE4A (Inh), PDE4B (Inh) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 10 | **abrocitinib** | **fluoxetine** | 3.493 | JAK1*, JAK3*, CD8A + HTR1A (Act*), TYR (Act), MITF (Act) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
