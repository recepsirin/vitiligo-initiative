# Research roadmap

The order of work from October 2026 to mid-2027, and the gates after. [`success.md`](success.md) defines the outcomes and the test for any piece of work. [`strategic-plan.md`](strategic-plan.md) holds the mission and phases. This page decides **what comes next and what it needs**.

## Two decisions this roadmap rests on

1. **The first objective is outcome 3, durability.** We chose it in [`success.md`](success.md): relapse after stopping is the largest unmet need, it has the least randomized evidence, and new randomized data are on the way. The other three outcomes get evidence maps and whatever durability work needs from them, not equal effort. A program covering all four outcomes from the start would spread one team over four problems.
2. **We assume public data and computation only.** Lab and clinical work happen through partners. We will not run an in-house wet lab (a [non-goal](strategic-plan.md#non-goals)). Each item below is tagged with what it needs:

| Tag | Needs |
|---|---|
| **Now** | Nothing beyond us and public data |
| **Reviewer** | A vitiligo clinician or researcher willing to read and answer |
| **Biostatistician** | A named statistician on the team, which data-sharing platforms require |
| **Lab** | A translational lab partner |
| **Clinic** | A clinical lead at a vitiligo centre |

## What we do not need to build

A generic plan for AI in vitiligo starts by building an evidence base, a knowledge graph and predictive models. Those exist: the [engine](engine.md), the [JAK atlas and scenario model](findings.md), the [sealed forecasts](../forecasts/README.md) and the [discovery loop](discovery-loop-plan.md). Two lessons from building them shape what comes next:

- **Bigger models must earn their place.** The mechanistic simulator beat the scenario model on its search data, then failed its locked exam ([`lab/simulator/`](../lab/simulator/README.md)). A model must beat the simpler one on data it has not seen before we use it.
- **Re-analysing public data is not a finding.** Under [`success.md`](success.md), a result counts only once a prediction is sealed and then tested on data that did not exist at sealing. For omics, the rule is: derive a signature from data already deposited, seal it, and test it on series deposited later.

## Checks on what exists

An outside review of the public repository (2026-10-23) asked whether these parts are sound enough to build on. We checked each concern against the code:

| Concern | What we found | Status |
|---|---|---|
| The candidate score double-counts sources | **True, in two ways.** Every graph edge is seeded from the same priors and trials the score already counts, so the graph component (up to 40 points) counted them again. A paper held in both PubMed and PMC also counted twice under literature. The global top 10 kept its order; totals fell by 20–26 points, and three of the five per-intent tables reordered below the leaders | Fixed: only edges extracted from papers count (none yet, so the graph scores 0 for every drug), and each paper counts once. [Report](candidate-report-v1.md) regenerated |
| The score reads as therapeutic potential | It measures **evidence maturity**: an approved drug ranks first because it is well studied. A promising, little-studied target scores low by construction | Stated in the report. Candidates aimed at the gaps ([`success.md`](success.md), contribution 2) will come from hypothesis records (3.6), not from this score |
| Model choice leaked into the held-out tests | **True for the back-tests:** v0.1 was changed to fix v0's back-test failures. The sealed forecasts are clean | Disclosed in the [model doc](jak-scenario-model.md) |
| No comparison with simpler models | **It was true.** Now done for the back-tests: the model clearly beats both baselines on the face, and is slightly worse than the crudest one on the body ([model doc](jak-scenario-model.md#compared-with-simple-baselines)) | Post hoc. The prospective half is 0.1 below |
| The graph cannot tell mechanism from association | **True, and starker than suggested:** it holds no mechanistic claims at all, only structured links from priors and trials | Built instead: [mechanism records](mechanisms/README.md), where every claim carries its evidence on a causal ladder and what the support reaches is computed, not curated |
| Clean reproduction from a recorded corpus | Each sealed forecast records a data fingerprint; the corpus itself has no published snapshot | 0.2 below |

**Built, but not first.** The review proposed a causal graph of genes, cells, pathways and outcomes. Building it before anything was testable would have been infrastructure ahead of an answer, so the hypotheses came first and the graph was built from them and from the measurements the corpus already held — never from an invented ontology.

**Built instead: a mechanism-to-intervention layer, one hypothesis at a time** ([`mechanisms/`](mechanisms/README.md)). Each record carries the chain from biological state to clinical outcome, its evidence on a causal ladder, the strongest competing explanation and how to tell it apart, and what we expect if the claim is right and if it is wrong. `vitiligo mechanism verify` rejects a claim that outranks its evidence, cites a paper the corpus does not hold, or cannot fail. Two records exist: the resident-memory claim behind 3.6, and the follicular-reservoir claim behind 2.1. Structure gets added when several hypotheses need connecting, not before.

| # | Deliverable | Needs | How we will know |
|---|---|---|---|
| 0.1 | Seal a baseline forecast beside every model forecast, and score both as results post. The back-test comparison is [done](jak-scenario-model.md#compared-with-simple-baselines) and post hoc; this is the clean test | Now | If v0.2 does not beat the baseline prospectively, the simpler model becomes the default. The body (T-VASI) is where it is most at risk |
| 0.2 | A published corpus snapshot (Zenodo), with the fingerprint the sealed forecasts cite, before either preprint | Now | A clean install reproduces a sealed forecast from the snapshot |
| 0.3 | Extract baseline severity per arm from the registry (six trials post baseline F-VASI, T-VASI or body-surface area) and pre-register whether adding it to the model improves held-out prediction | Now | Adopted only if it beats v0.2 on trials it has not seen, by the rule that governs every model change |

### The review's four priorities

It also proposed a four-step programme. Where each stands:

| | Proposal | Position |
|---|---|---|
| **P1** | A mechanism-centred knowledge graph of genes, proteins, pathways, cells, interventions and outcomes | **Done** ([graph](architecture.md), `vitiligo graph seed-evidence`). All eight node types are populated; every edge says whether it was **measured or asserted**, and a measured one carries the rung of the causal ladder it reached; all 1,882 edges carry source-level provenance. 126 edges rest on a measurement: 103 GWAS associations with a p-value and cohort, 21 trial responder rates, 2 from mechanism records. The other 1,600 are what Open Targets and the registries state, and now say so |
| **P2** | Molecular-data analysis across transcriptomic, single-cell, genetic and spatial datasets | **The live gap, now scoped.** The corpus holds GEO metadata, never the data. The first dataset we need is blocked on undocumented labels (3.6 above); the next step is resolving them, not building a general pipeline |
| **P3** | An intervention-prioritisation engine ranking hypotheses by causal support, benefit, uncertainty, feasibility and novelty | **Premature.** Causal support is already computed per record, and evidence maturity is already separate from it. Ranking two hypotheses is theatre. The same idea already runs where it has something to rank: the [value-of-information engine](../forecasts/voi/ranking/README.md) ranks pending trial results |
| **P4** | Close the experimental feedback loop with lab and clinical collaborators | **Blocked on people, not code** (gates A and D). The loop that can run without them already does: sealed forecasts scored as results post |

**The trials we cannot reach are now named.** CTRI, ChiCTR and IRCT publish no API, and WHO's ICTRP search refuses programmatic access, so trials from India, China and Iran never reach the corpus. `vitiligo report cited-trials` recovers them from the papers that report them: **34 leads**, 12 Indian, 9 Chinese, 8 Iranian, each with the paper describing it. They are leads, not records — no arms, outcomes or results — but the gap is now a list of 34 specific trials rather than an unknown. An ICTRP bulk export, which needs WHO's data-use agreement accepted by a person, would close it properly.

## The constraint: people, not code

Most items that would move an outcome now wait for a person:

| Waiting item | Waits for |
|---|---|
| [TRuE-V patient-level data request](durability/data-request-draft.md): who keeps their response | Biostatistician |
| [Stop vs step-down trial concept](durability/maintenance-trial-concept.md) | Clinic |
| [Expert questions on the JAK findings](findings.md#what-we-need-from-experts) | Reviewer |
| [Lab validation proposals](validation-proposals/) | Reviewer, then Lab |

**So outside review comes first.** The review pack exists (`./scripts/review/kol-share-pack.sh`); it has not been sent.

**Who to send it to is now answerable.** `vitiligo report funding` lists who holds NIH funding on vitiligo today. Since FY2024, 25 vitiligo-centred projects run across 10 investigators. Two work on exactly the questions the [mechanism records](mechanisms/README.md) ask: John E Harris (UMass/MGH, $5.2M active), whose lab produced the IL-15 evidence behind 3.6, and Jessica Shiu (UC Irvine), funded on how local factors govern repigmentation in stable vitiligo, which is 2.1. A grant is a plan, not evidence, so none of this counts toward any outcome — it answers who to approach, not what is true.

## Dates that set the pace

Estimated dates are the sponsors' registry estimates; results usually post months later.

| When | Event | What we do |
|---|---|---|
| Weekly | Forecast check and evidence watch ([workflow](../.github/workflows/forecast-check.yml)) | Triage leads ([`watch-triage.md`](../forecasts/watch-triage.md)); seal before results appear |
| H1 2027 | Incyte plans to file povorcitinib | Score the sealed STOP-V T-VASI50 forecasts when numbers are public |
| 2027-03 (primary completion) | Tranquillo LTE: stopping ritlecitinib | Score the [sealed durability forecast](durability-forecast-preregistration.md) |
| 2027-07 (primary completion) | Tranquillo 2 Part Ia: 50 vs 100 mg | Seal the tapering forecast for Part Ib before its results |
| 2027-12 (primary completion) | IBI3013 (anti-IL-15) phase 1, includes active vitiligo | Read the first data on targeting resident memory since AMG 714 |

## Outcome 3: Last (the focus)

**Question:** what happens when JAK treatment is reduced or stopped, and who keeps the response? ([evidence map](durability/README.md))

| # | Deliverable | Needs | How we will know |
|---|---|---|---|
| 3.1 | Score the stopping forecast when Tranquillo LTE posts | Now | Pre-registered: log score for the hazard ratio vs an uninformed forecast; Kaplan–Meier retention at week 52 if reported |
| 3.2 | Read the two 2026 TRuE-V papers (Kaplan–Meier proportions, treatment duration) through author copies or library access | Now | Evidence map updated. The sealed forecast stays as it is |
| 3.3 | Seal the tapering forecast after Part Ia results, before Part Ib | Now | Scored on Part Ib, as in 3.1 |
| 3.4 | Send the TRuE-V data request, with the "who keeps it" analysis plan sealed before the data arrive | Biostatistician | Predictors of relapse stated in advance, tested in the data |
| 3.5 | Turn the trial concept into a protocol synopsis, with an optional 1 mm biopsy at randomization (below) | Clinic | A funding application submitted |
| 3.6 | A sealed resident-memory relapse signature (below), for the hypothesis [`trm-il15-relapse`](mechanisms/README.md) | Now, then Clinic | Tested on skin sampled after treatment stops |

**3.6: measure the memory, not only the pigment.** The [success definition](success.md) names immune cells resident in the skin as what brings the disease back. No public data yet test this in people who stopped treatment: none of the vitiligo series in our GEO index samples skin after treatment is stopped.
- **Recorded as a hypothesis**: [`trm-il15-relapse`](mechanisms/README.md) (`vitiligo mechanism show trm-il15-relapse`). Its supporting evidence reaches a perturbation in animals; the human trial of IL-15 blockade only bounds it, because it tested induction rather than relapse. It is not sealed yet: a test whose score can still be tuned is not a test.
- **The data are not usable as deposited (checked 2026-10-23).** GSE203262's processed files merge each patient's lesional and non-lesional samples into one matrix, and nothing says which barcode suffix is which: not the series metadata, not the samples (they carry no files of their own), not the paper's methods ([PMC9310536](https://europepmc.org/article/PMC/PMC9310536)). Melanocyte markers should separate them, because lesional skin has lost its melanocytes, but the order is **inconsistent across patients**: four patients show more melanocyte signal in the first group, two in the second, and in two of them the difference is only about twofold. The labels have to be resolved first, by asking the authors or by reprocessing the raw data per sample. The file naming inside the deposit also varies between patients, so a reader has to tolerate three conventions.
- **Derive now.** Build a resident-memory score from matched lesional and non-lesional single-cell data (GSE203262) and mouse vitiligo resident-memory data (GSE169238). Seal the score and the direction of its predicted association with relapse.
- **Test later.** Two routes. One is a public series deposited after sealing that samples repigmented skin and follows patients. The other is the trial in 3.5: GSE311770 showed that 1 mm punch biopsies, which need no stitches, yield enough RNA for bulk RNA sequencing. A small biopsy at randomization would let the trial test whether the score predicts who relapses after stopping.
- **Stop rule.** If the score does not predict relapse in its first test, it is dropped and the failure recorded, as with the simulator.

## Outcome 2: Restore pigment

**Question:** what limits repigmentation on the body and hands, where today's best results are poorest? This is the only outcome without an evidence map.

| # | Deliverable | Needs | How we will know |
|---|---|---|---|
| 2.1 | Evidence map `docs/repigmentation/`, testing the hypothesis [`follicular-reservoir-limits-repigmentation`](mechanisms/README.md): how many trials measure hands; results on body and hands; what limits regrowth (the follicle reservoir: GSE150954; lesions that do not respond to NB-UVB: GSE256271); combinations, including the [ruxolitinib + NB-UVB proposal](validation-proposals/ruxolitinib-nb-uvb-combination.md) | Now | The map, built as for [spread](spread/README.md) and [safety and access](safety-access/README.md) |
| 2.2 | Score the sealed T-VASI50 forecasts as phase 3 body results post | Now | [Scoreboard](../forecasts/README.md) |
| 2.3 | Ask reviewers which repigmentation question is open, then pre-register an omics question on it | Reviewer | A question experts disagree on. "Hands respond poorly" is already known and would not count |

## Outcome 1: Stop spread

| # | Deliverable | Needs | How we will know |
|---|---|---|---|
| 1.1 | Find how Tranquillo defines "stabilization" (EADV 2026 late-breaker LB-161, the protocol); if the definition is public, seal a forecast for Tranquillo 2's stabilization endpoint | Now | Sealed before results; scored when posted |
| 1.2 | A draft shared definition of arrest in active disease (for example, no new or enlarging lesions over 12 months, with VSAS at entry), circulated for comment | Reviewer | Adopted or amended by clinicians |

## Outcome 4: Safe and reachable

Keep the [map](safety-access/README.md) current, at minimum effort. One item serves durability directly: **4.1**, the cost of a twice-weekly tacrolimus maintenance regimen against continuous ruxolitinib cream, for the trial synopsis in 3.5 (Now).

## Omics: where the public datasets fit

All are small; use them to generate hypotheses, never as evidence that a treatment works. "Samples" is the number GEO lists.

| Series | What it holds | Samples | Use here |
|---|---|---|---|
| GSE203262 | Single-cell RNA sequencing, matched lesional and non-lesional skin, stable disease | 12 | 3.6: derive the memory score — **labels unresolved**, see above |
| GSE169238 | Mouse melanoma-associated vitiligo: single-cell and TCR sequencing of CD8 T cells from draining lymph node and affected skin | 16 | 3.6: resident-memory reference |
| GSE311770 | Bulk RNA sequencing of 1 mm biopsies: lesional, perilesional, non-lesional, control (2026; PMID 42220516) | 105 | 3.5: shows 1 mm biopsies work; regional signatures |
| GSE150954 | Hair-follicle melanocyte precursors from untreated and NB-UVB-treated vitiligo skin | 24 | 2.1: what drives regrowth |
| GSE256271 | NB-UVB responding vs non-responding lesions, same patients | 8 | 2.1: why some lesions do not respond |
| GSE231794 | Single-cell RNA sequencing of blood immune cells in progressive non-segmental vitiligo | 8 | 1.2: a blood marker of activity, if the definition needs one |

**Two gaps to fix (Now).**
- ~~**The GEO index is stale.**~~ Refreshed 2026-10-23: GSE311770 and two other series are in, and the papers were refreshed with them (+321 PubMed, +177 PMC).
- **The weekly watch does not cover GEO.** It covers Europe PMC, ClinicalTrials.gov and SEC filings. Adding new vitiligo GEO series is the minimum infrastructure the "test later" rule in 3.6 needs.

## Gates

| Gate | Passed if | If passed | If not |
|---|---|---|---|
| **A. Outside review** | At least two reviewers answer by 2027-01-31 | Their answers set 2.3 and 1.2; ask one of them for a clinical-lead or biostatistician introduction | Present at a conference or go through a patient organization; keep work that needs no partner moving |
| **B. Stopping forecast scored** | The forecast beats the uninformed benchmark | Topical-to-oral transfer is usable for the tapering forecast (3.3) | Widen the transfer uncertainty in a pre-registered revision before sealing 3.3 |
| **C. Memory signature tested** | It predicts relapse in its first test | Write a lab proposal for the mechanism | Drop it and record the failure |
| **D. Clinical lead** | A named lead by mid-2027 | Protocol synopsis and funding application (3.5) | Publish the concept openly so others can run it |

## The next 90 days (to 2027-01-21)

In order:
1. **Send the review pack** to 2–3 clinicians or researchers and one patient organization (gate A). Reviewer.
2. **Add GEO to the watch** (the refresh itself is done); refresh the registries on a schedule. Now.
3. **Seal a baseline beside the next model forecast** (0.1), now that the back-test comparison is done. Now.
4. **Build and seal the resident-memory score** (3.6), with its pre-registration. Now.
5. **Build the repigmentation evidence map** (2.1). Now.
6. **Look for Tranquillo's stabilization definition**, and seal 1.1 if it is public. Now.
7. **Get the two 2026 TRuE-V papers** (3.2) and cost the maintenance regimen (4.1). Now.
8. **Publish a corpus snapshot** (0.2) and **finish the methods preprint's Methods** once reviewers have answered ([draft](methods-preprint-draft.md)). Now, then Reviewer.

**By 2027-01-21 we should know** whether reviewers will engage, whether the memory score is sealed and waiting for its test, and what limits repigmentation on the body and hands. We will have no answer yet to the durability question itself: that waits for Tranquillo LTE.
