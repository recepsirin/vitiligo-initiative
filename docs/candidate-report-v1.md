# Therapeutic Candidate Report v1

**Generated:** 2026-10-14T14:03:03.928696+00:00  
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

**Corpus snapshot:** 13,988 documents, 344 trials, 1044 graph entities.

## Global top candidates (aggregated across intents)

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 117 (prior 40 + graph 22 + trials 35 + literature 20)  
**Clinical stage (prior):** APPROVAL  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase TYK2 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL1789941`  

**Trials:**
- [ctgov:NCT04052425] Topical Ruxolitinib Evaluation in Vitiligo Study 1 (TRuE-V1) — COMPLETED, PHASE3, results
- [ctgov:NCT05247489] A Study to Evaluate the Safety and Efficacy of Ruxolitinib Cream With Phototherapy in Participants With Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT04057573] Topical Ruxolitinib Evaluation in Vitiligo Study 2 (TRuE-V2) — COMPLETED, PHASE3, results
- [ctgov:NCT03099304] A Study of INCB018424 Phosphate Cream in Subjects With Vitiligo — COMPLETED, PHASE2, results
- [ctgov:NCT04896385] A Study to Evaluate the Mechanism of Action of Ruxolitinib Cream in Subjects With Vitiligo (TRuE-V MOA) — COMPLETED, PHASE2, results

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
**Score:** 101 (prior 30 + graph 22 + trials 33 + literature 16)  
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

### #3 POVORCITINIB

**Evidence strength:** strong  
**Score:** 91 (prior 30 + graph 22 + trials 35 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-506011-18-00] INCB 54707-304 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531

### #4 RITLECITINIB

**Evidence strength:** strong  
**Score:** 90 (prior 30 + graph 22 + trials 30 + literature 8)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL4085457`  

**Trials:**
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [ctgov:NCT06163326] A 52-Week Study to Learn About the Safety and Effects of Ritlecitinib in Participants With Nonsegmental Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- Ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:39508655] Ritlecitinib rescues exacerbated vitiligo during the JAK1 inhibitor therapy: More than a coincidence? (2024) — Other, score=0.8403

### #5 AFAMELANOTIDE

**Evidence strength:** strong  
**Score:** 87 (prior 30 + graph 22 + trials 35 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2023-507470-40-00] CUV105 — AUTHORISED, PHASE2, PHASE3, no results yet
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #6 TACROLIMUS ANHYDROUS

**Evidence strength:** strong  
**Score:** 81 (prior 30 + graph 22 + trials 25 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT01082393] Vitiligo and the Koebner Phenomenon (Model of Vitiligo Induction and Therapy: a Clinical and Immunological Analysis) — COMPLETED, PHASE4, no results yet
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT06719024] Topical Ruxolitinib for Face and Neck Vitiligo of Adult Chinese Patients Refractory to Topical Tacrolimus — RECRUITING, PHASE2, PHASE3, no results yet
- [ictrp:ISRCTN99887766] NB-UVB plus topical tacrolimus for vitiligo — NOT_YET_RECRUITING, PHASE2, no results yet
- [ctgov:NCT00807690] Vitiligo Treated With TL01 Combined With Tacrolimus Ointment Versus Placebo — COMPLETED, PHASE3, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:12399684] Repigmentation of vitiligo with topical tacrolimus. (2002) — Case report, score=0.8248

### #7 METHOTREXATE

**Evidence strength:** strong  
**Score:** 77 (prior 30 + graph 22 + trials 25 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Dihydrofolate reductase inhibitor  
**Open Targets ID:** `CHEMBL34259`  

**Trials:**
- [ctgov:NCT07352293] The Value of Methotrexate in NCES for Stable Vitiligo — RECRUITING, PHASE4, no results yet
- [ctgov:NCT04237103] Combination of Methotrexate and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT07336641] LANDSCAPE: Demographics and Treatment Patterns of Patients With Immune-Mediated Inflammatory Skin Diseases in Italian Clinical Practice — NOT_YET_RECRUITING, —, no results yet
- [ctgov:NCT07208890] Methotrexate Iontophoresis Versus Methotrexate 1% Gel on Depigmentation in Vitiligo Patients — NOT_YET_RECRUITING, NA, no results yet
- [ctgov:NCT06877455] Topical Methotrexate with Fractional CO2 Laser in Treatment of Non Segmental Vitiligo — NOT_YET_RECRUITING, NA, no results yet

**Graph:**
- METHOTREXATE —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #8 FLUOROURACIL

**Evidence strength:** strong  
**Score:** 77 (prior 25 + graph 20 + trials 24 + literature 8)  
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

### #9 BARICITINIB

**Evidence strength:** strong  
**Score:** 74 (prior 20 + graph 20 + trials 18 + literature 16)  
**Clinical stage (prior):** PHASE_2  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor  
**Open Targets ID:** `CHEMBL2105759`  

**Trials:**
- [ctgov:NCT06768840] Vitiligo, New Treatment and Serum s100B — RECRUITING, PHASE2, PHASE3, no results yet
- [ctgov:NCT04822584] Evaluation of Effect and Tolerance of the Association of Baricitinib and Phototherapy Versus Phototherapy in Adults With Progressive Vitiligo — COMPLETED, PHASE2, no results yet
- [ctgov:NCT07554222] Study to Evaluate the Safety, Tolerability and How IBI3013 is Taken up and Processed by the Body in Healthy Volunteers After Single-dose Administration, and in Non-segmental Vitiligo Patients and Alopecia Areata Patients After Multiple-dose Administration — RECRUITING, PHASE1, no results yet
- [ctgov:NCT05950542] Evaluation Safety ,Efficacy Baricitinib Plus Excimer Light Versus Excimer Light Alone in Non Segmental Vitiligo — UNKNOWN, —, no results yet

**Graph:**
- Baricitinib —[treats]→ Vitiligo (conf=0.82, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:40682379] 308 nm Excimer Laser Combined With JAK Inhibitors for Adult Localized Non-Segmental Vitiligo: A Multicenter Randomized Controlled Trial. (2025) — RCT, score=0.8513
- [pubmed:39723343] Combination Therapy with Baricitinib and Narrowband Ultraviolet B for Active Non-Segmental Vitiligo: A Retrospective Controlled Study. (2024) — Other, score=0.8453
- [pmc:PMC11668684] Combination Therapy with Baricitinib and Narrowband Ultraviolet B for Active Non-Segmental Vitiligo: A Retrospective Controlled Study (2024) — Other, score=0.8398

### #10 LATANOPROST

**Evidence strength:** moderate  
**Score:** 63 (prior 25 + graph 20 + trials 18 + literature 0)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Prostanoid FP receptor agonist  
**Open Targets ID:** `CHEMBL1051`  

**Trials:**
- [ctgov:NCT07016113] 0.005% Latanoprost Gel for Nonsegmental Vitiligo — NOT_YET_RECRUITING, PHASE2, no results yet
- [ctgov:NCT04811326] Latanoprost Plus NB-UVB Versus Each Alone in Non-segmental Vitiligo: Clinical and Laboratory Evaluation — UNKNOWN, PHASE4, no results yet
- [ctgov:NCT05513924] Comparative Study Between Topical 5-fluorouracil and Latanoprost in Vitiligo. — COMPLETED, PHASE2, PHASE3, no results yet
- [ctgov:NCT03611348] Microneedling and Latanoprost in Acrofacial Vitiligo — UNKNOWN, PHASE2, PHASE3, no results yet

