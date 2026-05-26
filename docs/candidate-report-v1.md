# Therapeutic Candidate Report v1

**Generated:** 2026-05-26T17:55:15.545987+00:00  
**Engine:** v1.0.0  
**Status:** Research hypothesis ranking — not medical advice, not an endorsement.

## Methodology

Candidates are aggregated from Open Targets drug priors (Phase 2+), knowledge-graph edges linking drugs to vitiligo, registered trials whose interventions match the drug stem, and semantic literature retrieval for each intent query. Scores are transparent and reproducible from the local corpus snapshot.

### Score rubric

| Component | Max points | Source |
|-----------|------------|--------|
| Prior clinical stage | 40 | Open Targets (`EFO_0004208`) |
| Knowledge graph | 40 | `treats` / `investigates` / trial links |
| Registered trials | 35 | CT.gov, EU CTR, ICTRP |
| Literature retrieval | 20 | Semantic search (top-K per intent) |

**Corpus snapshot:** 14,245 documents, 344 trials, 1044 graph entities.

## Global top candidates (aggregated across intents)

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 117 (prior 40 + graph 22 + trials 35 + literature 20)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase TYK2 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL1789941`  

**Trials:**
- [euctr:2024-513171-41-00] INCB 18424-309 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT07595939] Efficacy and Safety of Ruxolitinib Cream in Chinese Children Aged 2-11 Years With Non-segmental Vitiligo — NOT_YET_RECRUITING, PHASE3, no results yet
- [ctgov:NCT05750823] A Study to Assess the Safety and Efficacy of Ruxolitinib Cream in Participants With Genital Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07153666] A Real-world Study on the Influencing Factors of Efficacy of Ruxolitinib Cream in Vitiligo — RECRUITING, —, no results yet

**Graph:**
- ruxolitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pmc:PMC12804599] Laser-assisted drug delivery of topical ruxolitinib for treatment-refractory stable nonsegmental vitiligo: A case analyzed using noninvasive imaging modalities (2026) — Other, score=0.9013
- [pubmed:41551626] Laser-assisted drug delivery of topical ruxolitinib for treatment-refractory stable nonsegmental vitiligo: A case analyzed using noninvasive imaging modalities. (2026) — Other, score=0.9008
- [pubmed:35787401] Addition of Narrow-Band UVB Phototherapy to Ruxolitinib Cream in Patients With Vitiligo. (2022) — Other, score=0.9004
- [pubmed:39011655] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream over 52 weeks. (2025) — Other, score=0.8985
- [pmc:PMC11851260] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream over 52 weeks (2024) — Other, score=0.8973

### #2 UPADACITINIB

**Evidence strength:** strong  
**Score:** 91 (prior 30 + graph 22 + trials 23 + literature 16)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor; Tyrosine-protein kinase TYK2 inhibitor  
**Open Targets ID:** `CHEMBL3622821`  

**Trials:**
- [euctr:2023-506195-27-00] M19-044 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06118411] A Study To Assess Adverse Events and Effectiveness of Upadacitinib Oral Tablets in Adult and Adolescent Participants With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06454461] Efficacy of Upadacitinib After NECS in Vitiligo — RECRUITING, NA, no results yet
- [ctgov:NCT04927975] Study to Evaluate Adverse Events and Change in Disease Activity With Oral Tablets of Upadacitinib in Adult Participants With Non-Segmental Vitiligo — COMPLETED, PHASE2, results

**Graph:**
- Upadacitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pmc:PMC11169949] Once-daily upadacitinib versus placebo in adults with extensive non-segmental vitiligo: a phase 2, multicentre, randomised, double-blind, placebo-controlled, dose-ranging study (2024) — Other, score=0.852
- [pubmed:39704810] Repigmentation in non-segmental vitiligo using the Janus kinase inhibitor upadacitinib, a retrospective case series. (2024) — Case series, score=0.8502
- [pubmed:38873632] Once-daily upadacitinib versus placebo in adults with extensive non-segmental vitiligo: a phase 2, multicentre, randomised, double-blind, placebo-controlled, dose-ranging study. (2024) — Other, score=0.8489

### #3 RITLECITINIB

**Evidence strength:** strong  
**Score:** 85 (prior 20 + graph 22 + trials 35 + literature 8)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL5314649`  

**Trials:**
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [ctgov:NCT06163326] A 52-Week Study to Learn About the Safety and Effects of Ritlecitinib in Participants With Nonsegmental Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:39508655] Ritlecitinib rescues exacerbated vitiligo during the JAK1 inhibitor therapy: More than a coincidence? (2024) — Other, score=0.8403

### #4 POVORCITINIB

**Evidence strength:** strong  
**Score:** 81 (prior 30 + graph 22 + trials 25 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-506011-18-00] INCB 54707-304 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531

### #5 TACROLIMUS ANHYDROUS

**Evidence strength:** strong  
**Score:** 71 (prior 30 + graph 22 + trials 15 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT07532330] Tyrosine Vs Tacrolimus With NB-UVB in Vitiligo — ACTIVE_NOT_RECRUITING, NA, no results yet
- [ctgov:NCT07519031] Study of Umbilical Cord Mesenchymal Stem Cell-Derived Exosomes in Vitiligo — NOT_YET_RECRUITING, PHASE1, PHASE2, no results yet
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07307534] Nevus Removal vs. Conservative Treatment in Halo Nevus With Vitiligo: A Randomized Study — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06880042] COMPARISON OF EFFICACY AND SAFETY OF NARROWBAND UVB WITH 0.1% TACROLIMUS VS NARROWBAND UVB WITH 0.005% CALCIPOTRIOL IN TREATMENT OF VITILIGO — ENROLLING_BY_INVITATION, EARLY_PHASE1, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:12399684] Repigmentation of vitiligo with topical tacrolimus. (2002) — Case report, score=0.8248

