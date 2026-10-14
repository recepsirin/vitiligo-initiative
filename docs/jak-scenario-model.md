# JAK Inhibitor Scenario Model (v0.2)

**Status:** research model, local-first. Not medical advice; not a basis for treatment decisions.
**Code:** `src/vitiligo/models/jak_mbma.py` · **CLI:** `vitiligo model backtest`, `vitiligo model predict`
**Install:** `pip install -e '.[model]'` (adds PyMC)

## What it answers

"What share of patients reach endpoint *E* by week *W* on regimen *R*, compared with placebo in the same trial?"
Every answer is a probability distribution (median plus 80% and 95% intervals), with explicit notes when it extrapolates beyond the data.

## Pipeline

1. `vitiligo report jak`: registry atlas of JAK-family vitiligo trials.
2. `vitiligo report jak-arms`: harmonized arm × endpoint × week table from posted ClinicalTrials.gov results.
3. `vitiligo model …`: the model below, fitted to the model-ready rows.

## Data rules

The model fits responder endpoints from step 2. For each instrument (F-VASI or T-VASI), a row is used only if:

- the arm is active or placebo/vehicle, not a mid-arm treatment switch;
- it is not from a separate extension or randomized-withdrawal study;
- week, *n* and responders are known.

Where a trial reports both central and local VASI reads, only the central reads are used.

Continuation periods inside a trial (e.g. TRuE-V weeks 24–52) are used when the regimen does not change.

**Design annotations** (`DESIGN_ANNOTATIONS`) capture study-design facts the registry fields cannot express. They are listed in every model output and should be expert-reviewed.

- **NCT03099304** is capped at week 24. After week 24 its arms were re-assigned, so arms observed later are selected subsets, not the randomized population.

## Model

An ordered-probit model-based meta-analysis, the form used in NICE network meta-analyses of PASI50/75/90 in psoriasis, applied to VASI thresholds:

```
P(improvement ≥ k | arm a, trial t, week w) = Φ( μ_t + π·(h(w) − 1) + D_a·h(w) − c_k )
```

**Model terms**

| Term | Meaning |
|---|---|
| `c_k` | Cut-points shared by all trials (`c_50 = 0`). Data at one threshold inform the others. |
| `μ_t` | Trial baseline (placebo/vehicle response at week 24). Partially pooled across **controlled** trials; trials with no control arm get their own unpooled baseline, so they inform the time course and within-trial contrasts (e.g. phototherapy) but not the absolute size of drug effects. |
| `π` | Placebo-response drift along the same saturating time course as the drug effect (zero at week 24). |
| `D_a` | Active-arm effect; see the components below. Zero for placebo arms. |
| `h(w) = [w/(w+T50)]·[(24+T50)/24]` | How the effect builds over time, with a half-time T50 **per route** (oral vs topical); `h(24) = 1`. A control arm follows its trial's route. |

**Components of the active-arm effect `D_a`**

| Component | Meaning |
|---|---|
| `α_agent` | Drug effect at the reference dose. Partially pooled toward a **route-specific** class mean (oral vs topical), so a drug borrows strength only from drugs given the same way, and an unseen drug gets its route's class prediction. |
| `β_agent · log(daily dose / reference dose)` | Dose response. The reference dose is the agent's highest studied daily dose; cream dose = concentration × applications per day. |
| `λ · loading_dose` | Effect of starting with a loading dose. |
| `φ · phototherapy` | Effect of adding phototherapy. |
| `ε_a` | Random deviation of each arm. |
| `γ_t` (v0.3) | Trial-by-treatment effect: how much more or less the drug helps in this trial than in others, beyond its placebo response. Shared by the trial's active arms; a new trial draws a new one. |
| `κ_route · [phase 3]` (v0.3) | Shift of the drug effect in phase 3 trials, per route. |

Thresholds observed in the same arm and week are nested: every F-VASI90 responder is also an F-VASI75 responder. The likelihood is therefore a chain of conditional binomials, which is equivalent to a multinomial over the response bands.

