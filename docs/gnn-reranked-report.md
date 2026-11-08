# Stage-2 Dense Cross-Encoder Reranked Curative Candidates

**Architecture:** `Two-Stage Retrieve-and-Rerank (Stage 1: RGAT-4H ComplEx GNN -> Stage 2: Modality-Balanced Bottleneck Cross-Encoder)`  
**Feature Vector:** `1172-D` (1024-D Morgan Fingerprints + 128-D RGAT-ComplEx Latent + 18-D Triad Target Affinities + GSE256271 Barrier Alignment)  
**5-Fold Out-of-Fold CV:** `AUROC = 0.9490`, `Accuracy = 85.7%`  

| S2 Rank | S1 Rank | Candidate Drug | Prob | Rerank Logit | TRM Disarm | McSC Regen | PDE4B Barrier | Curative Triad Alignment | Key Targets (`*` = Verified) |
|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| **1** | 183 | **baricitinib** | `0.999` | `7.08` | `1.49` | `1.49` | `1.35` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+1) |
| **2** | 65 | **itacitinib** | `0.999` | `6.87` | `1.84` | `1.61` | `1.68` | Pillar 1: TRM Disarmament | JAK1 (Inh*), PDE4A (Inh) |
| **3** | 18 | **ruxolitinib** | `0.999` | `6.49` | `1.56` | `1.42` | `1.45` | Pillar 1: TRM Disarmament | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT3 (Inh*), CD8A (Inh*) (+1) |
| **4** | 300 | **tofacitinib** | `0.997` | `5.83` | `2.13` | `0.84` | `1.62` | Pillar 1: TRM Disarmament | IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*), CD8A (Inh*) (+1) |
| **5** | 120 | **voclosporin** | `0.997` | `5.65` | `2.62` | `2.20` | `1.81` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh), JAK1 (Inh), CD8A (Inh), MITF (Act), TYR (Act) (+1) |
| **6** | 45 | **Leflunomide** | `0.996` | `5.58` | `1.84` | `1.21` | `1.61` | Supportive Immunomodulator | JAK1 (Inh), PDE4A (Inh) |
| **7** | 164 | **ritlecitinib** | `0.996` | `5.45` | `1.91` | `1.80` | `1.70` | Pillar 1: TRM Disarmament | JAK1 (Inh), JAK3 (Inh*), PDE4A (Inh) |
| **8** | 11 | **Roflumilast** | `0.995` | `5.26` | `1.92` | `1.63` | `1.75` | Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), PDE4B (Inh*), PDE4A (Inh*) |
| **9** | 142 | **fluoxetine** | `0.990` | `4.58` | `2.17` | `2.00` | `1.64` | Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), MITF (Act), HTR1A (Act*), TYR (Act), PDE4A (Inh) |
| **10** | 225 | **lorlatinib** | `0.988` | `4.37` | `2.45` | `1.71` | `2.06` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh), JAK1 (Inh), CD8A (Inh), PDE4B (Inh), PDE4A (Inh) |
| **11** | 86 | **abrocitinib** | `0.981` | `3.96` | `1.90` | `1.45` | `1.60` | Pillar 1: TRM Disarmament | JAK1 (Inh*), JAK3 (Inh*), PDE4A (Inh) |
| **12** | 4 | **Ustekinumab** | `0.976` | `3.72` | `1.43` | `0.10` | `1.20` | Pillar 1: TRM Disarmament + Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh*), PDE4A (Inh*) |
| **13** | 213 | **givinostat hydrochloride** | `0.971` | `3.49` | `2.07` | `1.75` | `1.73` | Supportive Immunomodulator | JAK1 (Inh), PDE4A (Inh) |
| **14** | 62 | **Voriconazole** | `0.970` | `3.47` | `2.05` | `1.48` | `1.59` | Supportive Immunomodulator | JAK1 (Inh), PDE4A (Inh) |
| **15** | 28 | **Mycophenolic Acid** | `0.969` | `3.46` | `2.11` | `1.66` | `1.45` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration | JAK1 (Inh), CD8A (Inh*), MITF (Act*), TYR (Act*), PDE4A (Inh) |
| **16** | 117 | **peficitinib** | `0.968` | `3.39` | `1.81` | `1.41` | `1.56` | Pillar 1: TRM Disarmament | JAK1 (Inh*), JAK3 (Inh*), PDE4A (Inh) |
| **17** | 12 | **Vilazodone Hydrochloride** | `0.959` | `3.15` | `2.44` | `1.86` | `1.99` | Pillar 1: TRM Disarmament + Pillar 2: Stem-Cell Regeneration + Pillar 3: PDE4B Barrier Suppression | IL15 (Inh), JAK1 (Inh), CD8A (Inh), MITF (Act), HTR1A (Act*) (+2) |
| **18** | 10 | **Amifostine** | `0.957` | `3.11` | `1.57` | `1.15` | `1.31` | Supportive Immunomodulator |  |
| **19** | 31 | **Formoterol Fumarate** | `0.956` | `3.07` | `2.25` | `1.84` | `1.83` | Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), MITF (Act), PDE4A (Inh) |
| **20** | 141 | **cabozantinib** | `0.955` | `3.05` | `1.96` | `1.81` | `1.74` | Pillar 3: PDE4B Barrier Suppression | JAK1 (Inh), MITF (Act), PDE4A (Inh) |
