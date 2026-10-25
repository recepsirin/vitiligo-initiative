# Therapeutic Candidate Report v1

**Generated:** 2026-10-25T19:06:03.888528+00:00  
**Engine:** v1.0.0  
**Status:** Research hypothesis ranking — not medical advice, not an endorsement.

## Methodology

Candidates are aggregated from Open Targets drug priors (Phase 2+), knowledge-graph edges linking drugs to vitiligo, registered trials whose interventions match the drug stem, and semantic literature retrieval for each intent query. Scores are transparent and reproducible from the local corpus snapshot. The score ranks evidence maturity, not therapeutic potential.

### Score rubric

| Component | Max points | Source |
|-----------|------------|--------|
| Prior clinical stage | 40 | Open Targets (`EFO_0004208`) |
| Knowledge graph | 40 | Edges extracted from papers (seeded edges restate priors and trials) |
| Registered trials | 35 | CT.gov, EU CTR, ICTRP |
| Literature retrieval | 20 | Semantic search (top-K per intent) |

**Corpus snapshot:** 14,497 documents, 1064 trials, 1203 graph entities.

## Global top candidates (aggregated across intents)

### #1 RUXOLITINIB

**Evidence strength:** strong  
**Score:** 95 (prior 40 + graph 0 + trials 35 + literature 20)  
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
- [pubmed:42473916] Noninvasive imaging for the evaluation of JAK inhibitors efficacy in the management of facial vitiligo. (2026) — Cohort / observational, score=0.8635
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:42664062] Efficacy and safety of JAK inhibitors for vitiligo: an updated systematic review and meta-analysis of randomized controlled trials. (2026) — Meta-analysis, score=0.8513
- [pmc:PMC13385178] Advances in Janus kinase inhibitors for vitiligo (2026) — Review, score=0.8444
- [pubmed:40332460] Efficacy and Safety of JAK Inhibitors in the Management of Vitiligo: A Systematic Review and Meta-analysis. (2025) — Review, score=0.8431

### #2 UPADACITINIB

**Evidence strength:** strong  
**Score:** 81 (prior 30 + graph 0 + trials 35 + literature 16)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK1 inhibitor; Tyrosine-protein kinase JAK2 inhibitor; Tyrosine-protein kinase TYK2 inhibitor  
**Open Targets ID:** `CHEMBL3622821`  

**Trials:**
- [ictrp:ChiCTR2400080649] Clinical observations on the treatment of moderate-to-severe atopic dermatitis and its comorbidities with Upadacitinib — NOT_RECRUITING, RETROSPECTIVE_STUDY, no results yet
- [ictrp:ChiCTR2400085121] Efficacy of upadacitinib after autologous non-cultured epidermal cell suspension transplantation in vitiligo participants——a pilot, random, observer blinded, comparative study — NOT_RECRUITING, —, no results yet
- [euctr:2023-506195-27-00] M19-044 — AUTHORISED, PHASE3, no results yet
- [ctgov:NCT04159597] Expanded Access to Upadacitinib — AVAILABLE, —, no results yet
- [ctgov:NCT06118411] A Study To Assess Adverse Events and Effectiveness of Upadacitinib Oral Tablets in Adult and Adolescent Participants With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet

**Graph:**
- upadacitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531
- [pubmed:39704810] Repigmentation in non-segmental vitiligo using the Janus kinase inhibitor upadacitinib, a retrospective case series. (2024) — Case series, score=0.8502
- [pubmed:38873632] Once-daily upadacitinib versus placebo in adults with extensive non-segmental vitiligo: a phase 2, multicentre, randomised, double-blind, placebo-controlled, dose-ranging study. (2024) — Other, score=0.8489
- [pmc:PMC13385178] Advances in Janus kinase inhibitors for vitiligo (2026) — Review, score=0.8444

### #3 POVORCITINIB

