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

- Forecasts of unreported trials are sealed (timestamp plus SHA-256) before their results are looked up. The record holds the data fingerprint, priors, diagnostics, the search for already-public results (`--public-results-check`; registry status alone missed public toplines) and the git commit of the code. Sealing refuses to run while the model code has uncommitted changes.
- Model changes are pre-registered and hash-sealed before their first fit; `python scripts/model/verify_preregistrations.py` checks the seals.
- A weekly job (`vitiligo discover check-forecasts`) scores the forecasts as results post. Only the 7 targets named in the v0.4/v0.5 pre-registrations decide the default model; forecasts sealed later are scored but do not count. All forecasts and the model scoreboard are in [`forecasts/`](../forecasts/README.md).
- The same job runs `vitiligo discover watch`: it ranks pending results by how much they would tell us about which model is right, and lists new papers, trials and SEC filings. Each lead is triaged in [`forecasts/watch-triage.md`](../forecasts/watch-triage.md).

## Results (v0.2, back-tests run 2026-10-14)

| Back-test | Instrument | Points | In 80% PI | In 95% PI | Mean abs. error | Converged |
|---|---|---:|---:|---:|---:|---|
| Leave-one-trial-out | F-VASI | 107 | 0.93 | 0.99 | 5.1 pp | all folds |
| Leave-one-trial-out | T-VASI | 139 | 0.95 | 1.00 | 4.3 pp | all folds |
| Weeks ≤ 24 → later | F-VASI | 26 | 0.69 | 0.73 | 10.6 pp | 1 divergence |
| Weeks ≤ 24 → later | T-VASI | 29 | 0.86 | 0.97 | 9.1 pp | yes |

**These back-tests helped choose the model.** v0.1's changes were made to fix v0's back-test failures (see Versions), so the back-tests are held out for each fit but not for the design. Only the sealed forecasts are clean tests.

**Calibration runs in opposite directions on either side of week 24.** Within the studied weeks the intervals are wider than nominal (0.93 and 0.95 of points inside an 80% interval), so the model is conservative there. Extrapolating past week 24, F-VASI coverage falls to 0.69, below nominal, while T-VASI stays near it at 0.86.

Given a trial's control arm, the model predicts its drug arms well within the studied weeks. Beyond week 24 it over-predicts (TRuE-V week 52: by 20–23 pp on F-VASI, 10–14 pp on T-VASI) and is over-confident. Its phase 3 forecasts were also far too high ([findings](findings.md)).

## Compared with simple baselines

A model-based meta-analysis is worth its complexity only if it beats the obvious thing. Two baselines are scored on exactly the points the leave-one-trial-out back-test scored, so only the method differs (`python scripts/model/baseline_compare.py`, [`models/baseline.py`](../src/vitiligo/models/baseline.py)):

- **Pooled rate.** The rates other trials reported for the same route, threshold and week. It knows nothing about this trial.
- **Placebo-anchored.** This trial's own control arm, plus the pooled log-odds difference between active and control arms in other trials.

| Instrument | Points | Model | Pooled rate | Placebo-anchored |
|---|---:|---:|---:|---:|
| F-VASI | 77 of 107 | **4.3 pp** (0.99) | 15.6 pp (0.73) | 16.9 pp (0.39) |
| T-VASI | 84 of 139 | 4.0 pp (0.93) | **3.6 pp** (0.94) | 4.8 pp (0.79) |

Mean absolute error, with 80% interval coverage in brackets.

- **On the face, the model earns its complexity.** It beats the placebo-anchored baseline by 12.7 pp (95% CI 2.9–14.4) and the pooled rate by 11.4 pp (−0.4 to 13.2).
- **On the body, it does not.** Pooling other trials' T-VASI rates was slightly better, by 0.4 pp (0.2–2.7). T-VASI rates are low and alike across trials, so their average is hard to beat.
- **Read those intervals as rough.** Points within a trial share its patients, so the bootstrap resamples trials; the common subsets hold only 5 and 4 trials. This is a direction, not a significance test.
- **The baselines are not replacements.** They predict only where other trials report the same week, abstaining on 30 of 107 F-VASI and 55 of 139 T-VASI points, and they cannot forecast an unreported trial at a new dose or week, which is what the model is for.
- **A time-course baseline was barely estimable.** A slope in log(week) needs control-anchored arms at more than one week. Outside the two oral trials, every control arm in this corpus reports week 24 only, so a slope existed for 16 F-VASI and 9 T-VASI points. The corpus carries almost no control-anchored information about how the effect grows with time — the same gap behind the failed week-24-to-later back-test above.

**Post hoc.** These results were public before the comparison, they shaped the model's development, and the baselines were written after reading the model's back-test. The prospective version is to seal a baseline beside every model forecast and score both as results post ([roadmap](roadmap.md) 0.1).

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
- **Population differences.** Disease activity, prior therapy, body sites and inclusion criteria are not modelled; they enter only as trial and arm random effects. The registry posts baseline severity per arm for six of the trials with results (baseline F-VASI, T-VASI or affected body-surface area; NCT03468855 also posts disease duration), so for those trials this is a gap in the model rather than in the data ([roadmap](roadmap.md) 0.3).
- **Dose comparability.** Doses are comparable only within an agent; across agents, the class pooling is an assumption.