### #6 AFAMELANOTIDE

**Evidence strength:** moderate  
**Score:** 65 (prior 30 + graph 22 + trials 13 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet
- [ctgov:NCT01382589] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo — COMPLETED, PHASE2, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #7 FLUOROURACIL

**Evidence strength:** moderate  
**Score:** 63 (prior 25 + graph 20 + trials 10 + literature 8)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Thymidylate synthase inhibitor  
**Open Targets ID:** `CHEMBL185`  

**Trials:**
- [ctgov:NCT07398807] Effectiveness of Micro-needling With 5 Fluorouracil Versus Potent Topical Steroids in the Treatment of Limited Vitiligo — RECRUITING, EARLY_PHASE1, no results yet
- [ctgov:NCT05536856] Topical 5-Fluorouracil Effervescent Powder in the Treatment of Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT06209138] 5-fluorouracil for Treatment of Stable Vitiligo — COMPLETED, NA, no results yet
- [ctgov:NCT05513924] Comparative Study Between Topical 5-fluorouracil and Latanoprost in Vitiligo. — COMPLETED, PHASE2, PHASE3, no results yet
- [ctgov:NCT05008887] Fractional CO2 Laser-assisted Cutaneous Delivery of Methotrexate Versus 5-fluorouracil in Stable Non-segmental Vitiligo — UNKNOWN, PHASE4, no results yet

**Graph:**
- FLUOROURACIL —[treats]→ Vitiligo (conf=0.82, structured)

**Literature (intent retrieval):**
- [pmc:PMC11928802] Repigmentation of vitiligo with 5-fluorouracil tattooing in combination with topical ruxolitinib: A case report (2025) — Other, score=0.8785
- [pubmed:40123791] Repigmentation of vitiligo with 5-fluorouracil tattooing in combination with topical ruxolitinib: A case report. (2025) — Case report, score=0.8767

### #8 MONOBENZONE

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosinase inhibitor  
**Open Targets ID:** `CHEMBL1388`  

**Graph:**
- Monobenzone —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #9 TRIOXSALEN

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Open Targets ID:** `CHEMBL1475`  

**Graph:**
- TRIOXSALEN —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #10 BARICITINIB

**Evidence strength:** moderate  
**Score:** 61 (prior 20 + graph 20 + trials 5 + literature 16)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL2105759`  

**Trials:**
- [ctgov:NCT04822584] Evaluation of Effect and Tolerance of the Association of Baricitinib and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT06768840] Vitiligo, New Treatment and Serum s100B — RECRUITING, PHASE2, PHASE3, no results yet
- [ctgov:NCT05950542] Evaluation Safety ,Efficacy Baricitinib Plus Excimer Light Versus Excimer Light Alone in Non Segmental Vitiligo — UNKNOWN, —, no results yet

**Graph:**
- Baricitinib —[treats]→ Vitiligo (conf=0.82, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:40682379] 308 nm Excimer Laser Combined With JAK Inhibitors for Adult Localized Non-Segmental Vitiligo: A Multicenter Randomized Controlled Trial. (2025) — RCT, score=0.8513
- [pubmed:39723343] Combination Therapy with Baricitinib and Narrowband Ultraviolet B for Active Non-Segmental Vitiligo: A Retrospective Controlled Study. (2024) — Other, score=0.8453
- [pmc:PMC11668684] Combination Therapy with Baricitinib and Narrowband Ultraviolet B for Active Non-Segmental Vitiligo: A Retrospective Controlled Study (2024) — Other, score=0.8398

## Intent: Stop spread — active non-segmental vitiligo

**Query:** `stop spread active non-segmental vitiligo JAK inhibitor`  
**Goal:** spread_arrest

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 113 (prior 40 + graph 22 + trials 35 + literature 16)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase TYK2 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL1789941`  

**Trials:**
- [euctr:2024-513171-41-00] INCB 18424-309 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT07595939] Efficacy and Safety of Ruxolitinib Cream in Chinese Children Aged 2-11 Years With Non-segmental Vitiligo — NOT_YET_RECRUITING, PHASE3, no results yet
- [ctgov:NCT05750823] A Study to Assess the Safety and Efficacy of Ruxolitinib Cream in Participants With Genital Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07153666] A Real-world Study on the Influencing Factors of Efficacy of Ruxolitinib Cream in Vitiligo — RECRUITING, —, no results yet

**Graph:**
- ruxolitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pmc:PMC12126450] Efficacy and Safety of JAK Inhibitors in the Management of Vitiligo: A Systematic Review and Meta-analysis (2025) — Review, score=0.8431
- [pubmed:40332460] Efficacy and Safety of JAK Inhibitors in the Management of Vitiligo: A Systematic Review and Meta-analysis. (2025) — Review, score=0.8431
- [pubmed:39134884] A meta-analysis of therapeutic trials of topical ruxolitinib cream for the treatment of vitiligo: therapeutic efficacy, safety, and implications for therapeutic practice. (2024) — Meta-analysis, score=0.8426

### #2 UPADACITINIB

**Evidence strength:** strong  
**Score:** 91 (prior 30 + graph 22 + trials 23 + literature 16)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor; Tyrosine-protein kinase TYK2 inhibitor  
**Open Targets ID:** `CHEMBL3622821`  

**Trials:**
- [euctr:2023-506195-27-00] M19-044 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06118411] A Study To Assess Adverse Events and Effectiveness of Upadacitinib Oral Tablets in Adult and Adolescent Participants With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06454461] Efficacy of Upadacitinib After NECS in Vitiligo — RECRUITING, NA, no results yet
- [ctgov:NCT04927975] Study to Evaluate Adverse Events and Change in Disease Activity With Oral Tablets of Upadacitinib in Adult Participants With Non-Segmental Vitiligo — COMPLETED, PHASE2, results

**Graph:**
- Upadacitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pmc:PMC11169949] Once-daily upadacitinib versus placebo in adults with extensive non-segmental vitiligo: a phase 2, multicentre, randomised, double-blind, placebo-controlled, dose-ranging study (2024) — Other, score=0.852
- [pubmed:39704810] Repigmentation in non-segmental vitiligo using the Janus kinase inhibitor upadacitinib, a retrospective case series. (2024) — Case series, score=0.8502
- [pubmed:38873632] Once-daily upadacitinib versus placebo in adults with extensive non-segmental vitiligo: a phase 2, multicentre, randomised, double-blind, placebo-controlled, dose-ranging study. (2024) — Other, score=0.8489

### #3 RITLECITINIB

**Evidence strength:** strong  
**Score:** 85 (prior 20 + graph 22 + trials 35 + literature 8)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL5314649`  

**Trials:**
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [ctgov:NCT06163326] A 52-Week Study to Learn About the Safety and Effects of Ritlecitinib in Participants With Nonsegmental Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:39508655] Ritlecitinib rescues exacerbated vitiligo during the JAK1 inhibitor therapy: More than a coincidence? (2024) — Other, score=0.8403

### #4 POVORCITINIB

**Evidence strength:** strong  
**Score:** 81 (prior 30 + graph 22 + trials 25 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-506011-18-00] INCB 54707-304 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531

### #5 TACROLIMUS ANHYDROUS

**Evidence strength:** moderate  
**Score:** 67 (prior 30 + graph 22 + trials 15 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT07532330] Tyrosine Vs Tacrolimus With NB-UVB in Vitiligo — ACTIVE_NOT_RECRUITING, NA, no results yet
- [ctgov:NCT07519031] Study of Umbilical Cord Mesenchymal Stem Cell-Derived Exosomes in Vitiligo — NOT_YET_RECRUITING, PHASE1, PHASE2, no results yet
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07307534] Nevus Removal vs. Conservative Treatment in Halo Nevus With Vitiligo: A Randomized Study — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06880042] COMPARISON OF EFFICACY AND SAFETY OF NARROWBAND UVB WITH 0.1% TACROLIMUS VS NARROWBAND UVB WITH 0.005% CALCIPOTRIOL IN TREATMENT OF VITILIGO — ENROLLING_BY_INVITATION, EARLY_PHASE1, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #6 AFAMELANOTIDE

**Evidence strength:** moderate  
**Score:** 65 (prior 30 + graph 22 + trials 13 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet
- [ctgov:NCT01382589] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo — COMPLETED, PHASE2, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #7 MONOBENZONE

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosinase inhibitor  
**Open Targets ID:** `CHEMBL1388`  

**Graph:**
- Monobenzone —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #8 TRIOXSALEN

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Open Targets ID:** `CHEMBL1475`  

**Graph:**
- TRIOXSALEN —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #9 BARICITINIB

**Evidence strength:** moderate  
**Score:** 61 (prior 20 + graph 20 + trials 5 + literature 16)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL2105759`  

**Trials:**
- [ctgov:NCT04822584] Evaluation of Effect and Tolerance of the Association of Baricitinib and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT06768840] Vitiligo, New Treatment and Serum s100B — RECRUITING, PHASE2, PHASE3, no results yet
- [ctgov:NCT05950542] Evaluation Safety ,Efficacy Baricitinib Plus Excimer Light Versus Excimer Light Alone in Non Segmental Vitiligo — UNKNOWN, —, no results yet

**Graph:**
- Baricitinib —[treats]→ Vitiligo (conf=0.82, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:40682379] 308 nm Excimer Laser Combined With JAK Inhibitors for Adult Localized Non-Segmental Vitiligo: A Multicenter Randomized Controlled Trial. (2025) — RCT, score=0.8513
- [pubmed:39723343] Combination Therapy with Baricitinib and Narrowband Ultraviolet B for Active Non-Segmental Vitiligo: A Retrospective Controlled Study. (2024) — Other, score=0.8453
- [pmc:PMC11668684] Combination Therapy with Baricitinib and Narrowband Ultraviolet B for Active Non-Segmental Vitiligo: A Retrospective Controlled Study (2024) — Other, score=0.8398

### #10 METHOTREXATE

**Evidence strength:** moderate  
**Score:** 57 (prior 30 + graph 22 + trials 5 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Dihydrofolate reductase inhibitor  
**Open Targets ID:** `CHEMBL34259`  

**Trials:**
- [ctgov:NCT04237103] Combination of Methotrexate and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT07352293] The Value of Methotrexate in NCES for Stable Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT07208890] Methotrexate Iontophoresis Versus Methotrexate 1% Gel on Depigmentation in Vitiligo Patients — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06877455] Topical Methotrexate with Fractional CO2 Laser in Treatment of Non Segmental Vitiligo — NOT_YET_RECRUITING, NA, no results yet
- [euctr:2024-512766-34-00] CHUBX 2017/44 — ENDED, PHASE2, no results yet

**Graph:**
- METHOTREXATE —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

## Intent: Drive repigmentation — non-segmental vitiligo

**Query:** `repigmentation non-segmental vitiligo ruxolitinib phototherapy`  
**Goal:** repigmentation

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 117 (prior 40 + graph 22 + trials 35 + literature 20)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase TYK2 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL1789941`  

**Trials:**
- [euctr:2024-513171-41-00] INCB 18424-309 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT07595939] Efficacy and Safety of Ruxolitinib Cream in Chinese Children Aged 2-11 Years With Non-segmental Vitiligo — NOT_YET_RECRUITING, PHASE3, no results yet
- [ctgov:NCT05750823] A Study to Assess the Safety and Efficacy of Ruxolitinib Cream in Participants With Genital Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07153666] A Real-world Study on the Influencing Factors of Efficacy of Ruxolitinib Cream in Vitiligo — RECRUITING, —, no results yet

**Graph:**
- ruxolitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pmc:PMC12804599] Laser-assisted drug delivery of topical ruxolitinib for treatment-refractory stable nonsegmental vitiligo: A case analyzed using noninvasive imaging modalities (2026) — Other, score=0.9013
- [pubmed:41551626] Laser-assisted drug delivery of topical ruxolitinib for treatment-refractory stable nonsegmental vitiligo: A case analyzed using noninvasive imaging modalities. (2026) — Other, score=0.9008
- [pubmed:35787401] Addition of Narrow-Band UVB Phototherapy to Ruxolitinib Cream in Patients With Vitiligo. (2022) — Other, score=0.9004
- [pubmed:39011655] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream over 52 weeks. (2025) — Other, score=0.8985
- [pmc:PMC11851260] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream over 52 weeks (2024) — Other, score=0.8973

### #2 RITLECITINIB

**Evidence strength:** strong  
**Score:** 85 (prior 20 + graph 22 + trials 35 + literature 8)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL5314649`  

**Trials:**
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [ctgov:NCT06163326] A 52-Week Study to Learn About the Safety and Effects of Ritlecitinib in Participants With Nonsegmental Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pmc:PMC12281511] Successful repigmentation with ritlecitinib and combined home-based phototherapy in an intractable case of generalized vitiligo☆ (2025) — Other, score=0.8845
- [pubmed:40664119] Successful repigmentation with ritlecitinib and combined home-based phototherapy in an intractable case of generalized vitiligo. (2025) — Other, score=0.8821

### #3 POVORCITINIB

**Evidence strength:** strong  
**Score:** 77 (prior 30 + graph 22 + trials 25 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-506011-18-00] INCB 54707-304 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #4 UPADACITINIB

**Evidence strength:** strong  
**Score:** 75 (prior 30 + graph 22 + trials 23 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor; Tyrosine-protein kinase TYK2 inhibitor  
**Open Targets ID:** `CHEMBL3622821`  

**Trials:**
- [euctr:2023-506195-27-00] M19-044 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06118411] A Study To Assess Adverse Events and Effectiveness of Upadacitinib Oral Tablets in Adult and Adolescent Participants With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06454461] Efficacy of Upadacitinib After NECS in Vitiligo — RECRUITING, NA, no results yet
- [ctgov:NCT04927975] Study to Evaluate Adverse Events and Change in Disease Activity With Oral Tablets of Upadacitinib in Adult Participants With Non-Segmental Vitiligo — COMPLETED, PHASE2, results

**Graph:**
- Upadacitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #5 TACROLIMUS ANHYDROUS

**Evidence strength:** moderate  
**Score:** 67 (prior 30 + graph 22 + trials 15 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT07532330] Tyrosine Vs Tacrolimus With NB-UVB in Vitiligo — ACTIVE_NOT_RECRUITING, NA, no results yet
- [ctgov:NCT07519031] Study of Umbilical Cord Mesenchymal Stem Cell-Derived Exosomes in Vitiligo — NOT_YET_RECRUITING, PHASE1, PHASE2, no results yet
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07307534] Nevus Removal vs. Conservative Treatment in Halo Nevus With Vitiligo: A Randomized Study — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06880042] COMPARISON OF EFFICACY AND SAFETY OF NARROWBAND UVB WITH 0.1% TACROLIMUS VS NARROWBAND UVB WITH 0.005% CALCIPOTRIOL IN TREATMENT OF VITILIGO — ENROLLING_BY_INVITATION, EARLY_PHASE1, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #6 AFAMELANOTIDE

