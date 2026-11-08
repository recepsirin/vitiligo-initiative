# Stage-2 Dense Cross-Encoder Curative Discovery Screen

## Executive Summary
- **Stage 1 (Retrieval):** Relational ComplEx GNN screened 893 canonical compounds and retrieved Top-60.
- **Stage 2 (Reranking):** Cross-encoder fused 1024-D Morgan fingerprints, 128-D ComplEx embeddings, GSE256271 PDE4B non-responder barrier, and melanocyte stem-cell regeneration pathways.

## Top Reranked Curative Candidates
| Rank | Drug | Reranker Score | Prob | GNN Score | Safety Profile | Curative Triad Alignment |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **betamethasone** | -0.048 | 48.8% | 1.733 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 2 | **betamethasone valerate** | -0.057 | 48.6% | 1.857 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 3 | **triamcinolone** | -0.271 | 43.3% | 1.893 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 4 | **clobetasol** | -0.297 | 42.6% | 1.955 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 5 | **clobetasone butyrate** | -1.133 | 24.3% | 2.018 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 6 | **bimatoprost** | -1.214 | 22.9% | 1.978 | Repurposed Non-Oncology (Favorable systemic safety profile) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 7 | **pimecrolimus** | -1.217 | 22.9% | 1.777 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 8 | **Beclomethasone** | -1.225 | 22.7% | 1.941 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 9 | **TACROLIMUS ANHYDROUS** | -1.334 | 20.8% | 2.022 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 10 | **triamcinolone acetonide** | -1.390 | 19.9% | 1.964 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 11 | **Fluticasone** | -1.392 | 19.9% | 1.837 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 12 | **fluticasone propionate** | -1.432 | 19.3% | 1.858 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 13 | **betamethasone-17,21-dipropionate** | -1.535 | 17.7% | 1.799 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 14 | **betamethasone dipropionate, betamethasone sodium phosphate drug combination** | -1.580 | 17.1% | 1.931 | Corticosteroid (Well-established dermatologic rescue) | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 15 | **Pravastatin** | -1.756 | 14.7% | 1.631 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 16 | **travoprost** | -1.782 | 14.4% | 1.764 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 17 | **fluprostenol** | -2.030 | 11.6% | 1.758 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 18 | **prednisolone** | -2.077 | 11.1% | 1.985 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 19 | **Fludrocortisone** | -2.100 | 10.9% | 1.844 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |
| 20 | **Epoprostenol** | -2.146 | 10.5% | 1.617 | Standard Molecular Entity | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression |