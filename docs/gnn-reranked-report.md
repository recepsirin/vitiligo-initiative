# Stage-2 Dense Cross-Encoder Curative Discovery Screen

## Executive Summary
- **Stage 1 (Retrieval):** Relational ComplEx GNN screened 893 canonical compounds and retrieved Top-60.
- **Stage 2 (Reranking):** Cross-encoder fused 1024-D Morgan fingerprints, 128-D ComplEx embeddings, GSE256271 PDE4B non-responder barrier, and melanocyte stem-cell regeneration pathways.

## Top Reranked Curative Candidates
| Rank | Drug | Reranker Score | Prob | GNN Score | Safety Profile | Curative Triad Alignment |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **betamethasone valerate** | 2.429 | 91.9% | 1.774 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 2 | **clobetasol** | 2.426 | 91.9% | 1.810 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 3 | **clobetasone butyrate** | 2.357 | 91.3% | 1.738 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 4 | **pimecrolimus** | 2.350 | 91.3% | 1.793 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 5 | **fluticasone propionate** | 2.317 | 91.0% | 1.706 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 6 | **Fluticasone** | 2.316 | 91.0% | 1.702 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 7 | **TACROLIMUS ANHYDROUS** | 2.201 | 90.0% | 1.940 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 8 | **betamethasone-17,21-dipropionate** | 2.117 | 89.2% | 1.865 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 9 | **betamethasone dipropionate, betamethasone sodium phosphate drug combination** | 2.093 | 89.0% | 1.880 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 10 | **sacubitril and valsartan sodium hydrate drug combination** | 0.715 | 67.2% | 1.879 | Repurposed Non-Oncology (Favorable systemic safety profile) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 11 | **fluprostenol** | 0.011 | 50.3% | 1.887 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 12 | **flumequine** | -0.139 | 46.5% | 1.887 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 13 | **Pemetrexed** | -1.727 | 15.1% | 1.959 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 14 | **Formoterol Fumarate** | -1.773 | 14.5% | 1.904 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 15 | **temsirolimus** | -2.133 | 10.6% | 1.672 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 16 | **Terbinafine** | -2.201 | 10.0% | 1.940 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 17 | **Edetic Acid** | -2.677 | 6.4% | 1.962 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 18 | **Sunitinib** | -2.699 | 6.3% | 1.864 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 19 | **Vilazodone Hydrochloride** | -2.725 | 6.2% | 1.927 | Repurposed Non-Oncology (Favorable systemic safety profile) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 20 | **folic acid** | -2.754 | 6.0% | 2.012 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |