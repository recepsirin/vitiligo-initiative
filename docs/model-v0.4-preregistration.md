# Scenario model v0.4 (challenger): pre-registration

Written 2026-10-14, after v0.3's topline hold-out (E1) and **before** its back-tests (E2) finished. The SHA-256 of this file is recorded in `forecasts/v0.4-preregistration.sha256`.

## Why

v0.3 did not beat v0.2 on E1: summed log score −54.29 vs −54.13 ([`forecasts/v0.3/e1.json`](../forecasts/v0.3/e1.json)). So under its pre-registration it was not adopted.

Fitted without the phase 3 toplines, v0.3 had no evidence about the oral phase 3 gap. Its phase 3 shift for oral drugs stayed at the prior, its medians stayed as high as v0.2's, and only its intervals widened. Learning the gap needs phase 3 oral data, and a model trained on that data can only be tested cleanly on results that are not yet public.

## The challenger

v0.4 is v0.3's structure and data rules, **with** the public phase 3 toplines (`curation/topline-results.json`), at `target_accept = 0.995`. It is v0.3's "production" fit, run as a challenger. **v0.2 remains the default model.**

## Evaluation

**P, prospective (decides).** v0.4 seals forecasts for the 7 targets that v0.2 has already sealed and whose results are not public:
- the 3 pediatric ruxolitinib targets (NCT06548360, NCT06804811);
- Tranquillo week 24, F-VASI75 and T-VASI50;
- Tranquillo 2 50 mg, F-VASI75 and T-VASI50 at week 52.

As results post, both models are scored by the log probability of the observed active and placebo counts (`vitiligo discover check-forecasts`). v0.4 replaces v0.2 as the default only if, once at least 4 targets have resolved, its summed log score on the resolved targets is higher. Until then, v0.2 stays.

**L, leave one oral programme out (report only).** Fit v0.4 without one oral phase 3 programme and predict that programme as new phase 3 trials:
- ritlecitinib (Tranquillo and Tranquillo 2), predicted from the upadacitinib toplines;
- upadacitinib (Viti-Up 1 and 2), predicted from the ritlecitinib toplines.

Compare with v0.2's sealed draws where they exist (6 pairs). This is not first-look and does not decide anything; it shows whether one oral programme's phase 3 shift transfers to another.

## Disclosure

v0.4 exists because v0.3 failed E1. It is trained on public numbers that the v0.2 forecasts missed. Only P is a clean test.

## Amendments

1. **Clarification, 2026-10-14, before any target resolved.** Log scores need sealed predictive draws, and v0.2's two Tranquillo week-24 forecasts were sealed without them. So the comparison uses the targets where every compared model has a log score: 5 targets for v0.2 against a challenger, and all 7 between challengers. The "at least 4 resolved" rule counts those targets. `vitiligo discover check-forecasts` prints the comparison.