**Graph:**
- Latanoprost —[treats]→ Vitiligo (conf=0.82, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

## Intent: Stop spread — active non-segmental vitiligo

**Query:** `stop spread active non-segmental vitiligo JAK inhibitor`  
**Goal:** spread_arrest

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 113 | 40 | 22 | 35 | 16 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 2 | UPADACITINIB | 101 | 30 | 22 | 33 | 16 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 3 | POVORCITINIB | 91 | 30 | 22 | 35 | 4 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 4 | RITLECITINIB | 90 | 30 | 22 | 30 | 8 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 5 | AFAMELANOTIDE | 87 | 30 | 22 | 35 | 0 | — |
| 6 | METHOTREXATE | 77 | 30 | 22 | 25 | 0 | — |
| 7 | TACROLIMUS ANHYDROUS | 77 | 30 | 22 | 25 | 0 | — |
| 8 | BARICITINIB | 74 | 20 | 20 | 18 | 16 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 9 | FLUOROURACIL | 69 | 25 | 20 | 24 | 0 | — |
| 10 | LATANOPROST | 63 | 25 | 20 | 18 | 0 | — |

## Intent: Drive repigmentation — non-segmental vitiligo

**Query:** `repigmentation non-segmental vitiligo ruxolitinib phototherapy`  
**Goal:** repigmentation

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 117 | 40 | 22 | 35 | 20 | [pmc:PMC12804599] Laser-assisted drug delivery of topical ruxolitinib for treatment-refractory stable non... (2026) |
| 2 | RITLECITINIB | 90 | 30 | 22 | 30 | 8 | [pmc:PMC12281511] Successful repigmentation with ritlecitinib and combined home-based phototherapy in an... (2025) |
| 3 | AFAMELANOTIDE | 87 | 30 | 22 | 35 | 0 | — |
| 4 | POVORCITINIB | 87 | 30 | 22 | 35 | 0 | — |
| 5 | UPADACITINIB | 85 | 30 | 22 | 33 | 0 | — |
| 6 | METHOTREXATE | 77 | 30 | 22 | 25 | 0 | — |
| 7 | TACROLIMUS ANHYDROUS | 77 | 30 | 22 | 25 | 0 | — |
| 8 | FLUOROURACIL | 77 | 25 | 20 | 24 | 8 | [pmc:PMC11928802] Repigmentation of vitiligo with 5-fluorouracil tattooing in combination with topical ru... (2025) |
| 9 | LATANOPROST | 63 | 25 | 20 | 18 | 0 | — |
| 10 | MONOBENZONE | 62 | 40 | 22 | 0 | 0 | — |

## Intent: JAK inhibitor + NB-UVB combination

**Query:** `topical ruxolitinib narrowband UVB combination vitiligo`  
**Goal:** combination

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 117 | 40 | 22 | 35 | 20 | [pubmed:35787401] Addition of Narrow-Band UVB Phototherapy to Ruxolitinib Cream in Patients With Vitiligo. (2022) |
| 2 | AFAMELANOTIDE | 87 | 30 | 22 | 35 | 0 | — |
| 3 | POVORCITINIB | 87 | 30 | 22 | 35 | 0 | — |
| 4 | UPADACITINIB | 85 | 30 | 22 | 33 | 0 | — |
| 5 | RITLECITINIB | 82 | 30 | 22 | 30 | 0 | — |
| 6 | METHOTREXATE | 77 | 30 | 22 | 25 | 0 | — |
| 7 | TACROLIMUS ANHYDROUS | 77 | 30 | 22 | 25 | 0 | — |
| 8 | FLUOROURACIL | 69 | 25 | 20 | 24 | 0 | — |
| 9 | BARICITINIB | 66 | 20 | 20 | 18 | 8 | [pubmed:41211759] Topical ruxolitinib ± oral baricitinib in the treatment of active non-segmental vitilig... (2025) |
| 10 | LATANOPROST | 63 | 25 | 20 | 18 | 0 | — |

## Intent: Acral / recalcitrant site repigmentation

**Query:** `acral vitiligo hands feet repigmentation treatment`  
**Goal:** repigmentation

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 97 | 40 | 22 | 35 | 0 | — |
| 2 | AFAMELANOTIDE | 87 | 30 | 22 | 35 | 0 | — |
| 3 | POVORCITINIB | 87 | 30 | 22 | 35 | 0 | — |
| 4 | UPADACITINIB | 85 | 30 | 22 | 33 | 0 | — |
| 5 | RITLECITINIB | 82 | 30 | 22 | 30 | 0 | — |
| 6 | TACROLIMUS ANHYDROUS | 81 | 30 | 22 | 25 | 4 | [pubmed:12399684] Repigmentation of vitiligo with topical tacrolimus. (2002) |
| 7 | METHOTREXATE | 77 | 30 | 22 | 25 | 0 | — |
| 8 | FLUOROURACIL | 69 | 25 | 20 | 24 | 0 | — |
| 9 | LATANOPROST | 63 | 25 | 20 | 18 | 0 | — |
| 10 | MONOBENZONE | 62 | 40 | 22 | 0 | 0 | — |

## Intent: Facial vitiligo repigmentation

**Query:** `facial vitiligo repigmentation treatment face`  
**Goal:** repigmentation

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 105 | 40 | 22 | 35 | 8 | [pmc:PMC11851260] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream... (2024) |
| 2 | AFAMELANOTIDE | 87 | 30 | 22 | 35 | 0 | — |
| 3 | POVORCITINIB | 87 | 30 | 22 | 35 | 0 | — |
| 4 | UPADACITINIB | 85 | 30 | 22 | 33 | 0 | — |
| 5 | RITLECITINIB | 82 | 30 | 22 | 30 | 0 | — |
| 6 | METHOTREXATE | 77 | 30 | 22 | 25 | 0 | — |
| 7 | TACROLIMUS ANHYDROUS | 77 | 30 | 22 | 25 | 0 | — |
| 8 | FLUOROURACIL | 69 | 25 | 20 | 24 | 0 | — |
| 9 | LATANOPROST | 63 | 25 | 20 | 18 | 0 | — |
| 10 | MONOBENZONE | 62 | 40 | 22 | 0 | 0 | — |

## Accountability notes

- Deterministic ranking — not a clinical recommendation.
- Score rubric: prior clinical stage (0-40) + graph edges (0-40) + trials (0-35) + literature (0-20).
- Trials score the best evidence (top phase 15, posted Phase 2+ results 10, active trial 5, breadth up to 5), not trial count.
- Re-run after corpus updates: vitiligo report candidates

Reproduce: `vitiligo report candidates --json exports/candidate-report.json --markdown docs/candidate-report-v1.md`
