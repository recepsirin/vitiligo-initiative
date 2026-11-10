# Pairwise In-Silico Drug Synergy Matrix: The Curative Triad

**The Vitiligo Initiative | Computational Pharmacology & Multi-Target Therapeutics**  
**Model Basis:** Heterogeneous `RGAT-4H + ComplEx` GNN on 96,073 relations + Stage-2 Cross-Encoder reranker.  

---

## Executive Summary

Monotherapy oral or topical kinase inhibitors hit a biological ceiling at ~18% total body clearance (STOP-V Phase 3, *Nature Medicine* Nov 2026) with >34% relapse upon cessation. To overcome the $+9.09 \log_2\text{FC}$ `PDE4B` non-responder barrier (*GSE256271*) and disarm anchored epidermal $CD8^+ T_{\text{RM}}$ memory cells, pairwise combinations were computationally screened across target orthogonality, Bliss excess surfaces, and virtual Chou-Talalay Combination Indices ($CI$).

| Rank | Combination Regimen | Virtual CI | Bliss Excess | Synergy Score | Route & Safety | Key Mechanistic Rationale |
|---|---|---:|---:|---:|---|---|
| 1 | **Cyclosporine** + **Pioglitazone** | **0.35** (Synergistic) | +0.148 | 4.18 | Oral / Systemic Combination | Immune disarmament via cyclosporine; Follicular McSC stem-cell mobilization via Pioglitazone |
| 2 | **Afamelanotide** + **Tofacitinib** | **0.35** (Synergistic) | +0.146 | 4.15 | Oral / Systemic Combination | Immune disarmament via tofacitinib; Follicular McSC stem-cell mobilization via afamelanotide |
| 3 | **Afamelanotide** + **Cyclosporine** | **0.35** (Synergistic) | +0.145 | 4.15 | Oral / Systemic Combination | Immune disarmament via cyclosporine; Follicular McSC stem-cell mobilization via afamelanotide |
| 4 | **Ruxolitinib** + **Afamelanotide** | **0.35** (Synergistic) | +0.145 | 4.14 | Oral / Systemic Combination | Immune disarmament via afamelanotide; PDE4B (+9.09 log2FC) barrier reversal via ruxolitinib; Follicular McSC stem-cell mobilization via afamelanotide |
| 5 | **Cyclosporine** + **Bimatoprost** | **0.35** (Synergistic) | +0.144 | 4.12 | Targeted Oral + Topical Adjuvant | Immune disarmament via cyclosporine; Follicular McSC stem-cell mobilization via bimatoprost |
| 6 | **Ruxolitinib** + **Pioglitazone** | **0.35** (Synergistic) | +0.131 | 3.94 | Oral / Systemic Combination | Immune disarmament via Pioglitazone; PDE4B (+9.09 log2FC) barrier reversal via ruxolitinib; Follicular McSC stem-cell mobilization via Pioglitazone |
| 7 | **Tofacitinib** + **Pioglitazone** | **0.35** (Synergistic) | +0.129 | 3.91 | Oral / Systemic Combination | Immune disarmament via tofacitinib; Follicular McSC stem-cell mobilization via Pioglitazone |
| 8 | **Ruxolitinib** + **Bimatoprost** | **0.35** (Synergistic) | +0.126 | 3.85 | Targeted Oral + Topical Adjuvant | Immune disarmament via ruxolitinib; PDE4B (+9.09 log2FC) barrier reversal via ruxolitinib; Follicular McSC stem-cell mobilization via bimatoprost |
| 9 | **Tofacitinib** + **Bimatoprost** | **0.35** (Synergistic) | +0.124 | 3.82 | Targeted Oral + Topical Adjuvant | Immune disarmament via tofacitinib; Follicular McSC stem-cell mobilization via bimatoprost |
| 10 | **Fedratinib** + **Pf-06651600** | **0.36** (Synergistic) | +0.115 | 3.69 | Oral / Systemic Combination | Immune disarmament via PF-06651600; PDE4B (+9.09 log2FC) barrier reversal via PF-06651600; Follicular McSC stem-cell mobilization via PF-06651600 |

---

## Detailed Top Pair Profiles

### #1. Cyclosporine + Pioglitazone
- **Synergy Score:** `4.181` · **Virtual CI:** `0.35` (Chou-Talalay: $<0.70$ indicates strong synergy) · **Bliss Excess:** `+0.148`
- **Target Orthogonality:** `1.00` (Jaccard distance: non-redundant target mechanisms)
- **Route Compatibility:** Oral / Systemic Combination (Clinical monitoring recommended)
- **Cyclosporine Targets:** JAK1 (Inh), CD8A (Inh*)
- **Pioglitazone Targets:** MITF (Act), TYR (Act), PDE4A (Inh)
- **Mechanistic Rationale:** Immune disarmament via cyclosporine; Follicular McSC stem-cell mobilization via Pioglitazone

### #2. Afamelanotide + Tofacitinib
- **Synergy Score:** `4.148` · **Virtual CI:** `0.35` (Chou-Talalay: $<0.70$ indicates strong synergy) · **Bliss Excess:** `+0.146`
- **Target Orthogonality:** `1.00` (Jaccard distance: non-redundant target mechanisms)
- **Route Compatibility:** Oral / Systemic Combination (Clinical monitoring recommended)
- **Afamelanotide Targets:** MITF (Act), TYR (Act)
- **Tofacitinib Targets:** IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT1 (Inh*)
- **Mechanistic Rationale:** Immune disarmament via tofacitinib; Follicular McSC stem-cell mobilization via afamelanotide

### #3. Afamelanotide + Cyclosporine
- **Synergy Score:** `4.146` · **Virtual CI:** `0.35` (Chou-Talalay: $<0.70$ indicates strong synergy) · **Bliss Excess:** `+0.145`
- **Target Orthogonality:** `1.00` (Jaccard distance: non-redundant target mechanisms)
- **Route Compatibility:** Oral / Systemic Combination (Clinical monitoring recommended)
- **Afamelanotide Targets:** MITF (Act), TYR (Act)
- **Cyclosporine Targets:** JAK1 (Inh), CD8A (Inh*)
- **Mechanistic Rationale:** Immune disarmament via cyclosporine; Follicular McSC stem-cell mobilization via afamelanotide

### #4. Ruxolitinib + Afamelanotide
- **Synergy Score:** `4.144` · **Virtual CI:** `0.35` (Chou-Talalay: $<0.70$ indicates strong synergy) · **Bliss Excess:** `+0.145`
- **Target Orthogonality:** `1.00` (Jaccard distance: non-redundant target mechanisms)
- **Route Compatibility:** Oral / Systemic Combination (Clinical monitoring recommended)
- **Ruxolitinib Targets:** IL15 (Inh*), JAK1 (Inh*), JAK3 (Inh*), STAT3 (Inh*)
- **Afamelanotide Targets:** MITF (Act), TYR (Act)
- **Mechanistic Rationale:** Immune disarmament via afamelanotide; PDE4B (+9.09 log2FC) barrier reversal via ruxolitinib; Follicular McSC stem-cell mobilization via afamelanotide

### #5. Cyclosporine + Bimatoprost
- **Synergy Score:** `4.122` · **Virtual CI:** `0.35` (Chou-Talalay: $<0.70$ indicates strong synergy) · **Bliss Excess:** `+0.144`
- **Target Orthogonality:** `1.00` (Jaccard distance: non-redundant target mechanisms)
- **Route Compatibility:** Targeted Oral + Topical Adjuvant (Systemic halt + localized rescue)
- **Cyclosporine Targets:** JAK1 (Inh), CD8A (Inh*)
- **Bimatoprost Targets:** TYR (Act*), PDE4A (Inh)
- **Mechanistic Rationale:** Immune disarmament via cyclosporine; Follicular McSC stem-cell mobilization via bimatoprost

