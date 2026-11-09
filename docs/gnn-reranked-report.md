# Stage-2 Dense Cross-Encoder Reranked Curative Candidates

**Architecture:** `Two-Stage Retrieve-and-Rerank (Stage 1: RGAT-4H ComplEx GNN -> Stage 2: Modality-Balanced Bottleneck Cross-Encoder)`  
**Feature Vector:** `1172-D` (1024-D Morgan Fingerprints + 128-D RGAT-ComplEx Latent + 18-D Triad Target Affinities + GSE256271 Barrier Alignment)  
**5-Fold Out-of-Fold CV:** `AUROC = 0.8980`, `Accuracy = 83.9%`  

| S2 Rank | S1 Rank | Candidate Drug | Prob | Rerank Logit | TRM Disarm | McSC Regen | PDE4B Barrier | Curative Triad Alignment | Key Targets (`*` = Verified) |
|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| **1** | 358 | **baricitinib** | `0.999` | `7.03` | `1.64` | `1.29` | `1.93` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+2) |
| **2** | 135 | **ruxolitinib** | `0.998` | `6.43` | `1.73` | `1.17` | `2.02` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+2) |
| **3** | 565 | **fedratinib** | `0.998` | `6.29` | `1.58` | `1.27` | `1.98` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4A (Inh) |
| **4** | 185 | **itacitinib** | `0.998` | `6.19` | `1.63` | `1.21` | `2.04` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4B (Inh), PDE4A (Inh) |
| **5** | 349 | **afamelanotide** | `0.997` | `5.84` | `1.74` | `1.93` | `1.47` | Pillar 2: Stem-Cell Regeneration | MITF (Act), TYR (Act) |
| **6** | 408 | **apremilast** | `0.997` | `5.70` | `1.40` | `1.25` | `1.99` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4B (Inh*), PDE4A (Inh*) |
| **7** | 587 | **temsirolimus** | `0.997` | `5.69` | `1.93` | `1.72` | `2.00` | Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), TYR (Act), PDE4B (Inh), PDE4A (Inh) |
| **8** | 934 | **upadacitinib** | `0.997` | `5.66` | `2.09` | `1.53` | `1.48` | Pillar 1: TRM Disarmament | JAK1 (Inh*), JAK3 (Inh*), CD8A (Inh*), PDE4A (Inh) |
| **9** | 224 | **travoprost** | `0.997` | `5.64` | `1.70` | `1.56` | `1.70` | Pillar 2: Stem-Cell Regeneration | TYR (Act*), PDE4A (Inh) |
| **10** | 266 | **calcipotriol** | `0.997` | `5.64` | `1.93` | `1.81` | `1.76` | Supportive Immunomodulator | JAK1 (Inh), MITF (Act), TYR (Act), PDE4A (Inh) |
| **11** | 472 | **PF-06651600** | `0.996` | `5.60` | `2.40` | `1.93` | `2.30` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+4) |
| **12** | 902 | **cyclosporine** | `0.996` | `5.44` | `2.38` | `1.14` | `1.32` | Pillar 1: TRM Disarmament | JAK1 (Inh), CD8A (Inh*) |
| **13** | 397 | **RITLECITINIB TOSYLATE** | `0.995` | `5.38` | `2.33` | `1.80` | `2.44` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), JAK3 (Inh*), TYR (Act), PDE4B (Inh), PDE4A (Inh) |
| **14** | 756 | **SIROLIMUS** | `0.995` | `5.36` | `2.43` | `2.17` | `2.01` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), STAT1 (Inh), CD8A (Inh*), MITF (Act*), TYR (Act*) (+2) |
| **15** | 936 | **tofacitinib** | `0.995` | `5.24` | `2.24` | `0.93` | `1.51` | Pillar 1: TRM Disarmament | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*), CD8A (Inh*) (+1) |
| **16** | 22 | **Roflumilast** | `0.994` | `5.17` | `2.19` | `2.17` | `2.28` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), MITF (Act), TYR (Act), PDE4B (Inh*), PDE4A (Inh*) |
| **17** | 133 | **bimatoprost** | `0.994` | `5.14` | `1.72` | `1.71` | `1.69` | Pillar 2: Stem-Cell Regeneration | TYR (Act*), PDE4A (Inh) |
| **18** | 529 | **Pioglitazone** | `0.994` | `5.11` | `2.24` | `2.31` | `1.72` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | MITF (Act), TYR (Act), PDE4A (Inh) |
| **19** | 469 | **atorvastatin** | `0.994` | `5.07` | `2.18` | `1.99` | `1.71` | Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), MITF (Act), TYR (Act), PDE4A (Inh) |
| **20** | 446 | **ivarmacitinib** | `0.993` | `5.02` | `1.47` | `1.00` | `1.95` | Pillar 1: TRM Disarmament | JAK1 (Inh*), PDE4A (Inh) |
