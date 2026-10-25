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
- week, *n* and responders are known;
- it was measured on the analysis population its trial anchors its time course to;
- its arm still reports at least 80% of the largest group it reported at that endpoint.

Where a trial reports both central and local VASI reads, only the central reads are used.

**Analysis population.** A sequence of responder rates is only a time course if its points were computed the same way, and the registry says how in each measure's population description. The corpus contains three ways: counting only the patients assessed at a visit (35 of 69 VASI responder measures), imputing a missing result as a failure (3), and imputing it from the rest of the data (12). TRuE-V uses the third at week 24 and the first at week 52 — 30.9% of 222 randomized, then 48.0% of the 177 with data — so most of that rise is the denominator moving. Each trial therefore contributes only the population covering its reference week (week 24, or the nearest week to it, a primary endpoint deciding within a week). Trials that report one way throughout, such as ritlecitinib's, contribute everything. Subgroup rows are never used.

**Retention.** An arm stops describing the group it enrolled once enough of that group has left. NCT05247489's ruxolitinib arm reports 16 patients at week 4 and 6 at week 48, rising to 100%; fitting that estimates how quickly the patients who stayed were improving. Observations below 80% of an arm's largest reported group at that endpoint are dropped, measured per assessor, because a central read of 52 is a different measurement set from a local read of 67 rather than attrition from it.

Continuation periods inside a trial (e.g. TRuE-V weeks 24–52) keep the same regimen but not always the same analysis population, so the population rule decides whether they are used; for TRuE-V it is not.

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

## Results (v0.2, back-tests re-run 2026-10-25 on the corrected dataset)

| Back-test | Instrument | Points | In 80% PI | In 95% PI | Mean abs. error | Converged |
|---|---|---:|---:|---:|---:|---|
| Leave-one-trial-out | F-VASI | 99 | 0.96 | 1.00 | 2.91 pp | NCT03099304 fold: 1 divergence |
| Leave-one-trial-out | T-VASI | 131 | 0.94 | 1.00 | 2.48 pp | all folds |
| Weeks ≤ 24 → later | F-VASI | 6 | 1.00 | 1.00 | 2.77 pp | yes |
| Weeks ≤ 24 → later | T-VASI | 9 | 0.89 | 1.00 | 6.87 pp | yes |

Previously (2026-10-14, before the analysis-population and retention rules): F-VASI 107 points at 5.1 pp and T-VASI 139 at 4.3 pp for leave-one-trial-out; 26 F-VASI points at 10.6 pp (coverage 0.69) and 29 T-VASI at 9.1 pp for the week-24-to-later test.

**Do not read the lower errors as the model having improved.** The rows that left the scored set are the ones it predicted worst, because they were the ones measured on a different analysis population or reported by an arm that had lost its group. Removing a hard question raises the average mark.

