# Evidence ranking (2026-10-22)

Pre-registration: [`docs/voi-ranking-preregistration.md`](../../../docs/voi-ranking-preregistration.md), sealed and committed before any value was computed. Code: `python scripts/model/voi_core.py rank` (commit `97bbbdb`). Results: [`ranking-2026-10-22.json`](ranking-2026-10-22.json).

**What the numbers mean:** how much each pending result is expected to reduce the uncertainty in two questions, the expected responder rate in a new phase 3 trial of ritlecitinib 50 mg (oral) and of ruxolitinib 1.5% cream (topical). This is expected variance reduction of their sum, ×10⁻⁴.

**Scale:** the total uncertainty (prior variance) is 155 (F-VASI75 model) and 160 (T-VASI50 model).

## Result

| # | Pending result | F-VASI75 | F-VASI75, oral question only | T-VASI50 (upper bound) |
|---|---|---|---|---|
| 5 | Ruxolitinib cream in children, 0.75% and 1.5% (NCT06804811) | 16.8 | 2.3 | 25.0 |
| 1, 2 | STOP-V1, STOP-V2: povorcitinib 30 mg, each | 15.1 (outcome public) | 5.9 | 8.4 |
| 4 | Ruxolitinib cream in children, 1.5% (NCT06548360) | 13.5 | 2.0 | 21.3 |
| 3 | Povorcitinib 30 mg, China (NCT07865312) | 9.7 | 4.3 | 7.9 |
| 7 | Zasocitinib, 3 doses (NCT07108283) | 7.3 | 2.0 | 4.7 |
| 6 | Tranquillo 2, ritlecitinib 50 mg arm (NCT06072183) | 2.9 | 2.2 | 4.2 |

## Simulation noise (post hoc)

The values above come from one simulation seed, as pre-registered. Repeating them with five other seeds ([`monte-carlo-2026-10-22.json`](monte-carlo-2026-10-22.json); `voi_core.py rank-mc`) gives these ranges:

| # | F-VASI75, other seeds | T-VASI50, other seeds |
|---|---|---|
| 5 | 14.1–19.9 | 20.1–27.3 |
| 1, 2 | **9.4–12.8** | 7.2–10.0 |
| 4 | 12.5–16.2 | 19.8–23.8 |
| 3 | 9.4–10.8 | 7.0–9.1 |
| 7 | 6.0–8.2 | 4.3–4.8 |
| 6 | 2.7–4.1 | 4.0–4.8 |

- **STOP-V's pre-registered F-VASI75 value (15.1) is a high draw.** Some of its simulated outcomes are carried by very few posterior draws (minimum effective sample size about 3), which makes the estimate noisy.
- **What holds across all six seeds:**
  - on F-VASI75, items 5, 4 and 1–2 form a top group whose order is not settled. The China trial is close behind (its range overlaps STOP-V's), then zasocitinib; Tranquillo 2's 50 mg arm is last;
  - on T-VASI50, the pediatric trials lead clearly, ahead of STOP-V and the China trial.

The pre-registered values stand as the recorded result; this check only says which differences they can support.

## Reading it

- **For the oral question alone, STOP-V scores highest (5.9), then the China trial (4.3).** These are single-seed values; the noise check covered only the sum. STOP-V's F-VASI75 is already public but in no model yet, which supports fitting it once Incyte publishes the arm sizes ([standing item](../../watch-triage.md)).
- **The pediatric ruxolitinib trials are in the top group on F-VASI75 and lead on T-VASI50, mainly through the topical question.**
- **Tranquillo 2's 50 mg arm is worth little.** The model already has the trial's 100 mg and placebo arms at week 52.
- **Zasocitinib and other drugs without data** inform the questions only through what the drugs share as a class.

## Prospective test

Each result, once public, is curated into `resolved.json` (format of `curation/topline-results.json`, plus the `item` it resolves). `python scripts/model/voi_core.py rank-score` then refits the base model with it, measures how far the questions move, and applies the pre-registered criterion:
- **The criterion:** once 5 item-instrument pairs have resolved, the Spearman correlation between predicted value and squared realized shift must be at least 0.5.
- **Which pairs count:** 12. STOP-V's F-VASI75 is excluded; its outcome was public at sealing.
- **Status:** 0 resolved ([`prospective.json`](prospective.json)). The weekly watch marks news about these trials.