**Evidence strength:** moderate  
**Score:** 65 (prior 30 + graph 22 + trials 13 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet
- [ctgov:NCT01382589] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo — COMPLETED, PHASE2, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #7 FLUOROURACIL

**Evidence strength:** moderate  
**Score:** 63 (prior 25 + graph 20 + trials 10 + literature 8)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Thymidylate synthase inhibitor  
**Open Targets ID:** `CHEMBL185`  

**Trials:**
- [ctgov:NCT07398807] Effectiveness of Micro-needling With 5 Fluorouracil Versus Potent Topical Steroids in the Treatment of Limited Vitiligo — RECRUITING, EARLY_PHASE1, no results yet
- [ctgov:NCT05536856] Topical 5-Fluorouracil Effervescent Powder in the Treatment of Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT06209138] 5-fluorouracil for Treatment of Stable Vitiligo — COMPLETED, NA, no results yet
- [ctgov:NCT05513924] Comparative Study Between Topical 5-fluorouracil and Latanoprost in Vitiligo. — COMPLETED, PHASE2, PHASE3, no results yet
- [ctgov:NCT05008887] Fractional CO2 Laser-assisted Cutaneous Delivery of Methotrexate Versus 5-fluorouracil in Stable Non-segmental Vitiligo — UNKNOWN, PHASE4, no results yet

**Graph:**
- FLUOROURACIL —[treats]→ Vitiligo (conf=0.82, structured)

**Literature (intent retrieval):**
- [pmc:PMC11928802] Repigmentation of vitiligo with 5-fluorouracil tattooing in combination with topical ruxolitinib: A case report (2025) — Other, score=0.8785
- [pubmed:40123791] Repigmentation of vitiligo with 5-fluorouracil tattooing in combination with topical ruxolitinib: A case report. (2025) — Case report, score=0.8767

### #8 MONOBENZONE

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosinase inhibitor  
**Open Targets ID:** `CHEMBL1388`  

**Graph:**
- Monobenzone —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #9 TRIOXSALEN

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Open Targets ID:** `CHEMBL1475`  

**Graph:**
- TRIOXSALEN —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #10 METHOTREXATE

**Evidence strength:** moderate  
**Score:** 57 (prior 30 + graph 22 + trials 5 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Dihydrofolate reductase inhibitor  
**Open Targets ID:** `CHEMBL34259`  

**Trials:**
- [ctgov:NCT04237103] Combination of Methotrexate and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT07352293] The Value of Methotrexate in NCES for Stable Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT07208890] Methotrexate Iontophoresis Versus Methotrexate 1% Gel on Depigmentation in Vitiligo Patients — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06877455] Topical Methotrexate with Fractional CO2 Laser in Treatment of Non Segmental Vitiligo — NOT_YET_RECRUITING, NA, no results yet
- [euctr:2024-512766-34-00] CHUBX 2017/44 — ENDED, PHASE2, no results yet

**Graph:**
- METHOTREXATE —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

## Intent: JAK inhibitor + NB-UVB combination

**Query:** `topical ruxolitinib narrowband UVB combination vitiligo`  
**Goal:** combination

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 117 (prior 40 + graph 22 + trials 35 + literature 20)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase TYK2 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL1789941`  

**Trials:**
- [euctr:2024-513171-41-00] INCB 18424-309 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT07595939] Efficacy and Safety of Ruxolitinib Cream in Chinese Children Aged 2-11 Years With Non-segmental Vitiligo — NOT_YET_RECRUITING, PHASE3, no results yet
- [ctgov:NCT05750823] A Study to Assess the Safety and Efficacy of Ruxolitinib Cream in Participants With Genital Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07153666] A Real-world Study on the Influencing Factors of Efficacy of Ruxolitinib Cream in Vitiligo — RECRUITING, —, no results yet

**Graph:**
- ruxolitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:35787401] Addition of Narrow-Band UVB Phototherapy to Ruxolitinib Cream in Patients With Vitiligo. (2022) — Other, score=0.9277
- [pubmed:29438765] Treatment of vitiligo with the topical Janus kinase inhibitor ruxolitinib: A 32-week open-label extension study with optional narrow-band ultraviolet B. (2018) — Other, score=0.898
- [pubmed:33248492] Ruxolitinib cream for the treatment of vitiligo. (2020) — Other, score=0.8955
- [pubmed:37450618] Eyelid Vitiligo Treatment with Topical Ruxolitinib. (2024) — Other, score=0.8854
- [pubmed:41386328] Efficacy and safety of ruxolitinib cream combined with narrow-band UVB phototherapy for treatment of vitiligo. (2025) — Other, score=0.8827

### #2 POVORCITINIB

**Evidence strength:** strong  
**Score:** 77 (prior 30 + graph 22 + trials 25 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-506011-18-00] INCB 54707-304 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #3 RITLECITINIB

**Evidence strength:** strong  
**Score:** 77 (prior 20 + graph 22 + trials 35 + literature 0)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL5314649`  

**Trials:**
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [ctgov:NCT06163326] A 52-Week Study to Learn About the Safety and Effects of Ritlecitinib in Participants With Nonsegmental Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #4 UPADACITINIB

**Evidence strength:** strong  
**Score:** 75 (prior 30 + graph 22 + trials 23 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor; Tyrosine-protein kinase TYK2 inhibitor  
**Open Targets ID:** `CHEMBL3622821`  

**Trials:**
- [euctr:2023-506195-27-00] M19-044 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06118411] A Study To Assess Adverse Events and Effectiveness of Upadacitinib Oral Tablets in Adult and Adolescent Participants With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06454461] Efficacy of Upadacitinib After NECS in Vitiligo — RECRUITING, NA, no results yet
- [ctgov:NCT04927975] Study to Evaluate Adverse Events and Change in Disease Activity With Oral Tablets of Upadacitinib in Adult Participants With Non-Segmental Vitiligo — COMPLETED, PHASE2, results