Priors are weakly informative on the probit scale and are reported in full with every frozen forecast (`PRIORS`). A fit is accepted only if max R-hat ≤ 1.01, bulk ESS ≥ 400 and there are 0 divergent transitions. Otherwise `predict` refuses to answer.

## Evaluation protocol

The model is judged only on data it has not seen.

| Back-test | Design | Question |
|---|---|---|
| Leave-one-trial-out | For each controlled trial: drop its active arms, keep its control arm, refit, then predict the dropped arms' observed rates (with binomial noise for the arm's size). | Given a trial's placebo response, does the model predict its drug arms? |
| Time extrapolation | Fit on weeks ≤ 24 only, then predict later weeks of the same arms. | Does the response-over-time curve hold beyond week 24? (The Tranquillo forecast depends on this.) |

Metrics: coverage of the 80% and 95% predictive intervals (well calibrated ≈ 0.80 and 0.95) and mean absolute error in percentage points.

## Forecasting policy

Pre-registrations are hash-sealed before their first fit; `python scripts/model/verify_preregistrations.py` checks that each still matches its seal (amendments are appended afterwards and listed in the document).

Forecasts of unreported trials are **frozen before any results are looked up** (and before sealing, sponsor press releases and conference abstracts must be searched too, because registry status alone missed public toplines): timestamped and sealed with a SHA-256 of their content (`vitiligo model predict … --freeze PATH`). The frozen file records the data fingerprint, priors, diagnostics and the public-results search, so the forecast can be checked against results later and cannot be quietly revised. A weekly job (`vitiligo discover check-forecasts`) scores them as results are posted.

## Results (v0.2, corpus snapshot May 2026, back-tests run 2026-10-14)

| Back-test | Instrument | Points | In 80% PI | In 95% PI | Mean abs. error | Mean signed error | Converged |
|---|---|---:|---:|---:|---:|---:|---|
| Leave-one-trial-out | F-VASI | 107 | 0.93 | 0.99 | 5.1 pp | see file | all folds |
| Leave-one-trial-out | T-VASI | 139 | 0.95 | 1.00 | 4.3 pp | see file | all folds |
| Time extrapolation (≤ wk 24 → later) | F-VASI | 26 | 0.69 | 0.73 | 10.6 pp | over-predicts TRuE-V wk 52 by ~20–23 pp | 1 divergence |
| Time extrapolation (≤ wk 24 → later) | T-VASI | 29 | 0.86 | 0.97 | 9.1 pp | over-predicts TRuE-V wk 52 by ~10–14 pp | yes |

**Reading:**
- Given a trial's control arm, the model predicts its drug arms well, at least within the studied weeks.
- Extrapolating beyond week 24 is the weak point. It over-predicts and is over-confident for TRuE-V's week-52 extension, while the uncontrolled ruxolitinib + NB-UVB trial extrapolates almost without bias. That points to a data-semantics question (how the extension results were analysed) as much as to model structure. The large per-trial errors for the small Phase 2 folds reflect wide intervals around few patients.

**Forecasts:** four Tranquillo (NCT05583526) forecasts were frozen on 2026-10-14 without consulting results. They are **not prospective**: Pfizer had announced the topline on 2026-07-30 and the numbers at EADV on 2026-10-03. Scored against those numbers, F-VASI75 at week 52 was over-predicted (45.8% vs 12.5% observed), and T-VASI50 was wrongly forecast not to separate from placebo ([topline check](../forecasts/TOPLINE-CHECK-2026-10-14.md)).

- **Location:** `forecasts/2026-10-14-tranquillo/`, including the sealed records, the back-test files they reference, and a post-freeze assessment of known weaknesses.
- **In short:** ritlecitinib 50 mg is forecast to beat placebo on F-VASI75 (P ≈ 0.99 at weeks 24 and 52; the magnitude at week 52 is very uncertain and likely biased high). It is forecast **not** to separate on T-VASI50, a low-confidence result driven by Phase 2b's week-24 data and the model's inability to represent late-onset effects.

## Change log

