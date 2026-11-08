# Relational GNN Curative Discovery Report

> Computational discovery screen using heterogeneous multi-relational graph neural networks (`RGAT-4H + ComplEx`)
> over 18,494 entities, 93,201 edges, and 58 GEO transcriptomic/perturbation series.
> Cytotoxic oncology chemotherapies and non-dermatologic comorbidity confounders are quarantined.
> Verified Knowledge Graph mechanisms (ChEMBL / DrugCentral / Literature) are marked with `*`.

## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)

Molecules with high predicted and verified affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse:

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **ruxolitinib** | 3.670 | 97.5% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A*, IL15*, STAT3* |
| 2 | **baricitinib** | 3.575 | 97.3% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A*, STAT1*, STAT3* |
| 3 | **Deucravacitinib** | 3.567 | 97.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, STAT1*, STAT3*, CD8A |
| 4 | **delgocitinib** | 3.470 | 97.0% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, STAT3*, IL15, CD8A |
| 5 | **abrocitinib** | 3.447 | 96.9% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A, IL15, CD69 |
| 6 | **ritlecitinib** | 3.433 | 96.9% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK3*, JAK1, CD69, CD8A, IL15 |
| 7 | **CERDULATINIB** | 3.322 | 96.5% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A, IL15, CD69 |
| 8 | **momelotinib** | 3.293 | 96.4% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, IL15, CD8A, CD69 |
| 9 | **itacitinib** | 3.227 | 96.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3, CD69, CD8A |
| 10 | **upadacitinib** | 3.210 | 96.1% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD8A*, ITGAE |
| 11 | **peficitinib** | 3.191 | 96.0% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, CD69 |
| 12 | **tofacitinib** | 3.103 | 95.7% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3*, IL15*, STAT1*, CD8A* |
| 13 | **PF-06651600** | 2.985 | 95.2% | Standard Molecular Entity | JAK1*, CD8A*, IL15*, JAK3*, CD69* |
| 14 | **fedratinib** | 2.975 | 95.1% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, CD8A, JAK3, CD69 |
| 15 | **ivarmacitinib** | 2.909 | 94.8% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | JAK1*, JAK3, CD69 |

## 2. Top Regeneration & Non-Response Overcomers (Stem Cell Awakening / PDE4B Reversal)

Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`, `TYR`) and reversing the `PDE4B` non-response barrier (+9.09 $\log_2\text{FC}$ in GSE256271):

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **Roflumilast** | 4.373 | 98.8% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*), HTR1A (Act), KIT (Act) |
| 2 | **apremilast** | 4.203 | 98.5% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) |
| 3 | **fluoxetine** | 3.788 | 97.8% | Repurposed Non-Oncology (Favorable systemic safety profile) | HTR1A (Act*), PDE4A (Inh), PDE4B (Inh), TYR (Act), MITF (Act) |
| 4 | **Vilazodone Hydrochloride** | 3.756 | 97.7% | Repurposed Non-Oncology (Favorable systemic safety profile) | HTR1A (Act*), PDE4A (Inh), PDE4B (Inh), PDE4D (Inh) |
| 5 | **Alitretinoin** | 3.703 | 97.6% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*), MITF (Act*), DCT (Act), EDNRB (Act), CTNNB1 (Act) |
| 6 | **crisaborole** | 3.678 | 97.5% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*), PDE4B (Inh*), PDE4A (Inh*), PDE4D (Inh*) |
| 7 | **Resveratrol** | 3.587 | 97.3% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), EDNRB (Act), CTNNB1 (Act) |
| 8 | **Quercetin** | 3.565 | 97.2% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), EDNRB (Act), CTNNB1 (Act) |
| 9 | **cholecalciferol** | 3.555 | 97.2% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), DCT (Act), MITF (Act), HTR1A (Act), EDNRB (Act) |
| 10 | **5-Methoxypsoralen** | 3.536 | 97.2% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act*), MITF (Act), DCT (Act), CTNNB1 (Act) |
| 11 | **bimatoprost** | 3.527 | 97.2% | Topical (Minimal systemic exposure; high tolerability) | TYR (Act*) |
| 12 | **Metformin Hydrochloride** | 3.493 | 97.0% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act), DCT (Act), MITF (Act), EDNRB (Act), CTNNB1 (Act) |
| 13 | **Rosiglitazone** | 3.456 | 96.9% | Repurposed Non-Oncology (Favorable systemic safety profile) | EDNRB (Act*), TYR (Act), MITF (Act), DCT (Act), CTNNB1 (Act) |
| 14 | **Curcumin** | 3.402 | 96.8% | Repurposed Non-Oncology (Favorable systemic safety profile) | TYR (Act), MITF (Act), DCT (Act), EDNRB (Act), CTNNB1 (Act) |
| 15 | **Isotretinoin** | 3.392 | 96.8% | Topical (Minimal systemic exposure; high tolerability) | PDE4A (Inh), PDE4B (Inh), TYR (Act), DCT (Act), MITF (Act) |

## 3. Synergistic Combination Cocktails (Mechanistically Orthogonal Regimens)

Rationally paired 2-drug combinations pairing an **Immune Reset ($T_{RM}$ Disarmer)** with a **Mechanistically Orthogonal Regenerative / PDE4B Barrier Adjuvant**:

| Rank | Immune Reset (Memory Disarmer) | Regenerative / Barrier Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |
|:---:|:---|:---|:---:|:---|:---|
| 1 | **ruxolitinib** | **Roflumilast** | 4.021 | JAK1*, JAK3*, CD8A* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 2 | **baricitinib** | **Roflumilast** | 3.974 | JAK1*, JAK3*, CD8A* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 3 | **ruxolitinib** | **apremilast** | 3.936 | JAK1*, JAK3*, CD8A* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 4 | **baricitinib** | **apremilast** | 3.889 | JAK1*, JAK3*, CD8A* + PDE4A (Inh*), PDE4B (Inh*), PDE4D (Inh*) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 5 | **Deucravacitinib** | **fluoxetine** | 3.678 | JAK1*, JAK3*, STAT1* + HTR1A (Act*), PDE4A (Inh), PDE4B (Inh) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 6 | **Deucravacitinib** | **Vilazodone Hydrochloride** | 3.662 | JAK1*, JAK3*, STAT1* + HTR1A (Act*), PDE4A (Inh), PDE4B (Inh) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 7 | **delgocitinib** | **fluoxetine** | 3.629 | JAK1*, JAK3*, STAT3* + HTR1A (Act*), PDE4A (Inh), PDE4B (Inh) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 8 | **delgocitinib** | **Vilazodone Hydrochloride** | 3.613 | JAK1*, JAK3*, STAT3* + HTR1A (Act*), PDE4A (Inh), PDE4B (Inh) | Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity. |
| 9 | **abrocitinib** | **Alitretinoin** | 3.575 | JAK1*, JAK3*, CD8A + TYR (Act*), MITF (Act*), DCT (Act) | Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation. |
| 10 | **ritlecitinib** | **Alitretinoin** | 3.568 | JAK3*, JAK1, CD69 + TYR (Act*), MITF (Act*), DCT (Act) | Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation. |
