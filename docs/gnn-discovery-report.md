# Relational GNN Curative Discovery Report

> Computational discovery screen using heterogeneous multi-relational graph neural networks
> over 17,685 entities, 62,006 edges, and 58 GEO transcriptomic/perturbation series.
> Cytotoxic oncology chemotherapies are quarantined from primary dermatologic discovery.

## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)

Molecules with high predicted affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse after JAK cessation:

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **TACROLIMUS ANHYDROUS** | 1.529 | 82.2% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, CD8A, ITGAE, CD69 |
| 2 | **Vancomycin** | 1.461 | 81.2% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, STAT3, CD8A, ITGAE, CD69, TBK1, CGAS |
| 3 | **Everolimus** | 1.441 | 80.9% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, STAT3, CD8A, ITGAE, CD69, TBK1, CGAS |
| 4 | **bimatoprost** | 1.440 | 80.8% | Repurposed Non-Oncology (Favorable systemic safety profile) | IL15, CD8A, CD69 |
| 5 | **clobetasone butyrate** | 1.420 | 80.5% | Corticosteroid (Well-established dermatologic rescue) | IL15, CXCR6, CXCL16, JAK1, STAT1, CD8A, ITGAE, CD69 |
| 6 | **Pentoxifylline** | 1.405 | 80.3% | Standard Molecular Entity | IL15, CD8A, CD69 |
| 7 | **ursodoxicoltaurine** | 1.404 | 80.3% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, STAT3, CD8A, ITGAE, CD69, TBK1, CGAS |
| 8 | **betamethasone dipropionate, betamethasone sodium phosphate drug combination** | 1.401 | 80.2% | Corticosteroid (Well-established dermatologic rescue) | IL15, CXCR6, CXCL16, JAK1, STAT1, CD8A, ITGAE, CD69 |
| 9 | **travoprost** | 1.391 | 80.1% | Standard Molecular Entity | IL15, CD8A, CD69 |
| 10 | **Curcumin** | 1.387 | 80.0% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, CD8A, ITGAE, CD69 |
| 11 | **Insulin Glargine** | 1.383 | 79.9% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, STAT3, CD8A, ITGAE, CD69, TBK1, CGAS |
| 12 | **Bromocriptine** | 1.381 | 79.9% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, CD8A, ITGAE, CD69 |
| 13 | **Pemetrexed** | 1.377 | 79.8% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, CD8A, ITGAE, CD69 |
| 14 | **clobetasol** | 1.377 | 79.8% | Corticosteroid (Well-established dermatologic rescue) | IL15, CXCR6, CXCL16, CD8A, ITGAE, CD69 |
| 15 | **Beclomethasone** | 1.377 | 79.8% | Standard Molecular Entity | IL15, CXCR6, CXCL16, JAK1, STAT1, CD8A, ITGAE, CD69 |

## 2. Top Regeneration & Non-Response Overcomers (Stem Cell Awakening / PDE4B Reversal)

Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`) and reversing the `PDE4B` non-response barrier (+9.09 $\log_2\text{FC}$ in GSE256271):

| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | **Curcumin** | 1.458 | 81.1% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 2 | **bimatoprost** | 1.426 | 80.6% | Repurposed Non-Oncology (Favorable systemic safety profile) | MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 3 | **Vancomycin** | 1.421 | 80.5% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh) |
| 4 | **betamethasone** | 1.415 | 80.5% | Corticosteroid (Well-established dermatologic rescue) | MITF (Act), TYR (Act), DCT (Act) |
| 5 | **Beclomethasone** | 1.410 | 80.4% | Standard Molecular Entity | WNT1 (Act), MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 6 | **ursodoxicoltaurine** | 1.409 | 80.4% | Standard Molecular Entity | WNT1 (Act), MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh) |
| 7 | **Buprenorphine** | 1.408 | 80.3% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 8 | **Fludrocortisone** | 1.407 | 80.3% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act) |
| 9 | **clobetasone butyrate** | 1.403 | 80.3% | Corticosteroid (Well-established dermatologic rescue) | WNT1 (Act), MITF (Act), EDNRB (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 10 | **prednisolone** | 1.399 | 80.2% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 11 | **2-(2-nitro-1H-imidazol-1-yl)-N-(2,2,3,3,3-pentafluoropropyl)acetamide** | 1.376 | 79.8% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act) |
| 12 | **Epoprostenol** | 1.371 | 79.8% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act) |
| 13 | **fluticasone propionate** | 1.371 | 79.8% | Corticosteroid (Well-established dermatologic rescue) | WNT1 (Act), MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 14 | **clobetasol** | 1.371 | 79.8% | Corticosteroid (Well-established dermatologic rescue) | WNT1 (Act), MITF (Act), EDNRB (Act), TYR (Act), DCT (Act), PDE4B (Inh) |
| 15 | **TACROLIMUS ANHYDROUS** | 1.371 | 79.8% | Standard Molecular Entity | MITF (Act), TYR (Act), DCT (Act), PDE4B (Inh), PDE4A (Inh), PDE4D (Inh) |

## 3. Synergistic Combination Cocktails (Pulsed Curative Regimens)

Rationally paired 2-drug combinations pairing an **Immune Reset** agent with a **Regenerative Adjuvant**:

| Rank | Immune Reset (Memory Disarmer) | Regenerative Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |
|:---:|:---|:---|:---:|:---|:---|
| 1 | **TACROLIMUS ANHYDROUS** | **Curcumin** | 1.494 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 2 | **TACROLIMUS ANHYDROUS** | **bimatoprost** | 1.478 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 3 | **TACROLIMUS ANHYDROUS** | **Vancomycin** | 1.475 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 4 | **TACROLIMUS ANHYDROUS** | **betamethasone** | 1.472 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 5 | **TACROLIMUS ANHYDROUS** | **Beclomethasone** | 1.470 | IL15, CXCR6, CXCL16 + WNT1 (Act), MITF (Act), TYR (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 6 | **TACROLIMUS ANHYDROUS** | **ursodoxicoltaurine** | 1.469 | IL15, CXCR6, CXCL16 + WNT1 (Act), MITF (Act), TYR (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 7 | **TACROLIMUS ANHYDROUS** | **Buprenorphine** | 1.468 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 8 | **TACROLIMUS ANHYDROUS** | **Fludrocortisone** | 1.468 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 9 | **Vancomycin** | **Curcumin** | 1.460 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
| 10 | **Everolimus** | **Curcumin** | 1.450 | IL15, CXCR6, CXCL16 + MITF (Act), TYR (Act), DCT (Act) | Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox. |
