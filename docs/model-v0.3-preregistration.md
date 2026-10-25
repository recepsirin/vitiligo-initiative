# Scenario model v0.3: pre-registration

Written 2026-10-14, before any v0.3 fit. The SHA-256 of this file is recorded in `forecasts/v0.3-preregistration.sha256`. Any later change is listed under *Amendments*.

## Why

The v0.2 forecasts for the phase 3 trials of oral JAK inhibitors were far too high. F-VASI75 was forecast at 38–56% against 12.5–25% observed, and placebo at 9–15% against 2–7% ([topline check](../forecasts/TOPLINE-CHECK-2026-10-14.md)). Within its own phase 2 trial, the model extrapolated upadacitinib reasonably ([curation](../curation/README.md)).

v0.2 lets a drug's effect vary across trials only through a small per-arm deviation (τ). That makes it confident that a phase 2 effect carries over to phase 3.

## Changes (v0.2 → v0.3)

1. **Trial-by-treatment effect.** `γ_t ~ N(0, σ_γ)`, `σ_γ ~ HalfNormal(0.5)`, is added to every active arm of trial t, on the same time course as the drug effect. A new trial draws a new γ. Trials can then differ in how much the drug helps, beyond their placebo response.
2. **Phase 3 shift.** `κ_route · [phase 3]` on the drug effect, with `κ_route ~ N(0, 0.5)` per route. The phase comes from the registry record.
3. **Paper rows.** Curated rows with population `nri` are added (`curation/paper-results.json`). `as_observed` rows are excluded, because their rates are not comparable. The NCT03099304 week-24 cap still applies to registry rows. It does not apply to the paper's 1.5% BID arm, which the paper reports as continuous from day 1.
4. **Toplines (production fit only).** The public week-48/52 numbers for Tranquillo (50 mg), Tranquillo 2 (100 mg) and Viti-Up studies 1 and 2 (`curation/topline-results.json`). Responders are derived from the reported percentages and arm sizes, and the population is assumed `nri`. Viti-Up's two sub-studies count as separate trials.

Everything else is as in v0.2: priors, likelihood, convergence gate (R-hat ≤ 1.01, ESS ≥ 400, 0 divergences) and sampler settings.

## Evaluation

**E1, topline hold-out (decides adoption).** Fit v0.3 with changes 1–3 only, without the toplines. Predict the 6 topline arm pairs that have sealed v0.2 predictive draws (Tranquillo 2 100 mg and Viti-Up 1/2, F-VASI75 and T-VASI50) as new phase 3 trials. Score both models by the log probability of the observed active and placebo counts.
- v0.2 is scored from its sealed draws in `forecasts/2026-10-14-auto/`.
- The two Tranquillo pairs have no sealed draws, so they are reported for v0.3 only.

**E2, back-tests.** The v0.2 leave-one-trial-out and time-extrapolation back-tests, rerun with v0.3 (changes 1–3).

**Adopt v0.3 for forecasting only if all of these hold:**
- (a) its E1 summed log score beats v0.2's on the 6 pairs;
- (b) its E2 leave-one-trial-out 80% coverage is at least 0.75 for both instruments;
- (c) every fit passes the convergence gate.

Otherwise v0.2 stays, and the result is reported.

**E3, prospective.** If adopted, the production v0.3 (changes 1–4) seals new forecasts for the same 3 pediatric ruxolitinib targets that v0.2 already sealed. Both models are then scored when those trials report. It also seals forecasts for the targets whose numbers are not public: Tranquillo week 24 and the Tranquillo 2 50 mg arm. Every sealing records its public-results search.

## Disclosure

- v0.3 was designed after seeing v0.2 miss the phase 3 toplines, so E1 is not first-look.
- Its value is to check that the new structure, fitted without those numbers, would have been less wrong.
- Only E3 is a clean test.

## Amendments