**Evidence strength:** moderate  
**Score:** 69 (prior 30 + graph 0 + trials 35 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Open Targets ID:** `CHEMBL5095079`  

**Trials:**
- [ctgov:NCT06113445] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V1) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT06113471] A Study to Evaluate Efficacy and Safety of Povorcitinib in Participants With Nonsegmental Vitiligo (STOP-V2) — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT07865312] A Phase 3 Study of Povorcitinib Phosphate in Chinese Adults With Nonsegmental Vitiligo — NOT_YET_RECRUITING, PHASE3, no results yet
- [euctr:2024-520107-12-00] INCB054707-801 — AUTHORISED, PHASE3, no results yet
- [euctr:2023-505782-86-00] INCB 54707-303 — AUTHORISED, PHASE3, no results yet

**Graph:**
- povorcitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531

### #4 RITLECITINIB

**Evidence strength:** moderate  
**Score:** 69 (prior 30 + graph 0 + trials 35 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Tyrosine-protein kinase JAK3 inhibitor; TEC family kinase inhibitor  
**Open Targets ID:** `CHEMBL4085457`  

**Trials:**
- [ctgov:NCT07152626] Combination Approach With Ritlecitinib and nbUVB Compared to Ritlecitinib Alone for Treating Vitiligo — RECRUITING, PHASE2, no results yet
- [ictrp:CTIS2023-505603-23-00] A Study to Learn How Different Manufactured Products of the Study Medicine Called Ritlecitinib are Taken up Into the Blood in Healthy Adults When Taken on an Empty Stomach or When Taken With a Meal in Healthy Adults. — NOT_RECRUITING, PHASE4, results
- [ctgov:NCT06072183] A 104-Week Study of Ritlecitinib Oral Capsules in Adults With Nonsegmental Vitiligo (Active and Stable) Tranquillo 2 — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [euctr:2025-521504-22-00] 25-PP-03 — AUTHORISED, PHASE2, no results yet
- [euctr:2022-502518-98-00] B7981080 — AUTHORISED, PHASE3, no results yet

**Graph:**
- ritlecitinib —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic Potential. (2025) — Review, score=0.8531

### #5 AFAMELANOTIDE

**Evidence strength:** moderate  
**Score:** 65 (prior 30 + graph 0 + trials 35 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Melanocortin receptor 1 agonist  
**Open Targets ID:** `CHEMBL441738`  

**Trials:**
- [ctgov:NCT05210582] A Study to Assess the Changes in Pigmentation and Safety of Afamelanotide in Patients With Vitiligo on the Face — UNKNOWN, PHASE2, no results yet
- [euctr:2023-507470-40-00] CUV105 — AUTHORISED, PHASE2, PHASE3, no results yet
- [ctgov:NCT06109649] A Study to Compare the Efficacy and Safety of SCENESSE and Narrow-Band Ultraviolet (NB-UVB) Light Versus NB-UVB Light Alone in Patients With Vitiligo — ACTIVE_NOT_RECRUITING, PHASE3, no results yet
- [ctgov:NCT04525157] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Phototherapy in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE2, results
- [ctgov:NCT01430195] Afamelanotide and Narrow-Band Ultraviolet B (NB-UVB) Light in the Treatment of Nonsegmental Vitiligo (NSV) — COMPLETED, PHASE1, no results yet

**Graph:**
- Afamelanotide —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #6 TRIOXSALEN

**Evidence strength:** moderate  
**Score:** 61 (prior 40 + graph 0 + trials 21 + literature 0)  
**Clinical stage (prior):** APPROVAL  
**Open Targets ID:** `CHEMBL1475`  

**Trials:**
- [ictrp:CTRI/2023/12/060436] A comparative study on efficacy, safety and tolerability of topical tofacitinib vs topical tofacitinib combined with puvasol in the management of vitiligo — RECRUITING, PHASE3, no results yet
- [ictrp:CTRI/2018/04/013434] A study to see the result of blood products in repigmentation in stable vitiligo. — RECRUITING, —, no results yet

**Graph:**
- TRIOXSALEN —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #7 TACROLIMUS ANHYDROUS

**Evidence strength:** moderate  
**Score:** 59 (prior 30 + graph 0 + trials 25 + literature 4)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** FK506-binding protein 1A inhibitor  
**Open Targets ID:** `CHEMBL269732`  

**Trials:**
- [ctgov:NCT07368673] Comparative Effectiveness of Ruxolitinib Monotherapy Versus Its Combination With Tacrolimus and Corticosteroids in the Management of Vitiligo: A Randomized Controlled Trial — COMPLETED, PHASE4, no results yet
- [ctgov:NCT06719024] Topical Ruxolitinib for Face and Neck Vitiligo of Adult Chinese Patients Refractory to Topical Tacrolimus — RECRUITING, PHASE2, PHASE3, no results yet
- [ctgov:NCT00807690] Vitiligo Treated With TL01 Combined With Tacrolimus Ointment Versus Placebo — COMPLETED, PHASE3, no results yet
- [ictrp:IRCT201606239014N103] Effect of narrow band UVB in combination with 0.1% topical Tacrolimus versus narrow band UVB alone on treatment of patients with vitiligo — NOT_RECRUITING, PHASE2, no results yet
- [ctgov:NCT07519031] Study of Umbilical Cord Mesenchymal Stem Cell-Derived Exosomes in Vitiligo — NOT_YET_RECRUITING, PHASE1, PHASE2, no results yet

**Graph:**
- TACROLIMUS ANHYDROUS —[treats]→ Vitiligo (conf=0.88, structured)

**Literature (intent retrieval):**
- [pubmed:42664062] Efficacy and safety of JAK inhibitors for vitiligo: an updated systematic review and meta-analysis of randomized controlled trials. (2026) — Meta-analysis, score=0.8513

### #8 METHOTREXATE

**Evidence strength:** moderate  
**Score:** 55 (prior 30 + graph 0 + trials 25 + literature 0)  
**Clinical stage (prior):** PHASE_3  
**Mechanisms:** Dihydrofolate reductase inhibitor  
**Open Targets ID:** `CHEMBL34259`  

**Trials:**
- [ctgov:NCT07352293] The Value of Methotrexate in NCES for Stable Vitiligo — COMPLETED, PHASE4, no results yet
- [ictrp:CTRI/2023/07/055546] Comparison of efficacy of 5-FU cream and methotrexate gel in acral vitiligo lesions — NOT_RECRUITING, PHASE4, no results yet
- [ictrp:IRCT20221013056158N1] Study of combined methotrexate and phototherapy in vitiligo. — NOT_RECRUITING, PHASE3, no results yet
- [ictrp:IRCT20230816059168N2] Fractional Carbon dioxide LASER with Topical Methotrexate Vs Topical PUVASOL in Treatment of Vitiligo — RECRUITING, PHASE2, no results yet
- [ictrp:CTRI/2017/08/009473] To Compare The Effect Of Methotrexate Versus Oral Mini Pulse(Betamethasone) With Narrow Band Ultra Violet-B In The Patients Of Vitiligo Vulagris. — RECRUITING, —, no results yet

**Graph:**
- METHOTREXATE —[treats]→ Vitiligo (conf=0.88, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

### #9 FLUOROURACIL

**Evidence strength:** moderate  
**Score:** 54 (prior 25 + graph 0 + trials 25 + literature 4)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Thymidylate synthase inhibitor  
**Open Targets ID:** `CHEMBL185`  

**Trials:**
- [ictrp:CTRI/2018/11/016487] A preliminary trial to Study the Effect of Adding Platelet Rich Plasma to Microneedling plus 5-Fluorouracil Therapy in Vitiligo confined to forearms, hands,legs and feet — NOT_RECRUITING, PHASE2, no results yet
- [ictrp:CTRI/2023/07/055546] Comparison of efficacy of 5-FU cream and methotrexate gel in acral vitiligo lesions — NOT_RECRUITING, PHASE4, no results yet
- [ictrp:IRCT20220806055626N1] Comparison the Effect of Three Different Type of Treatment in Patients Being Treated for Vitiligo Lesions: 1. Microneedling, 2. Microneedling with Topical Fluocinolone and 3. Microneedling with 5-FU — RECRUITING, —, no results yet
- [ictrp:IRCT20221105056407N2] Microneedling with Fluorouracil in Patients with Stable Vitiligo — RECRUITING, PHASE3, no results yet
- [ictrp:IRCT20180602039939N1] Effect of topical fluorouracil on vitiligo — RECRUITING, PHASE2, no results yet

**Graph:**
- FLUOROURACIL —[treats]→ Vitiligo (conf=0.82, structured)

**Literature (intent retrieval):**
- [pmc:PMC11928802] Repigmentation of vitiligo with 5-fluorouracil tattooing in combination with topical ruxolitinib: A case report (2025) — Other, score=0.8785

### #10 LATANOPROST

**Evidence strength:** moderate  
**Score:** 50 (prior 25 + graph 0 + trials 25 + literature 0)  
**Clinical stage (prior):** PHASE_2_3  
**Mechanisms:** Prostanoid FP receptor agonist  
**Open Targets ID:** `CHEMBL1051`  

**Trials:**
- [ctgov:NCT07016113] 0.005% Latanoprost Gel for Nonsegmental Vitiligo — NOT_YET_RECRUITING, PHASE2, no results yet
- [ictrp:CTRI/2024/04/065773] it is a study involving vitiligo patients, which will be treated by two separate topical medication followed by procedure with microneedling and NBUVB therapy which will result in darkening of vitiligo patches — RECRUITING, PHASE2, PHASE3, no results yet
- [ictrp:IRCT20120909010795N4] Fractional CO2 laser and topical latanoprost in acral vitiligo — NOT_RECRUITING, —, no results yet
- [ictrp:IRCT20120215009014N283] Comparison of effect of NB-UVB with and without topical Latanoprost solution or placebo in Vitiligo Patients — RECRUITING, PHASE2, no results yet
- [ictrp:CTRI/2024/06/068808] A study on efficacy of fractional CO2 LASER with topical Latanoprost vs fractional CO2 LASER with topical Tofacitinib in stable vitiligo - An interventional study — NOT_RECRUITING, —, no results yet

**Graph:**
- Latanoprost —[treats]→ Vitiligo (conf=0.82, structured)

**Caveats:** No intent-matched papers in top semantic retrieval.

## Intent: Stop spread — active non-segmental vitiligo

**Query:** `stop spread active non-segmental vitiligo JAK inhibitor`  
**Goal:** spread_arrest

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 95 | 40 | 0 | 35 | 20 | [pubmed:42473916] Noninvasive imaging for the evaluation of JAK inhibitors efficacy in the management of... (2026) |
| 2 | UPADACITINIB | 81 | 30 | 0 | 35 | 16 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 3 | POVORCITINIB | 69 | 30 | 0 | 35 | 4 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 4 | RITLECITINIB | 69 | 30 | 0 | 35 | 4 | [pubmed:40996476] JAK Inhibitors for the Treatment of Vitiligo: Current Evidence and Emerging Therapeutic... (2025) |
| 5 | AFAMELANOTIDE | 65 | 30 | 0 | 35 | 0 | — |
| 6 | TRIOXSALEN | 61 | 40 | 0 | 21 | 0 | — |
| 7 | TACROLIMUS ANHYDROUS | 59 | 30 | 0 | 25 | 4 | [pubmed:42664062] Efficacy and safety of JAK inhibitors for vitiligo: an updated systematic review and me... (2026) |
| 8 | METHOTREXATE | 55 | 30 | 0 | 25 | 0 | — |
| 9 | FLUOROURACIL | 50 | 25 | 0 | 25 | 0 | — |
| 10 | LATANOPROST | 50 | 25 | 0 | 25 | 0 | — |

## Intent: Drive repigmentation — non-segmental vitiligo

**Query:** `repigmentation non-segmental vitiligo ruxolitinib phototherapy`  
**Goal:** repigmentation

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 95 | 40 | 0 | 35 | 20 | [pmc:PMC12804599] Laser-assisted drug delivery of topical ruxolitinib for treatment-refractory stable non... (2026) |
| 2 | RITLECITINIB | 69 | 30 | 0 | 35 | 4 | [pmc:PMC12281511] Successful repigmentation with ritlecitinib and combined home-based phototherapy in an... (2025) |
| 3 | AFAMELANOTIDE | 65 | 30 | 0 | 35 | 0 | — |
| 4 | POVORCITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 5 | UPADACITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 6 | TRIOXSALEN | 61 | 40 | 0 | 21 | 0 | — |
| 7 | METHOTREXATE | 55 | 30 | 0 | 25 | 0 | — |
| 8 | TACROLIMUS ANHYDROUS | 55 | 30 | 0 | 25 | 0 | — |
| 9 | FLUOROURACIL | 54 | 25 | 0 | 25 | 4 | [pmc:PMC11928802] Repigmentation of vitiligo with 5-fluorouracil tattooing in combination with topical ru... (2025) |
| 10 | LATANOPROST | 50 | 25 | 0 | 25 | 0 | — |

## Intent: JAK inhibitor + NB-UVB combination

**Query:** `topical ruxolitinib narrowband UVB combination vitiligo`  
**Goal:** combination

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 95 | 40 | 0 | 35 | 20 | [pubmed:35787401] Addition of Narrow-Band UVB Phototherapy to Ruxolitinib Cream in Patients With Vitiligo. (2022) |
| 2 | AFAMELANOTIDE | 65 | 30 | 0 | 35 | 0 | — |
| 3 | POVORCITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 4 | RITLECITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 5 | UPADACITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 6 | TRIOXSALEN | 61 | 40 | 0 | 21 | 0 | — |
| 7 | METHOTREXATE | 55 | 30 | 0 | 25 | 0 | — |
| 8 | TACROLIMUS ANHYDROUS | 55 | 30 | 0 | 25 | 0 | — |
| 9 | FLUOROURACIL | 50 | 25 | 0 | 25 | 0 | — |
| 10 | LATANOPROST | 50 | 25 | 0 | 25 | 0 | — |

## Intent: Acral / recalcitrant site repigmentation

**Query:** `acral vitiligo hands feet repigmentation treatment`  
**Goal:** repigmentation

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 75 | 40 | 0 | 35 | 0 | — |
| 2 | AFAMELANOTIDE | 65 | 30 | 0 | 35 | 0 | — |
| 3 | POVORCITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 4 | RITLECITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 5 | UPADACITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 6 | TRIOXSALEN | 61 | 40 | 0 | 21 | 0 | — |
| 7 | TACROLIMUS ANHYDROUS | 59 | 30 | 0 | 25 | 4 | [pubmed:12399684] Repigmentation of vitiligo with topical tacrolimus. (2002) |
| 8 | METHOTREXATE | 55 | 30 | 0 | 25 | 0 | — |
| 9 | FLUOROURACIL | 50 | 25 | 0 | 25 | 0 | — |
| 10 | LATANOPROST | 50 | 25 | 0 | 25 | 0 | — |

## Intent: Facial vitiligo repigmentation

**Query:** `facial vitiligo repigmentation treatment face`  
**Goal:** repigmentation

| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | RUXOLITINIB | 79 | 40 | 0 | 35 | 4 | [pmc:PMC11851260] Repigmentation by body region in patients with vitiligo treated with ruxolitinib cream... (2024) |
| 2 | AFAMELANOTIDE | 65 | 30 | 0 | 35 | 0 | — |
| 3 | POVORCITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 4 | RITLECITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 5 | UPADACITINIB | 65 | 30 | 0 | 35 | 0 | — |
| 6 | TRIOXSALEN | 61 | 40 | 0 | 21 | 0 | — |
| 7 | METHOTREXATE | 55 | 30 | 0 | 25 | 0 | — |
| 8 | TACROLIMUS ANHYDROUS | 55 | 30 | 0 | 25 | 0 | — |
| 9 | FLUOROURACIL | 50 | 25 | 0 | 25 | 0 | — |
| 10 | LATANOPROST | 50 | 25 | 0 | 25 | 0 | — |

## Accountability notes

- Deterministic ranking — not a clinical recommendation.
- Score rubric: prior clinical stage (0-40) + graph edges (0-40) + trials (0-35) + literature (0-20).
- The score measures evidence maturity: how far and how much a drug has been studied in vitiligo. It is not a ranking of therapeutic potential; a promising but little-studied target scores low.
- Each source counts once: graph edges seeded from priors and trials are not scored again (only edges extracted from papers count), and a paper held in both PubMed and PMC counts once.
- Prior stage and top trial phase both reflect clinical development, so they overlap.
- Trials score the best evidence (top phase 15, posted Phase 2+ results 10, active trial 5, breadth up to 5), not trial count.
- Re-run after corpus updates: vitiligo report candidates

Reproduce: `vitiligo report candidates --json exports/candidate-report.json --markdown docs/candidate-report-v1.md`
