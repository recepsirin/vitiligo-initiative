# Stage-2 Dense Cross-Encoder Reranked Curative Candidates

**Architecture:** `Two-Stage Retrieve-and-Rerank (Stage 1: RGAT-4H ComplEx GNN -> Stage 2: Modality-Balanced Bottleneck Cross-Encoder)`  
**Feature Vector:** `1172-D` (1024-D Morgan Fingerprints + 128-D RGAT-ComplEx Latent + 18-D Triad Target Affinities + GSE256271 Barrier Alignment)  
**5-Fold Out-of-Fold CV:** `AUROC = 0.9247`, `Accuracy = 82.1%`  

| S2 Rank | S1 Rank | Candidate Drug | Prob | Rerank Logit | TRM Disarm | McSC Regen | PDE4B Barrier | Curative Triad Alignment | Key Targets (`*` = Verified) |
|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| **1** | 630 | **baricitinib** | `0.999` | `6.56` | `2.12` | `1.20` | `2.10` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+3) |
| **2** | 155 | **fedratinib** | `0.999` | `6.56` | `1.89` | `0.90` | `1.99` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4B (Inh), PDE4A (Inh) |
| **3** | 244 | **itacitinib** | `0.998` | `6.40` | `1.97` | `1.10` | `2.10` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), JAK3 (Inh), PDE4B (Inh), PDE4A (Inh) |
| **4** | 492 | **temsirolimus** | `0.998` | `6.39` | `1.83` | `1.03` | `1.83` | Supportive Immunomodulator | JAK1 (Inh), PDE4B (Inh), PDE4A (Inh) |
| **5** | 109 | **TACROLIMUS ANHYDROUS** | `0.998` | `6.39` | `1.78` | `0.88` | `1.81` | Supportive Immunomodulator | JAK1 (Inh), PDE4B (Inh), PDE4A (Inh) |
| **6** | 132 | **pimecrolimus** | `0.998` | `6.32` | `1.92` | `0.86` | `1.94` | Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), MITF (Act*), TYR (Act*), PDE4B (Inh), PDE4A (Inh) |
| **7** | 494 | **ruxolitinib** | `0.998` | `6.10` | `1.97` | `0.86` | `2.02` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+2) |
| **8** | 405 | **afamelanotide** | `0.998` | `6.02` | `1.99` | `1.35` | `1.70` | Supportive Immunomodulator | JAK1 (Inh), TYR (Act), PDE4B (Inh), PDE4A (Inh) |
| **9** | 391 | **povorcitinib** | `0.997` | `5.94` | `2.05` | `1.17` | `1.96` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), PDE4B (Inh), PDE4A (Inh) |
| **10** | 68 | **apremilast** | `0.997` | `5.92` | `1.87` | `0.62` | `1.95` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4B (Inh*), PDE4A (Inh*) |
| **11** | 49 | **calcipotriol** | `0.997` | `5.85` | `2.00` | `1.43` | `1.78` | Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), TYR (Act), PDE4B (Inh), PDE4A (Inh) |
| **12** | 850 | **upadacitinib** | `0.996` | `5.57` | `1.91` | `0.68` | `1.28` | Pillar 1: TRM Disarmament | JAK1 (Inh*), JAK3 (Inh*), CD8A (Inh*), PDE4A (Inh) |
| **13** | 579 | **SIROLIMUS** | `0.996` | `5.52` | `2.07` | `1.26` | `1.81` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), CD8A (Inh*), MITF (Act*), TYR (Act*), PDE4B (Inh) (+1) |
| **14** | 260 | **travoprost** | `0.996` | `5.52` | `1.62` | `1.12` | `1.55` | Supportive Immunomodulator | PDE4A (Inh) |
| **15** | 196 | **ritlecitinib** | `0.996` | `5.44` | `2.24` | `1.17` | `2.34` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh), JAK1 (Inh), JAK3 (Inh*), CD8A (Inh), PDE4B (Inh) (+1) |
| **16** | 802 | **cyclosporine** | `0.996` | `5.44` | `1.92` | `1.86` | `0.95` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), CD8A (Inh*), TYR (Act) |
| **17** | 26 | **Roflumilast** | `0.994` | `5.10` | `2.17` | `1.41` | `2.05` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh), JAK1 (Inh), TYR (Act), PDE4B (Inh*), PDE4A (Inh*) |
| **18** | 138 | **bimatoprost** | `0.994` | `5.04` | `1.84` | `1.21` | `1.73` | Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), TYR (Act*), PDE4B (Inh), PDE4A (Inh) |
| **19** | 281 | **Isotretinoin** | `0.993` | `4.94` | `2.34` | `1.61` | `1.97` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh), JAK1 (Inh), MITF (Act), TYR (Act), PDE4B (Inh) (+1) |
| **20** | 367 | **CERDULATINIB** | `0.993` | `4.92` | `2.33` | `1.41` | `2.29` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh), JAK1 (Inh*), JAK3 (Inh*), CD8A (Inh), TYR (Act) (+2) |