| Version | Change | Why |
|---|---|---|
| v0.1 | Uncontrolled trials get unpooled baselines | In v0, a single-arm trial's high response partly counted as drug effect, so held-out TRuE-V2 was over-predicted (44.6% vs 30.9% F-VASI75). |
| v0.1 | Placebo drift `π·(h(w)−1)` replaces `π·log(w/24)` | The log term, fitted on weeks 4–24, grew without bound; in v0, week-52 predictions overshot by 15–20 points. |
| v0.1 | Route-specific class means | In v0, held-out oral upadacitinib inherited topical ruxolitinib's larger F-VASI effect. |
| v0.1 | Back-tests no longer score rows excluded by design annotations; per-fold convergence is reported | Bug fixes. |
| v0.3 (pre-registered, [`model-v0.3-preregistration.md`](model-v0.3-preregistration.md)) | Trial-by-treatment effect `γ_t`; phase 3 shift `κ_route`; curated paper rows counted the registry's way; public phase 3 toplines in the production fit; `target_accept` 0.995 | v0.2 forecast the oral phase 3 trials 13–34 points too high: it treated phase 2 effects as transferring almost exactly to phase 3. **Not adopted:** fitted without the toplines, it scored −54.29 against v0.2's −54.13 on the held-out phase 3 toplines. With no phase 3 oral data, its phase 3 shift stayed at the prior, so it only widened its intervals. |
| v0.5 (challenger, [`model-v0.5-preregistration.md`](model-v0.5-preregistration.md)) | v0.4 with a separate baseline mean for oral-placebo and topical-vehicle trials | v0.4's forecasts for topical ruxolitinib in children were pulled down by the low oral phase 3 placebo rates. Same prospective test ([`forecasts/v0.5/`](../forecasts/v0.5/README.md)). |
| v0.4 (challenger, [`model-v0.4-preregistration.md`](model-v0.4-preregistration.md)) | v0.3 trained on the phase 3 toplines | Can only be tested prospectively. It has sealed forecasts for the same 7 targets as v0.2, and replaces v0.2 only if it scores better once at least 4 have resolved. Report-only check, holding out one oral programme at a time: −49.2 vs v0.2's −54.1 ([`forecasts/v0.4/`](../forecasts/v0.4/README.md)). |
| v0.2 | T50 per route instead of class-wide; 1,500 draws × 4 chains (was 1,000) | With one shared T50, v0.1 over-predicted topical ruxolitinib from week 24 to week 52 by 15–20 points (the shared half-time was driven by slow-onset oral data). Two v0.1 folds just missed the convergence gate. |

**Disclosure:** the v0.1 and v0.2 changes were made after seeing back-test results, so their back-tests are not a pure out-of-sample test of the model *choice*. Each change has an independent rationale (above). **Pre-commitment (recorded before the v0.2 back-test ran):** v0.2 is the last model change before the Tranquillo forecast is frozen; whatever the v0.2 back-test shows is reported as-is and sealed into the forecast record.

## Known limitations

- **Small, concentrated data.** Posted results from 9 trials, mostly ruxolitinib cream and ritlecitinib. Results published only in papers are curated separately (`curation/`) and not yet used by the model.
- **Phase 2 to phase 3 gap.** Phase 3 trials of oral drugs responded far below phase 2 (upadacitinib F-VASI75: at least 51% at week 52 in phase 2, about 25% at week 48 in phase 3). The model treats a new trial as typical of the mostly phase 2 trials it was fitted on ([`curation/README.md`](../curation/README.md)).
- **Time course by route only.** T50 is shared within a route and also drives the placebo drift. **Oral agents have no controlled data beyond week 24**, so oral week-52 predictions (e.g. Tranquillo) extrapolate the oral curve; the time-extrapolation back-test can only check this for topical ruxolitinib.
- **Placebo beyond week 24.** Placebo/vehicle data end at week 24, so placebo response later is extrapolated through `π` and `h(w)`.
- **Population differences.** Disease activity, prior therapy, body sites and inclusion criteria are not modelled; they enter only as trial and arm random effects.
- **Dose comparability.** Doses are comparable only within an agent; across agents, the class pooling is an assumption.
