# Scenario model v0.5 (challenger): pre-registration

Written 2026-10-14, after sealing v0.4 and before any v0.5 fit. The SHA-256 of this file is recorded in `forecasts/v0.5-preregistration.sha256`. No result for any forecast target was public or seen at the time of writing.

## Why

v0.4 roughly halved v0.2's forecasts, including topical ruxolitinib in children (about 13% vs 24% F-VASI75 at week 24). In adults and adolescents, topical ruxolitinib reached about 30%. The likely cause, noted right after v0.4 was sealed ([`forecasts/v0.4/`](../forecasts/v0.4/README.md)), is that oral placebo and topical vehicle share one baseline. The very low oral phase 3 placebo rates then pull every new trial down, topical included.

## The change (v0.4 → v0.5)

The mean trial baseline becomes **route-specific**: `μ_t ~ N(μ0_route(t), σ_μ)`, with `μ0_route ~ N(−1.5, 1.0)` per route (oral placebo, topical vehicle). A new trial draws its baseline from its route's mean. Everything else is v0.4: data (including the toplines), priors, `target_accept = 0.995` and the convergence gate.

## Evaluation

**P, prospective (decides).** v0.5 seals forecasts for the same 7 targets as v0.2 and v0.4, with the same public-results search. Once at least 4 targets have resolved, the model with the highest summed log score on the resolved targets becomes the default. If v0.2 is not beaten, it stays.

**L, leave one oral programme out (report only, not first-look).** As for v0.4.

## Disclosure

This change was motivated by v0.4's forecasts, not by any result for these targets. Only P is a clean test.

## Amendments

1. **Clarification, 2026-10-14, before any target resolved.** Log scores need sealed predictive draws, and v0.2's two Tranquillo week-24 forecasts were sealed without them. So the comparison uses the targets where every compared model has a log score: 5 targets for v0.2 against a challenger, and all 7 between challengers. The "at least 4 resolved" rule counts those targets. `vitiligo discover check-forecasts` prints the comparison.
