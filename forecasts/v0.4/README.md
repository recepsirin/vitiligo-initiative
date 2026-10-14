# v0.4 challenger (sealed 2026-10-14)

v0.3's structure fitted **with** the public phase 3 toplines ([pre-registration](../../docs/model-v0.4-preregistration.md)). It has sealed forecasts for the same 7 targets as v0.2; the numbers are in the [scoreboard](../README.md#scoreboard). Each record carries its public-results search.

## Post-freeze note (written after sealing; the sealed files are unchanged)

- **v0.4's forecasts for ruxolitinib cream in children (about 13% F-VASI75) may be an over-correction:** adults and adolescents reached about 30%, with vehicle near 7%. Oral placebo and topical vehicle share one baseline in the model, so the very low placebo rates in the oral phase 3 trials (2–3% at week 52) pull every new trial down, topical included. v0.5 tests a route-specific baseline.

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
