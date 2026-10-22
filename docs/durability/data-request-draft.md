# Data request draft: who keeps repigmentation after stopping ruxolitinib cream?

Draft for a request to Incyte (datasharing@incyte.com), following the fields of its data sharing request form. **Not submitted.** Submission needs a named research team that includes a biostatistician, and the analysis plan below should be pre-registered before any data are received.

## Eligibility, checked 2026-10-23

Incyte's published data sharing process (PDF metadata dated 2020; check for a newer version before submitting) covers:
- interventional studies other than phase 1, of products and indications approved since 2020 in a major market;
- data shared after the primary publication, or 2 years after the study ended.

**Ruxolitinib cream for vitiligo meets both:** it was approved in the US in 2022, the long-term extension's primary completion was November 2022, and its primary publication is in 2026.

**The process will not support** re-evaluating safety or efficacy questions already addressed in the product labelling. This request asks a different question: who keeps their response after stopping.

## Research objectives

1. **Who keeps their response after stopping?** Among patients with near-complete facial repigmentation (≥ F-VASI90) at week 52, randomized to vehicle in the TRuE-V long-term extension: which characteristics predict time to relapse (< F-VASI75) and time to losing F-VASI90?
2. **Who benefits most from continuing?** Does the benefit of continuing (the randomized comparison) differ by those characteristics?
3. **How is response lost?** How do F-VASI and T-VASI change after stopping, visit by visit, and does body response fade before facial response?

Why it matters: relapse after stopping is the largest unmet need in vitiligo ([`success.md`](../success.md), outcome 3). This is the only randomized withdrawal of a JAK inhibitor with results.

## Studies in scope

| Study | Role |
|---|---|
| TRuE-V long-term extension (NCT04530344) | Randomized withdrawal: the outcome data |
| TRuE-V1 (NCT04052425), TRuE-V2 (NCT04057573) | Baseline characteristics and the 52-week course of response before withdrawal |

## Endpoints

- **Primary:** time to relapse (< F-VASI75) after withdrawal, as defined in the extension.
- **Secondary:**
  - time to losing F-VASI90;
  - time to losing T-VASI50, for patients with it at week 52;
  - F-VASI and T-VASI by visit after withdrawal;
  - rescue treatment.

## Statistical analysis plan (outline)

**Few events limit the analysis.** About 56 patients stopped. Derived from the posted hazard ratios, about 15 relapsed and about 28 lost F-VASI90 ([`truev-reference.json`](data/truev-reference.json)). That supports two or three pre-specified predictors, not a search through many.

**Pre-specified predictors**, chosen for biology rather than fit:
1. **Disease activity at baseline** (active vs stable), as a marker of an ongoing immune attack.
2. **Depth of facial response at withdrawal** (percentage F-VASI improvement at week 52), as the margin above the relapse threshold.
3. **Body response at withdrawal** (T-VASI improvement at week 52).

**Models.**
- **Cox proportional hazards**, with each predictor and an interaction with the randomized arm (objective 2). A ridge penalty applies if all three are fitted jointly.
- **Kaplan–Meier curves** by pre-specified groups.
- **No model selection.** All results are reported with confidence intervals, including null ones.

**Checks.** Proportional hazards, the effect of rescue treatment (censoring at rescue vs counting rescue as relapse), and study (TRuE-V1 vs 2) as a stratum.

**Use in forecasts.** Results update the oral durability forecasts only through a new pre-registration ([`durability-forecast-preregistration.md`](../durability-forecast-preregistration.md) stays as sealed).

## Data requirements

Anonymized patient-level data, with data dictionaries:
- **Baseline:** age band, sex, Fitzpatrick skin type, disease duration, active vs stable disease, baseline F-VASI and T-VASI, prior treatments.
- **Response:** F-VASI and T-VASI at every visit from baseline of the parent study to week 104.
- **Extension:** randomization arm, rescue treatment and its timing, discontinuation and its reason.
- **Documents:** protocols and statistical analysis plans.

## Publication plan

- Pre-registration of the analysis, sealed before data access.
- Open-access preprint, then a peer-reviewed paper.
- Analysis code public.
- Results reported whether or not the predictors matter.

## To complete before submission

- [ ] Named team, with a biostatistician and a clinical vitiligo expert
- [ ] Conflict-of-interest statements
- [ ] Incyte's current request form and policy version
- [ ] Pre-registration of the analysis plan, sealed and committed