**Graph:**
- Upadacitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #5 TACROLIMUS ANHYDROUS

**Evidence strength:** moderate  
**Score:** 67 (prior 30 + graph 22 + trials 15 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT07532330] Tyrosine Vs Tacrolimus With NB-UVB in Vitiligo — ACTIVE_NOT_RECRUITING, NA, no results yet
- [ctgov:NCT07519031] Study of Umbilical Cord Mesenchymal Stem Cell-Derived Exosomes in Vitiligo — NOT_YET_RECRUITING, PHASE1, PHASE2, no results yet
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07307534] Nevus Removal vs. Conservative Treatment in Halo Nevus With Vitiligo: A Randomized Study — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06880042] COMPARISON OF EFFICACY AND SAFETY OF NARROWBAND UVB WITH 0.1% TACROLIMUS VS NARROWBAND UVB WITH 0.005% CALCIPOTRIOL IN TREATMENT OF VITILIGO — ENROLLING_BY_INVITATION, EARLY_PHASE1, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #6 AFAMELANOTIDE

**Evidence strength:** moderate  
**Score:** 65 (prior 30 + graph 22 + trials 13 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet
- [ctgov:NCT01382589] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo — COMPLETED, PHASE2, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #7 MONOBENZONE

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosinase inhibitor  
**Open Targets ID:** `CHEMBL1388`  

**Graph:**
- Monobenzone —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #8 TRIOXSALEN

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Open Targets ID:** `CHEMBL1475`  

**Graph:**
- TRIOXSALEN —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #9 METHOTREXATE

**Evidence strength:** moderate  
**Score:** 57 (prior 30 + graph 22 + trials 5 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Dihydrofolate reductase inhibitor  
**Open Targets ID:** `CHEMBL34259`  

**Trials:**
- [ctgov:NCT04237103] Combination of Methotrexate and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT07352293] The Value of Methotrexate in NCES for Stable Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT07208890] Methotrexate Iontophoresis Versus Methotrexate 1% Gel on Depigmentation in Vitiligo Patients — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06877455] Topical Methotrexate with Fractional CO2 Laser in Treatment of Non Segmental Vitiligo — NOT_YET_RECRUITING, NA, no results yet
- [euctr:2024-512766-34-00] CHUBX 2017/44 — ENDED, PHASE2, no results yet

**Graph:**
- METHOTREXATE —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #10 FLUOROURACIL

**Evidence strength:** moderate  
**Score:** 55 (prior 25 + graph 20 + trials 10 + literature 0)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Thymidylate synthase inhibitor  
**Open Targets ID:** `CHEMBL185`  

**Trials:**
- [ctgov:NCT07398807] Effectiveness of Micro-needling With 5 Fluorouracil Versus Potent Topical Steroids in the Treatment of Limited Vitiligo — RECRUITING, EARLY_PHASE1, no results yet
- [ctgov:NCT05536856] Topical 5-Fluorouracil Effervescent Powder in the Treatment of Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT06209138] 5-fluorouracil for Treatment of Stable Vitiligo — COMPLETED, NA, no results yet
- [ctgov:NCT05513924] Comparative Study Between Topical 5-fluorouracil and Latanoprost in Vitiligo. — COMPLETED, PHASE2, PHASE3, no results yet
- [ctgov:NCT05008887] Fractional CO2 Laser-assisted Cutaneous Delivery of Methotrexate Versus 5-fluorouracil in Stable Non-segmental Vitiligo — UNKNOWN, PHASE4, no results yet

