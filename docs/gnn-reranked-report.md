# Stage-2 Dense Cross-Encoder Reranked Curative Candidates

**Architecture:** `Two-Stage Retrieve-and-Rerank (Stage 1: RGAT-4H ComplEx GNN -> Stage 2: Modality-Balanced Bottleneck Cross-Encoder)`  
**Feature Vector:** `1172-D` (1024-D Morgan Fingerprints + 128-D RGAT-ComplEx Latent + 18-D Triad Target Affinities + GSE256271 Barrier Alignment)  
**5-Fold Out-of-Fold CV:** `AUROC = 0.9490`, `Accuracy = 85.7%`  

| S2 Rank | S1 Rank | Candidate Drug | Prob | Rerank Logit | TRM Disarm | McSC Regen | PDE4B Barrier | Curative Triad Alignment | Key Targets (`*` = Verified) |
|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| **1** | 183 | **baricitinib** | `0.999` | `7.08` | `1.49` | `1.49` | `1.35` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+2) |
| **2** | 219 | **temsirolimus** | `0.999` | `6.97` | `1.95` | `1.65` | `1.60` | Supportive Immunomodulator | JAK1 (Inh), PDE4A (Inh) |
| **3** | 65 | **itacitinib** | `0.999` | `6.87` | `1.84` | `1.61` | `1.68` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4A (Inh) |
| **4** | 18 | **ruxolitinib** | `0.999` | `6.49` | `1.56` | `1.42` | `1.45` | Pillar 1: TRM Disarmament | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+1) |
| **5** | 259 | **apremilast** | `0.998` | `6.21` | `1.46` | `0.97` | `1.45` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4B (Inh*), PDE4A (Inh*) |
| **6** | 176 | **Povorcitinib phosphate** | `0.998` | `6.10` | `1.94` | `1.64` | `1.58` | Supportive Immunomodulator | JAK1 (Inh), PDE4A (Inh) |
| **7** | 280 | **cyclosporine** | `0.998` | `6.02` | `1.82` | `0.34` | `1.20` | Pillar 1: TRM Disarmament | CD8A (Inh*) |
| **8** | 207 | **afamelanotide** | `0.997` | `5.89` | `1.89` | `1.79` | `1.35` | Supportive Immunomodulator | MITF (Act), TYR (Act) |
| **9** | 300 | **tofacitinib** | `0.997` | `5.83` | `2.13` | `0.84` | `1.62` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*), CD8A (Inh*) (+1) |
| **10** | 432 | **SIROLIMUS** | `0.997` | `5.70` | `2.28` | `1.84` | `1.65` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), CD8A (Inh*), MITF (Act*), TYR (Act*), PDE4A (Inh) |
| **11** | 126 | **travoprost** | `0.997` | `5.65` | `1.87` | `1.47` | `1.40` | Supportive Immunomodulator | JAK1 (Inh) |
| **12** | 193 | **ivarmacitinib** | `0.996` | `5.50` | `1.49` | `1.11` | `1.37` | Pillar 1: TRM Disarmament | JAK1 (Inh*) |
| **13** | 677 | **methotrexate** | `0.996` | `5.43` | `2.43` | `1.06` | `1.61` | Pillar 1: TRM Disarmament | IL15 (Inh), JAK1 (Inh*), CD8A (Inh), ITGAE (Inh*), PDE4A (Inh) |
| **14** | 705 | **tacrolimus** | `0.995` | `5.35` | `2.09` | `1.51` | `1.44` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), CD8A (Inh*), MITF (Act*), EDNRB (Act*), KIT (Act*) (+2) |
| **15** | 837 | **upadacitinib** | `0.995` | `5.35` | `0.97` | `-0.62` | `0.40` | Pillar 1: TRM Disarmament | JAK1 (Inh*), JAK3 (Inh*), CD8A (Inh*) |
| **16** | 137 | **crisaborole** | `0.995` | `5.32` | `1.69` | `1.27` | `1.35` | Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | TYR (Act*), PDE4B (Inh*), PDE4A (Inh*) |
| **17** | 11 | **Roflumilast** | `0.995` | `5.26` | `1.92` | `1.63` | `1.75` | Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), PDE4B (Inh*), PDE4A (Inh*) |
| **18** | 341 | **CERDULATINIB** | `0.994` | `5.11` | `2.32` | `1.61` | `1.84` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), JAK3 (Inh*), CD8A (Inh), PDE4A (Inh) |
| **19** | 636 | **latanoprost** | `0.994` | `5.09` | `1.50` | `0.63` | `1.23` | Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), TYR (Act*) |
| **20** | 212 | **RITLECITINIB TOSYLATE** | `0.994` | `5.09` | `2.16` | `1.87` | `1.77` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), JAK3 (Inh*), MITF (Act), PDE4A (Inh) |
