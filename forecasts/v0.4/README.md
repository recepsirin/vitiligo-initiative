# v0.4 challenger forecasts (sealed 2026-10-14)

Pre-registration: [`docs/model-v0.4-preregistration.md`](../../docs/model-v0.4-preregistration.md). v0.4 is v0.3's structure fitted **with** the public phase 3 toplines. v0.2 remains the default model. Both have sealed forecasts for the same 7 targets, and they are compared as results post.

| Target | v0.4 active (80%) | v0.4 placebo | v0.2 active (80%) | v0.2 placebo |
|---|---|---|---|---|
| Ruxolitinib 1.5% cream, children, F-VASI75 wk 24 (NCT06548360) | 12.8% (3–34) | 1.9% | 24.0% (6–57) | 2.8% |
| Ruxolitinib 0.75% cream, children, F-VASI75 wk 24 (NCT06804811) | 9.8% (2–29) | 1.9% | 20.3% (5–53) | 2.8% |
| Ruxolitinib 1.5% cream, children, F-VASI75 wk 24 (NCT06804811) | 12.8% (3–34) | 1.9% | 24.0% (6–57) | 2.8% |
| Ritlecitinib 50 mg, F-VASI75 wk 24 (Tranquillo) | 8.0% (2–25) | 1.9% | 16.6% (3–49) | 2.9% |
| Ritlecitinib 50 mg, T-VASI50 wk 24 (Tranquillo) | 7.9% (2–23) | 3.7% | 5.0% (1–18) | 6.9% |
| Ritlecitinib 50 mg, F-VASI75 wk 52 (Tranquillo 2) | 22.7% (7–51) | 5.6% | 45.8% (14–84) | 9.5% |
| Ritlecitinib 50 mg, T-VASI50 wk 52 (Tranquillo 2) | 14.4% (4–38) | 6.3% | 11.2% (2–41) | 15.5% |

Every record carries its public-results search (`public_results_check`). None of these targets' numbers were public at sealing. Pfizer has said that both ritlecitinib doses beat placebo at week 52 and that stabilization appeared from week 24.

## Post-freeze note (written after sealing; the sealed files are unchanged)

- **The two models disagree most on topical ruxolitinib in children:** about 13% vs 24% F-VASI75 at week 24. In adults and adolescents (TRuE-V) it was about 30%, with vehicle at about 7%.
- **v0.4's low topical forecasts may be an over-correction.** Oral placebo and topical vehicle share one baseline in the model, so the very low placebo rates in the oral phase 3 trials (2–3% at week 52) pull every new trial down, topical included. A route-specific baseline would address this, but it would be a new model change and needs its own pre-registration.
- **The pediatric trials will discriminate.** A result near 25–30% favours v0.2; near 10–15% favours v0.4.

## Leave one oral programme out (pre-registration L: report only, not first-look)

Each oral phase 3 programme is held out and predicted as new phase 3 trials from the other programme's toplines (`lopo.json`, all fits converged).

| Held out | Pair | Observed active / placebo | v0.4 active (80%) | v0.2 active (sealed) |
|---|---|---|---|---|
| Upadacitinib | Viti-Up 1 F-VASI75 wk 48 | 25.2% / 5.9% | 22.0% (3–63) | 37.9% |
| Upadacitinib | Viti-Up 1 T-VASI50 wk 48 | 19.4% / 5.9% | 23.9% (3–69) | 15.1% |
| Upadacitinib | Viti-Up 2 F-VASI75 wk 48 | 23.4% / 6.9% | 22.0% (3–63) | 37.9% |
| Upadacitinib | Viti-Up 2 T-VASI50 wk 48 | 21.5% / 5.9% | 23.9% (3–69) | 15.1% |
| Ritlecitinib | Tranquillo 2 100 mg F-VASI75 wk 52 | 21.9% / 2.4% | 46.8% (13–85) | 56.0% |
| Ritlecitinib | Tranquillo 2 100 mg T-VASI50 wk 52 | 13.0% / 2.4% | 19.5% (4–53) | 15.0% |
| Ritlecitinib | Tranquillo 50 mg F-VASI75 wk 52 | 12.5% / 2.5% | 35.8% (9–76) | (no sealed draws) |
| Ritlecitinib | Tranquillo 50 mg T-VASI50 wk 52 | 9.0% / 2.0% | 15.6% (3–45) | (no sealed draws) |

**Summed log score on the 6 pairs with v0.2 draws:** v0.4 −49.2, v0.2 −54.1.

What this shows:
- The phase 3 shift learned from one oral programme largely transfers to another. Upadacitinib predicted from ritlecitinib is close on F-VASI75 (22% vs 23–25%).
- The reverse direction is still too high (ritlecitinib F-VASI75: 36–47% vs 12.5–22%).
- This is not first-look, because the people designing v0.4 had seen these numbers. The prospective comparison above is the real test.