**Graph:**
- FLUOROURACIL —[treats]→ Vitiligo (conf=0.82, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

## Intent: Acral / recalcitrant site repigmentation

**Query:** `acral vitiligo hands feet repigmentation treatment`  
**Goal:** repigmentation

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 97 (prior 40 + graph 22 + trials 35 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase TYK2 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL1789941`  

**Trials:**
- [euctr:2024-513171-41-00] INCB 18424-309 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT07595939] Efficacy and Safety of Ruxolitinib Cream in Chinese Children Aged 2-11 Years With Non-segmental Vitiligo — NOT_YET_RECRUITING, PHASE3, no results yet
- [ctgov:NCT05750823] A Study to Assess the Safety and Efficacy of Ruxolitinib Cream in Participants With Genital Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07153666] A Real-world Study on the Influencing Factors of Efficacy of Ruxolitinib Cream in Vitiligo — RECRUITING, —, no results yet

**Graph:**
- ruxolitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #2 POVORCITINIB

**Evidence strength:** strong  
**Score:** 77 (prior 30 + graph 22 + trials 25 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-506011-18-00] INCB 54707-304 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #3 RITLECITINIB

**Evidence strength:** strong  
**Score:** 77 (prior 20 + graph 22 + trials 35 + literature 0)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL5314649`  

**Trials:**
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [ctgov:NCT06163326] A 52-Week Study to Learn About the Safety and Effects of Ritlecitinib in Participants With Nonsegmental Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #4 UPADACITINIB

**Evidence strength:** strong  
**Score:** 75 (prior 30 + graph 22 + trials 23 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor; Tyrosine-protein kinase TYK2 inhibitor  
**Open Targets ID:** `CHEMBL3622821`  

**Trials:**
- [euctr:2023-506195-27-00] M19-044 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06118411] A Study To Assess Adverse Events and Effectiveness of Upadacitinib Oral Tablets in Adult and Adolescent Participants With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06454461] Efficacy of Upadacitinib After NECS in Vitiligo — RECRUITING, NA, no results yet
- [ctgov:NCT04927975] Study to Evaluate Adverse Events and Change in Disease Activity With Oral Tablets of Upadacitinib in Adult Participants With Non-Segmental Vitiligo — COMPLETED, PHASE2, results

**Graph:**
- Upadacitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #5 TACROLIMUS ANHYDROUS

**Evidence strength:** strong  
**Score:** 71 (prior 30 + graph 22 + trials 15 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT07532330] Tyrosine Vs Tacrolimus With NB-UVB in Vitiligo — ACTIVE_NOT_RECRUITING, NA, no results yet
- [ctgov:NCT07519031] Study of Umbilical Cord Mesenchymal Stem Cell-Derived Exosomes in Vitiligo — NOT_YET_RECRUITING, PHASE1, PHASE2, no results yet
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07307534] Nevus Removal vs. Conservative Treatment in Halo Nevus With Vitiligo: A Randomized Study — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06880042] COMPARISON OF EFFICACY AND SAFETY OF NARROWBAND UVB WITH 0.1% TACROLIMUS VS NARROWBAND UVB WITH 0.005% CALCIPOTRIOL IN TREATMENT OF VITILIGO — ENROLLING_BY_INVITATION, EARLY_PHASE1, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:12399684] Repigmentation of vitiligo with topical tacrolimus. (2002) — Case report, score=0.8248

### #6 AFAMELANOTIDE

**Evidence strength:** moderate  
**Score:** 65 (prior 30 + graph 22 + trials 13 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet
- [ctgov:NCT01382589] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo — COMPLETED, PHASE2, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #7 MONOBENZONE

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosinase inhibitor  
**Open Targets ID:** `CHEMBL1388`  

**Graph:**
- Monobenzone —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #8 TRIOXSALEN

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Open Targets ID:** `CHEMBL1475`  

**Graph:**
- TRIOXSALEN —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #9 METHOTREXATE

**Evidence strength:** moderate  
**Score:** 57 (prior 30 + graph 22 + trials 5 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Dihydrofolate reductase inhibitor  
**Open Targets ID:** `CHEMBL34259`  

**Trials:**
- [ctgov:NCT04237103] Combination of Methotrexate and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT07352293] The Value of Methotrexate in NCES for Stable Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT07208890] Methotrexate Iontophoresis Versus Methotrexate 1% Gel on Depigmentation in Vitiligo Patients — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06877455] Topical Methotrexate with Fractional CO2 Laser in Treatment of Non Segmental Vitiligo — NOT_YET_RECRUITING, NA, no results yet
- [euctr:2024-512766-34-00] CHUBX 2017/44 — ENDED, PHASE2, no results yet

**Graph:**
- METHOTREXATE —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #10 FLUOROURACIL

**Evidence strength:** moderate  
**Score:** 55 (prior 25 + graph 20 + trials 10 + literature 0)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Thymidylate synthase inhibitor  
**Open Targets ID:** `CHEMBL185`  

**Trials:**
- [ctgov:NCT07398807] Effectiveness of Micro-needling With 5 Fluorouracil Versus Potent Topical Steroids in the Treatment of Limited Vitiligo — RECRUITING, EARLY_PHASE1, no results yet
- [ctgov:NCT05536856] Topical 5-Fluorouracil Effervescent Powder in the Treatment of Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT06209138] 5-fluorouracil for Treatment of Stable Vitiligo — COMPLETED, NA, no results yet
- [ctgov:NCT05513924] Comparative Study Between Topical 5-fluorouracil and Latanoprost in Vitiligo. — COMPLETED, PHASE2, PHASE3, no results yet
- [ctgov:NCT05008887] Fractional CO2 Laser-assisted Cutaneous Delivery of Methotrexate Versus 5-fluorouracil in Stable Non-segmental Vitiligo — UNKNOWN, PHASE4, no results yet

