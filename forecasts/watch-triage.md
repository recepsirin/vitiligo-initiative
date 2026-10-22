# Watch triage

What we decided about each lead from `vitiligo discover watch`, so that a lead that was read and set aside is on record. Newest first.

**What counts as model data:** arm-level F-VASI or T-VASI responder rates from a randomized trial of a JAK-family drug with a placebo arm. Paper rows must come from open-access tables whose cells can be verified ([`curation/`](../curation/README.md)).

**What can be sealed:** a randomized active arm with a placebo arm, a registered dose, and a VASI responder endpoint.

## Standing items

- **Povorcitinib phase 3 details (STOP-V1, STOP-V2).** Incyte plans more phase 3 data in the second half of 2026. When the arm sizes, analysis population and T-VASI50 numbers are public: score the sealed T-VASI50 forecasts ([`povorcitinib-phase3/`](povorcitinib-phase3/README.md)), then pre-register a model version that fits these toplines. Nothing that version would be tested on resolves before then, so the pre-registration waits for the data rather than guessing them.
- **Zasocitinib doses (NCT07108283).** Seal when the doses are public.

## 2026-10-22 (leads since 2026-09-01)

### Trials (ClinicalTrials.gov)

| Lead | Decision | Reason |
|---|---|---|
| [NCT07865312](https://clinicaltrials.gov/study/NCT07865312), povorcitinib 30 mg QD vs placebo, phase 3, China, 174 planned | **Sealed** F-VASI75 and T-VASI50 at week 52 under v0.2, v0.4, v0.5 ([`2026-10-22-new-trials/`](2026-10-22-new-trials/)) | Not yet recruiting, so no results can exist. The registry gives the dose only on the intervention; the parser now reads it there when that intervention belongs to this arm alone |
| [NCT07108283](https://clinicaltrials.gov/study/NCT07108283), zasocitinib (TYK2), phase 2, 3 doses vs placebo | Not sealed; revisit when doses are public | Doses are "low/medium/high" in both ClinicalTrials.gov and EU CTIS 2025-522309-40-00. No model has zasocitinib data, so every dose would get the same forecast |
| [NCT07820098](https://clinicaltrials.gov/study/NCT07820098), delgocitinib 2% cream, face, 12 patients | Not sealed | Open-label single arm: no control arm to forecast against |
| NCT06548360, NCT06804811 (ruxolitinib cream, children) | No action | Registry updates; sealed forecasts pending, no results posted |
| NCT06163326 (ritlecitinib, 52-week safety study), NCT07673640 (ruxolitinib with corticosteroids, real-world) | No action | Not randomized against placebo |

### Papers (Europe PMC)

| Lead | Decision | Reason |
|---|---|---|
| [TRuE-V mechanism-of-action trial](https://doi.org/10.1016/j.jid.2026.09.857) (ruxolitinib 1.5% BID vs vehicle, 2:1, n = 60; NCT04896385) | Candidate for a future model version, if open access | Randomized with a vehicle arm, but the registry posts only biomarkers and the paper is not open access; responder rates, if reported, cannot be verified yet |
| [Tofacitinib vs corticosteroid mini-pulse RCT](https://doi.org/10.1016/j.jaad.2026.08.061) | Not model data | Active comparator, no placebo; disease stabilization endpoint |
| [Ritlecitinib program synthesis](https://doi.org/10.1177/10600280261493131) | Not model data | Phase 2b only, percent change rather than responder rates; no Tranquillo phase 3 numbers, so the pending forecasts stay unpublished |
| [Ruxolitinib vs tacrolimus](https://doi.org/10.1016/j.jaad.2026.09.062), [upadacitinib + NB-UVB](https://doi.org/10.1093/ced/llag437) | Not model data | Not randomized against placebo |
| 2 case reports or letters, 5 reviews or bibliometric and Delphi studies, 1 ethics paper, 1 graft-versus-host trial | Not model data | No new trial results in vitiligo |