1. **2026-10-14, before any v0.3 score was computed.** The first E1 fit (F-VASI, `target_accept = 0.99`) had 1 divergent transition, which fails the convergence gate. The runs were stopped before any prediction was scored. From then on, **every v0.3 fit uses `target_accept = 0.995`** (E1, E2 and production alike), and the gate is unchanged. The same remedy was needed for the simulator benchmark's v0.2 fit.
2. **Correction, 2026-10-25, with none of the 7 scoreboard targets resolved.** Change 3 above excludes `as_observed` rows "because their rates are not comparable". **For registry rows that exclusion had never run.** Nothing read the `populationDescription` ClinicalTrials.gov posts beside each outcome measure, so no registry row carried a population and the flag the rule tested was never set; it applied only to curated paper rows, where a curator types the population in by hand. This amendment makes the pre-registered rule effective rather than changing it, and adds one rule the pre-registration did not anticipate.

   **What the rule was missing.** TRuE-V reports week 24 as 30.9% of all 222 randomised with missing F-VASI imputed by multiple imputation, and week 52 as 48.0% of the 177 who still had data ("Only participants with available data were analyzed"). Those are different populations, so most of the rise is the denominator moving, and the model was fitting it as one arm's time course — the same artifact the v0.1 note about "class-wide T50 over-predicting topical ruxolitinib from week 24 to 52" was patched to accommodate. Across the corpus, 35 of 69 VASI responder measures count only the patients assessed, 12 impute statistically and 3 impute as failures.

   **How it is enforced now.** `populationDescription` is parsed into `as_observed`, `nri`, `multiple_imputation` or `subgroup`; each trial contributes only the population covering its reference week (week 24, nearest week otherwise, a primary endpoint deciding within a week); subgroups are never fitted. A trial reporting one way throughout, such as ritlecitinib's, contributes everything it did before. The matcher is deliberately narrow: TRuE-V's imputation text also says a non-compliant site "were excluded from this analysis", and a looser subgroup pattern would discard the primary endpoint of both pivotal trials.

   **An additional rule, not pre-registered: retention.** Removing TRuE-V's week-52 rows alone made topical predictions *rise*, because the remaining long-week topical data is NCT05247489's arm, which reports 16 patients at week 4 and 6 at week 48 while climbing to 100%. That arm is internally consistent in population, so the population rule does not reach it. Observations below 80% of the largest group an arm reported at that endpoint are therefore dropped, measured per assessor (a central read of 52 is a different measurement set from a local read of 67, not attrition from it). Both rules apply to fitting, to the scored back-test points and to the simple baselines, so the benchmark still sees exactly what the model sees.

   **Effect on the data.** F-VASI goes from 55 fitted observations to 46 and T-VASI from 64 to 55. No trial and no control arm is lost, so the baseline pooling structure is unchanged.

   **Effect on predictions, declared after the fact and so not a first look.** Three fits per condition at production settings, differing seeds (spread across seeds ≤ 0.3 pp, so these shifts are not sampler noise). For a new trial of topical ruxolitinib 1.5% BID, F-VASI75: week 24 **30.6% → 24.8%**, week 52 **54.2% → 62.4%**; 0.75% BID at week 24, which three sealed targets forecast, **27.2% → 22.0%**; oral ritlecitinib 50 mg at week 52 **47.4% → 50.3%**, moving because cut-points and class means are shared rather than because its own data changed. The mechanism is `T50`: TRuE-V's modest 24→52 rise implied a shorter half-time, and without it the remaining evidence is NCT05247489 still climbing at week 40, which implies a longer one — raising the asymptote `(24+T50)/24` and lowering the pre-24 build. Measured against the only trial that can check it, the corrected model is *less* accurate on these two points (TRuE-V observed 30.9% at week 24). That is the finding, not an argument for putting the data back: the earlier agreement was produced by fitting a week-52 rate measured on a different population from its own week 24. What the correction mainly establishes is that the number was never supported: exactly two F-VASI observations past week 24 survive in the whole corpus, both from one 35-patient arm receiving ruxolitinib **and NB-UVB phototherapy**, uncontrolled. Phototherapy shifts the level through `phi` but shares the route's T50, so the facial time course past six months is borrowed from arms given both treatments; `predict` now reports that, and reports week 52 as beyond ruxolitinib's data at all, which it did not while the week-52 rows were in. Facial week-52 predictions should be read as unsupported by data rather than merely uncertain. The whole-body side keeps one clean late arm (NCT05750823, week 48, n=37).

   **Not done here, and deliberately.** Letting one phototherapy arm set the topical time course is itself a modelling problem, and the obvious remedies — excluding that arm from `T50`, or giving phototherapy its own time course — are model changes that need their own pre-registration. Bundling either with this data correction would leave neither assessable.

   **Effect on the sealed forecasts.** None are altered: the seals and sealed draws are what was predicted on the day, and scoring them against results is unaffected. But re-fitting does not reproduce them, their recorded `data_sha256` no longer describes the corpus, and five of the seven scoreboard targets are topical ruxolitinib or ritlecitinib, so forecasts sealed either side of this date are not comparing models ([scoreboard note](../forecasts/README.md#scoreboard)). The week-24-to-later back-test lost its F-VASI held-out points with the excluded rows and can no longer check facial time extrapolation.