**Graph:**
- FLUOROURACIL —[treats]→ Vitiligo (conf=0.82, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

## Intent: Facial vitiligo repigmentation

**Query:** `facial vitiligo repigmentation treatment face`  
**Goal:** repigmentation

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 105 (prior 40 + graph 22 + trials 35 + literature 8)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase TYK2 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL1789941`  

**Trials:**
- [euctr:2024-513171-41-00] INCB 18424-309 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT07595939] Efficacy and Safety of Ruxolitinib Cream in Chinese Children Aged 2-11 Years With Non-segmental Vitiligo — NOT_YET_RECRUITING, PHASE3, no results yet
- [ctgov:NCT05750823] A Study to Assess the Safety and Efficacy of Ruxolitinib Cream in Participants With Genital Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07153666] A Real-world Study on the Influencing Factors of Efficacy of Ruxolitinib Cream in Vitiligo — RECRUITING, —, no results yet

**Graph:**
- ruxolitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pmc:PMC11851260] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream over 52 weeks (2024) — Other, score=0.8608
- [pubmed:39011655] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream over 52 weeks. (2025) — Other, score=0.8581

### #2 POVORCITINIB

**Evidence strength:** strong  
**Score:** 77 (prior 30 + graph 22 + trials 25 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-506011-18-00] INCB 54707-304 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #3 RITLECITINIB

**Evidence strength:** strong  
**Score:** 77 (prior 20 + graph 22 + trials 35 + literature 0)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL5314649`  

**Trials:**
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [ctgov:NCT06163326] A 52-Week Study to Learn About the Safety and Effects of Ritlecitinib in Participants With Nonsegmental Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #4 UPADACITINIB

**Evidence strength:** strong  
**Score:** 75 (prior 30 + graph 22 + trials 23 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor; Tyrosine-protein kinase TYK2 inhibitor  
**Open Targets ID:** `CHEMBL3622821`  

**Trials:**
- [euctr:2023-506195-27-00] M19-044 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT06118411] A Study To Assess Adverse Events and Effectiveness of Upadacitinib Oral Tablets in Adult and Adolescent Participants With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06454461] Efficacy of Upadacitinib After NECS in Vitiligo — RECRUITING, NA, no results yet
- [ctgov:NCT04927975] Study to Evaluate Adverse Events and Change in Disease Activity With Oral Tablets of Upadacitinib in Adult Participants With Non-Segmental Vitiligo — COMPLETED, PHASE2, results

**Graph:**
- Upadacitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #5 TACROLIMUS ANHYDROUS

**Evidence strength:** moderate  
**Score:** 67 (prior 30 + graph 22 + trials 15 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT07532330] Tyrosine Vs Tacrolimus With NB-UVB in Vitiligo — ACTIVE_NOT_RECRUITING, NA, no results yet
- [ctgov:NCT07519031] Study of Umbilical Cord Mesenchymal Stem Cell-Derived Exosomes in Vitiligo — NOT_YET_RECRUITING, PHASE1, PHASE2, no results yet
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07307534] Nevus Removal vs. Conservative Treatment in Halo Nevus With Vitiligo: A Randomized Study — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06880042] COMPARISON OF EFFICACY AND SAFETY OF NARROWBAND UVB WITH 0.1% TACROLIMUS VS NARROWBAND UVB WITH 0.005% CALCIPOTRIOL IN TREATMENT OF VITILIGO — ENROLLING_BY_INVITATION, EARLY_PHASE1, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #6 AFAMELANOTIDE

**Evidence strength:** moderate  
**Score:** 65 (prior 30 + graph 22 + trials 13 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet
- [ctgov:NCT01382589] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo — COMPLETED, PHASE2, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #7 MONOBENZONE

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosinase inhibitor  
**Open Targets ID:** `CHEMBL1388`  

**Graph:**
- Monobenzone —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #8 TRIOXSALEN

**Evidence strength:** moderate  
**Score:** 62 (prior 40 + graph 22 + trials 0 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Open Targets ID:** `CHEMBL1475`  

**Graph:**
- TRIOXSALEN —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #9 METHOTREXATE

**Evidence strength:** moderate  
**Score:** 57 (prior 30 + graph 22 + trials 5 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Dihydrofolate reductase inhibitor  
**Open Targets ID:** `CHEMBL34259`  

**Trials:**
- [ctgov:NCT04237103] Combination of Methotrexate and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT07352293] The Value of Methotrexate in NCES for Stable Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT07208890] Methotrexate Iontophoresis Versus Methotrexate 1% Gel on Depigmentation in Vitiligo Patients — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06877455] Topical Methotrexate with Fractional CO2 Laser in Treatment of Non Segmental Vitiligo — NOT_YET_RECRUITING, NA, no results yet
- [euctr:2024-512766-34-00] CHUBX 2017/44 — ENDED, PHASE2, no results yet

**Graph:**
- METHOTREXATE —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #10 FLUOROURACIL

**Evidence strength:** moderate  
**Score:** 55 (prior 25 + graph 20 + trials 10 + literature 0)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Thymidylate synthase inhibitor  
**Open Targets ID:** `CHEMBL185`  

**Trials:**
- [ctgov:NCT07398807] Effectiveness of Micro-needling With 5 Fluorouracil Versus Potent Topical Steroids in the Treatment of Limited Vitiligo — RECRUITING, EARLY_PHASE1, no results yet
- [ctgov:NCT05536856] Topical 5-Fluorouracil Effervescent Powder in the Treatment of Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT06209138] 5-fluorouracil for Treatment of Stable Vitiligo — COMPLETED, NA, no results yet
- [ctgov:NCT05513924] Comparative Study Between Topical 5-fluorouracil and Latanoprost in Vitiligo. — COMPLETED, PHASE2, PHASE3, no results yet
- [ctgov:NCT05008887] Fractional CO2 Laser-assisted Cutaneous Delivery of Methotrexate Versus 5-fluorouracil in Stable Non-segmental Vitiligo — UNKNOWN, PHASE4, no results yet

**Graph:**
- FLUOROURACIL —[treats]→ Vitiligo (conf=0.82, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

## Accountability notes

- Deterministic ranking — not a clinical recommendation.
- Score rubric: prior clinical stage (0-40) + graph edges (0-40) + trials (0-35) + literature (0-20).
- Re-run after corpus updates: vitiligo report candidates

Reproduce: `vitiligo report candidates --json exports/candidate-report.json --markdown docs/candidate-report-v1.md`
