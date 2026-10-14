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
