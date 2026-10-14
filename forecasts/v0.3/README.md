# Scenario model v0.3: evaluation result (2026-10-14)

Pre-registration: [`docs/model-v0.3-preregistration.md`](../../docs/model-v0.3-preregistration.md), sealed before any fit. One amendment, made before any score was computed: `target_accept = 0.995` for every fit. **Decision: not adopted** (`decision.json`). v0.2 stays the default.

| Criterion | Result |
|---|---|
| (a) E1: beats v0.2 on the held-out phase 3 toplines (6 pairs, summed log score) | **Failed:** −54.29 vs −54.13 |
| (b) Leave-one-trial-out 80% coverage ≥ 0.75 | Passed: F-VASI 0.98, T-VASI 0.95 |
| (c) Every fit converged | Passed |

| Back-test | v0.2 | v0.3 |
|---|---|---|
| F-VASI leave-one-trial-out: 80% coverage / mean error | 0.93 / 5.1 pp | 0.98 / 6.7 pp |
| T-VASI leave-one-trial-out | 0.95 / 4.3 pp | 0.95 / 5.4 pp |
| F-VASI weeks ≤ 24 → later | 0.69 / 10.6 pp | 0.71 / 9.9 pp |
| T-VASI weeks ≤ 24 → later | 0.86 / 9.1 pp | 0.94 / 10.8 pp |

v0.3 has slightly more data (curated paper rows), so the point counts differ a little from v0.2's.

## Why it failed

Fitted without the phase 3 toplines, v0.3 had no phase 3 oral data. Its oral phase 3 shift stayed at the prior (0), so its median forecasts were as high as v0.2's (for example 59% vs 56% F-VASI75 for ritlecitinib 100 mg; observed 21.9%). The trial-by-treatment term only widened the intervals (80%: 10–97%), which costs log score wherever the forecast is far off. **Structure cannot learn a bias that the training data does not contain.**

The pre-registered follow-up is the v0.4 challenger ([`../v0.4/`](../v0.4/README.md)): the same structure trained on the toplines, tested prospectively against v0.2.

Files: `e1.json` (per-pair predictions and scores), `backtest-v03-*.json`, `decision.json`.
