# Forecasts

Sealed forecasts of unreported JAK-inhibitor trials. Each `.json` carries a SHA-256 of its content; predictive draws (`.npz`) are hash-sealed inside it. `vitiligo discover check-forecasts forecasts` re-verifies every seal and scores the forecasts against ClinicalTrials.gov results; a weekly workflow runs it.

| Folder | Contents |
|---|---|
| [`2026-10-14-tranquillo/`](2026-10-14-tranquillo/README.md) | v0.2, ritlecitinib Tranquillo (4); not prospective |
| [`2026-10-14-auto/`](2026-10-14-auto/README.md) | v0.2, every other unreported trial the registry describes well enough (11) |
| [`TOPLINE-CHECK-2026-10-14.md`](TOPLINE-CHECK-2026-10-14.md) | Which forecasts were really prospective, and how the others scored against public toplines |
| [`v0.3/`](v0.3/README.md) | Pre-registered evaluation of model v0.3 (not adopted) |
| [`v0.4/`](v0.4/README.md), [`v0.5/`](v0.5/README.md) | Challenger models, sealed for the same 7 targets as v0.2 |

## Scoreboard

The 7 targets whose results were not public at sealing. F-VASI75 unless noted; active arm, median with 80% interval, then placebo.

| Target | v0.2 (default) | v0.4 | v0.5 |
|---|---|---|---|
| Ruxolitinib 1.5% cream, children, wk 24 (NCT06548360) | 24.0% (6–57) / 2.8% | 12.8% (3–34) / 1.9% | 20.3% (6–44) / 4.2% |
| Ruxolitinib 0.75% cream, children, wk 24 (NCT06804811) | 20.3% (5–53) / 2.8% | 9.8% (2–29) / 1.9% | 16.0% (5–38) / 4.2% |
| Ruxolitinib 1.5% cream, children, wk 24 (NCT06804811) | 24.0% (6–57) / 2.8% | 12.8% (3–34) / 1.9% | 20.3% (6–44) / 4.2% |
| Ritlecitinib 50 mg, wk 24 (Tranquillo) | 16.6% (3–49) / 2.9%* | 8.0% (2–25) / 1.9% | 5.4% (1–17) / 1.2% |
| Ritlecitinib 50 mg, T-VASI50 wk 24 (Tranquillo) | 5.0% (1–18) / 6.9%* | 7.9% (2–23) / 3.7% | 6.7% (1–20) / 2.9% |
| Ritlecitinib 50 mg, wk 52 (Tranquillo 2) | 45.8% (14–84) / 9.5% | 22.7% (7–51) / 5.6% | 18.1% (6–42) / 4.0% |
| Ritlecitinib 50 mg, T-VASI50 wk 52 (Tranquillo 2) | 11.2% (2–41) / 15.5% | 14.4% (4–38) / 6.3% | 12.4% (3–35) / 5.1% |

\* Sealed without draws, so not scored.

**Rule** (pre-registered): once at least 4 targets that every compared model has scored have resolved, the model with the highest summed log score becomes the default. The pediatric trials separate the models most: near 25–30% favours v0.2, near 15–20% v0.5, near 10% v0.4.