**The F-VASI week-24-to-later test no longer tests extrapolation.** Its 26 points were mostly TRuE-V week 52; the 6 that remain are weeks 32 and 40 of NCT05247489's NB-UVB arm, whose own weeks 4–24 were in the fit. Predicting the next visits of an arm you have already seen is a far easier question than predicting a different trial's week 52 from its week 24, so 2.77 pp and coverage 1.00 say almost nothing. T-VASI keeps a little more (9 points, 3 of them NCT05750823's week 48 without phototherapy).

**One F-VASI fold now fails the convergence gate.** Holding out NCT03099304 leaves 1 divergent transition at `target_accept = 0.99`, and that fold predicts 8.6–25% against 25.8–50% observed (coverage 0.25, 24.95 pp). v0.3 onwards uses `target_accept = 0.995` for this reason ([amendment](model-v0.3-preregistration.md#amendments)); the v0.2 figure above is reported as it ran.

**These back-tests helped choose the model.** v0.1's changes were made to fix v0's back-test failures (see Versions), so the back-tests are held out for each fit but not for the design. Only the sealed forecasts are clean tests.

Given a trial's control arm, the model predicts its drug arms well within the studied weeks. What it used to show beyond week 24 — over-predicting TRuE-V week 52 by 20–23 pp on F-VASI and 10–14 pp on T-VASI — was measured against figures now excluded for mixing analysis populations, so that check no longer exists and nothing has replaced it. Its phase 3 forecasts were also far too high ([findings](findings.md)).

## Checked against what the data can bound

Excluding TRuE-V's week-52 rows for mixing analysis populations took away the only F-VASI evidence the week-24-to-later back-test had. Those rows are still evidence, though — they are just not a figure. TRuE-V2 reports 48.0% of the 177 patients assessed at week 52, out of the 222 the arm had at week 24; the 45 it does not cover either reached F-VASI75 or did not, so the rate over that group is **between 38.3% and 58.6%** whatever they did. A prediction outside that range is wrong at either end, which makes the row scorable where it is not fittable (`python scripts/model/bounds_check.py`, [`reports/bounds.py`](../src/vitiligo/reports/bounds.py)).

This is a weaker test than a back-test against a known figure, and it is deliberately asymmetric. Landing outside a bracket is a failure. Landing inside a 20-point bracket is a weak pass, because almost any plausible prediction would. It is worth running because the alternative, after the correction, is no check at all on facial time extrapolation.

Two properties make the bracket honest. It assumes nothing about why patients were not assessed — not that they were missing at random, which the model's imputation would need, nor that they all failed, which non-responder imputation assumes. And the reference group is named rather than inferred: a rate bracketed over an arm's week-24 analysis set is a statement about that set, not about everyone randomised, and the two differ whenever a trial dropped a site or a visit.

The same brackets are reported to clinicians (`GET /api/evidence`), where the published figure would otherwise be read as the answer. It is not: by construction, counting only the patients assessed is the most favourable reading available.

### Result (v0.2, 2026-10-25): the facial time course fails, the whole-body one passes

Conditioned on each trial's own baseline, so between-trial variation is not an excuse. Brackets wider than 25 points are reported but tell us nothing — NCT03099304's reach 94 points because its denominators collapsed — so the informative rows are TRuE-V's.

| Trial | Endpoint | Week | Bracket over the arm's week-24 group | Predicted (mean) | Over the ceiling by |
|---|---|---:|---:|---:|---:|
| TRuE-V1 NCT04052425 | F-VASI25 | 52 | 70.1–91.9% of 221 | 94.5% | +2.6 |
| TRuE-V1 | F-VASI50 | 52 | 58.8–80.5% | 88.9% | +8.4 |
| TRuE-V1 | F-VASI75 | 52 | 41.2–62.9% | 74.6% | +11.7 |
| TRuE-V1 | F-VASI90 | 52 | 25.8–47.5% | 53.5% | +6.0 |
| TRuE-V2 NCT04057573 | F-VASI25 | 52 | 65.8–86.0% of 222 | 94.8% | +8.8 |
| TRuE-V2 | F-VASI50 | 52 | 59.0–79.3% | 89.3% | +10.0 |
| TRuE-V2 | F-VASI75 | 52 | 38.3–58.6% | 75.3% | **+16.7** |
| TRuE-V2 | F-VASI90 | 52 | 22.1–42.3% | 54.4% | +12.1 |

**All 8 informative facial brackets are over-predicted**, by 2.6 to 16.7 points above what the trial could have shown had every uncounted patient responded. On the whole body, **8 of 8 land inside** (`exports/model/bounds-check-T-VASI.json`).

That contrast localises the fault rather than just measuring it. The whole-body side keeps one late arm without phototherapy (NCT05750823, week 48, n=37); the facial side keeps none, and its time course past week 24 comes entirely from NCT05247489's arm on ruxolitinib **and** NB-UVB. `T50` is shared within a route, so phototherapy's faster build is being applied to the drug alone. **This is the evidence for the model change the correction's amendment deferred** — giving phototherapy its own time course, or holding that arm out of `T50` — which needs its own pre-registration, and now has a measured failure to be judged against rather than an intuition.

## Compared with simple baselines

A model-based meta-analysis is worth its complexity only if it beats the obvious thing. Two baselines are scored on exactly the points the leave-one-trial-out back-test scored, so only the method differs (`python scripts/model/baseline_compare.py`, [`models/baseline.py`](../src/vitiligo/models/baseline.py)):

- **Pooled rate.** The rates other trials reported for the same route, threshold and week. It knows nothing about this trial.
- **Placebo-anchored.** This trial's own control arm, plus the pooled log-odds difference between active and control arms in other trials.

| Instrument | Points | Model | Pooled rate | Placebo-anchored |
|---|---:|---:|---:|---:|
| F-VASI | 62 of 99 | **3.95 pp** (0.95) | 8.9 pp (0.65) | 15.93 pp (0.37) |
| T-VASI | 54 of 131 | 2.51 pp (0.98) | **2.21 pp** (0.89) | 4.16 pp (0.83) |

Mean absolute error, with 80% interval coverage in brackets. Re-run 2026-10-25 on the corrected dataset; previously F-VASI 77 of 107 (model 4.3 pp, pooled 15.6, anchored 16.9) and T-VASI 84 of 139 (4.0, 3.6, 4.8).

- **On the face, the model beats the placebo-anchored baseline** by 11.98 pp (95% CI 2.61–13.58) but **is not distinguishable from simply pooling other trials' rates**, by 4.95 pp (−1.62 to 6.26). That conclusion is unchanged in direction — the pooled interval crossed zero before as well — but the margin halved, because pooling is much better on the corrected set (8.9 pp against 15.6) once the rows that no arm's own population supported are gone.
- **On the body, pooling and the model are now level**, pooling ahead by 0.3 pp (−0.78 to 0.27, crossing zero). Before the correction pooling won by a margin that did separate from zero, 0.4 pp (0.2–2.7). T-VASI rates are low and alike across trials, so their average is hard to beat.
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
- **Time course by route only.** T50 is shared within a route and also drives the placebo drift. **Oral agents have no controlled data beyond week 24**, so oral week-52 predictions (e.g. Tranquillo) extrapolate the oral curve.
- **Neither does the face past week 24, now.** Excluding TRuE-V's week-52 rows for mixing analysis populations leaves exactly two F-VASI observations beyond week 24 in the whole corpus, both from NCT05247489's 35-patient arm receiving ruxolitinib **and NB-UVB phototherapy**, uncontrolled. Phototherapy shifts the level through `phi` but shares the route's T50, so the facial time course past six months is borrowed from arms given both treatments; `predict` now says so in its extrapolation notes. The week-24-to-later back-test lost its F-VASI evidence with those rows, so there is nothing left to check it against. The whole-body side keeps one clean late arm (NCT05750823, week 48, n=37). **Treat facial week-52 predictions as unsupported by data rather than merely uncertain** — and note that the earlier figure was no better, having been fitted to a week-52 rate measured on a different population from its own week 24.
- **Placebo beyond week 24.** Placebo/vehicle data end at week 24, so placebo response later is extrapolated through `π` and `h(w)`.
- **Population differences.** Disease activity, prior therapy, body sites and inclusion criteria are not modelled; they enter only as trial and arm random effects. The registry posts baseline severity per arm for six of the trials with results (baseline F-VASI, T-VASI or affected body-surface area; NCT03468855 also posts disease duration), so for those trials this is a gap in the model rather than in the data ([roadmap](roadmap.md) 0.3).
- **Dose comparability.** Doses are comparable only within an agent; across agents, the class pooling is an assumption.
