# v0.5 challenger (sealed 2026-10-14)

v0.4 with a **separate baseline mean per route**, so oral placebo and topical vehicle trials no longer share one ([pre-registration](../../docs/model-v0.5-preregistration.md)). It has sealed forecasts for the same 7 targets; the numbers are in the [scoreboard](../README.md#scoreboard).

## What the change did (post-freeze note; the sealed files are unchanged)

- **As intended,** separating the baselines lifted the topical forecasts back up: pediatric ruxolitinib to 20% (v0.4 13%, v0.2 24%), and vehicle to 4.2%.
- **Oral forecasts went lower still:** ritlecitinib at week 24, 5.4% vs placebo 1.2%. They now follow the low oral phase 3 placebo rates.

## Leave one oral programme out (report only, not first-look)

Summed log score on the 6 pairs with v0.2 draws (`lopo.json`, all fits converged): **v0.5 −49.18, v0.4 −49.23, v0.2 −54.13.** On held-out oral phase 3 programmes, v0.5 and v0.4 are equivalent. The per-route baseline mainly changes topical forecasts, which these pairs do not test; only the pediatric ruxolitinib trials will.
