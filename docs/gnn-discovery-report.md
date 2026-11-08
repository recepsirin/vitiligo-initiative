# Relational GNN Curative Discovery Report

> Computational discovery screen using heterogeneous multi-relational graph neural networks
> over 17,685 entities, 62,006 edges, and 58 GEO transcriptomic/perturbation series.
> Cytotoxic oncology chemotherapies are quarantined from primary dermatologic discovery.

## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)

Molecules with high predicted affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse after JAK cessation:

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **ruxolitinib** | 1.914 | 87.2% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 2 | **tofacitinib** | 1.797 | 85.8% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, CXCR6, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69 |
| 3 | **itacitinib** | 1.786 | 85.7% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 4 | **Roflumilast** | 1.769 | 85.4% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 5 | **Voriconazole** | 1.754 | 85.2% | Standard Molecular Entity | IL15, CXCR6, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 6 | **bicalutamide** | 1.748 | 85.2% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 7 | **Terbinafine** | 1.746 | 85.1% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 8 | **ritlecitinib** | 1.742 | 85.1% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 9 | **lorlatinib** | 1.727 | 84.9% | Standard Molecular Entity | IL15, CXCR6, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69 |
| 10 | **LITFULO** | 1.713 | 84.7% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 11 | **Leflunomide** | 1.708 | 84.7% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 12 | **peficitinib** | 1.685 | 84.4% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 13 | **Vilazodone Hydrochloride** | 1.685 | 84.4% | Repurposed Non-Oncology (Favorable systemic safety profile) | IL15, CXCR6, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |
| 14 | **cabozantinib** | 1.682 | 84.3% | Standard Molecular Entity | IL15, JAK1, JAK3, STAT1, STAT3, CD8A, CD69 |
| 15 | **cobimetinib** | 1.671 | 84.2% | Standard Molecular Entity | IL15, CXCR6, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CD69, CGAS |

## 2. Top Regeneration & Non-Response Overcomers (Stem Cell Awakening / PDE4B Reversal)

Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`) and reversing the `PDE4B` non-response barrier (+9.09 $\log_2\text{FC}$ in GSE256271):

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **hydroxychloroquine** | 2.089 | 89.0% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 2 | **ruxolitinib** | 2.071 | 88.8% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CTNNB1 (Act), MITF (Act), EDNRB (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 3 | **Chloroquine** | 2.065 | 88.8% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 4 | **Haloperidol** | 1.993 | 88.0% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 5 | **Vilazodone Hydrochloride** | 1.964 | 87.7% | Repurposed Non-Oncology (Favorable systemic safety profile) | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 6 | **Ribavirin** | 1.955 | 87.6% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 7 | **plerixafor** | 1.940 | 87.4% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 8 | **Fluconazole** | 1.933 | 87.4% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 9 | **Insulin Glargine** | 1.921 | 87.2% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 10 | **voclosporin** | 1.909 | 87.1% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 11 | **Formoterol Fumarate** | 1.905 | 87.0% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 12 | **cobimetinib** | 1.903 | 87.0% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 13 | **ritlecitinib** | 1.881 | 86.8% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 14 | **alectinib** | 1.878 | 86.7% | Standard Molecular Entity | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |
| 15 | **itacitinib** | 1.876 | 86.7% | Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum) | CTNNB1 (Act), MITF (Act), EDNRB (Act), EDN3 (Act), KIT (Act), HTR1A (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |

## 3. Synergistic Combination Cocktails (Pulsed Curative Regimens)

Rationally paired 2-drug combinations pairing an **Immune Reset** agent with a **Regenerative Adjuvant**:

| Rank | Immune Reset (Memory Disarmer) | Regenerative Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |
|:---:|:---|:---|:---:|:---|:---|
| 1 | **ruxolitinib** | **hydroxychloroquine** | 2.001 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 2 | **ruxolitinib** | **Chloroquine** | 1.990 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 3 | **ruxolitinib** | **Haloperidol** | 1.954 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 4 | **tofacitinib** | **hydroxychloroquine** | 1.943 | IL15, CXCR6, JAK1 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 5 | **ruxolitinib** | **Vilazodone Hydrochloride** | 1.939 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 6 | **itacitinib** | **hydroxychloroquine** | 1.938 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 7 | **ruxolitinib** | **Ribavirin** | 1.935 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 8 | **tofacitinib** | **ruxolitinib** | 1.934 | IL15, CXCR6, JAK1 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 9 | **tofacitinib** | **Chloroquine** | 1.931 | IL15, CXCR6, JAK1 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 10 | **Roflumilast** | **hydroxychloroquine** | 1.929 | IL15, JAK1, JAK3 + CTNNB1 (Act), MITF (Act), EDNRB (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
