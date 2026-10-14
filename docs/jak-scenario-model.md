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

- Forecasts of unreported trials are sealed (timestamp plus SHA-256) before their results are looked up. The record holds the data fingerprint, priors, diagnostics and the search for already-public results (`--public-results-check`; registry status alone missed public toplines).
- Model changes are pre-registered and hash-sealed before their first fit; `python scripts/model/verify_preregistrations.py` checks the seals.
- A weekly job (`vitiligo discover check-forecasts`) scores the forecasts as results post. All forecasts and the model scoreboard are in [`forecasts/`](../forecasts/README.md).

## Results (v0.2, back-tests run 2026-10-14)

| Back-test | Instrument | Points | In 80% PI | In 95% PI | Mean abs. error | Converged |
|---|---|---:|---:|---:|---:|---|
| Leave-one-trial-out | F-VASI | 107 | 0.93 | 0.99 | 5.1 pp | all folds |
| Leave-one-trial-out | T-VASI | 139 | 0.95 | 1.00 | 4.3 pp | all folds |
| Weeks ≤ 24 → later | F-VASI | 26 | 0.69 | 0.73 | 10.6 pp | 1 divergence |
| Weeks ≤ 24 → later | T-VASI | 29 | 0.86 | 0.97 | 9.1 pp | yes |

Given a trial's control arm, the model predicts its drug arms well within the studied weeks. Beyond week 24 it over-predicts (TRuE-V week 52: by 20–23 pp on F-VASI, 10–14 pp on T-VASI) and is over-confident. Its phase 3 forecasts were also far too high ([findings](findings.md)).

## Versions

| Version | Change | Status |
|---|---|---|
| v0.1 | Unpooled baselines for uncontrolled trials; bounded placebo drift; route-specific class means; back-test fixes | Superseded. Each change fixed a back-test failure of v0 (e.g. held-out TRuE-V2 over-predicted, 44.6% vs 30.9% F-VASI75). |
| v0.2 | T50 per route; 1,500 draws × 4 chains | **Default.** A shared T50 had over-predicted topical ruxolitinib at week 52 by 15–20 points. |
| v0.3 | Trial-by-treatment effect `γ_t`; phase 3 shift `κ_route`; curated paper rows | Not adopted ([pre-registration](model-v0.3-preregistration.md), [result](../forecasts/v0.3/README.md)). |
| v0.4 | v0.3 fitted with the phase 3 toplines | Challenger, tested prospectively ([pre-registration](model-v0.4-preregistration.md), [forecasts](../forecasts/v0.4/README.md)). |
| v0.5 | v0.4 with separate baselines for oral placebo and topical vehicle | Challenger, tested prospectively ([pre-registration](model-v0.5-preregistration.md), [forecasts](../forecasts/v0.5/README.md)). |

The v0.1 and v0.2 changes were made after seeing back-test results, so those back-tests do not test the model *choice* out of sample. v0.3 onwards are pre-registered.

## Known limitations

- **Small, concentrated data.** Posted results from 9 trials, mostly ruxolitinib cream and ritlecitinib. Results published only in papers are curated separately (`curation/`) and not yet used by the model.
- **Phase 2 to phase 3 gap.** Oral drugs responded far less in phase 3 than in phase 2 ([findings](findings.md)), and v0.2 treats a new trial as typical of the mostly phase 2 trials it was fitted on. v0.4 and v0.5 address this and are being tested.
- **Time course by route only.** T50 is shared within a route and also drives the placebo drift. **Oral agents have no controlled data beyond week 24**, so oral week-52 predictions (e.g. Tranquillo) extrapolate the oral curve; the time-extrapolation back-test can only check this for topical ruxolitinib.
- **Placebo beyond week 24.** Placebo/vehicle data end at week 24, so placebo response later is extrapolated through `π` and `h(w)`.
- **Population differences.** Disease activity, prior therapy, body sites and inclusion criteria are not modelled; they enter only as trial and arm random effects.
- **Dose comparability.** Doses are comparable only within an agent; across agents, the class pooling is an assumption.
