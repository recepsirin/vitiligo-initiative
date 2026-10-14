# v0.5 challenger forecasts (sealed 2026-10-14)

Pre-registration: [`docs/model-v0.5-preregistration.md`](../../docs/model-v0.5-preregistration.md). v0.5 is v0.4 with a **separate baseline mean per route**: oral placebo trials and topical vehicle trials no longer share one. v0.2 remains the default. All three models have sealed forecasts for the same targets, and `vitiligo discover check-forecasts` compares them as results post.

| Target | v0.2 active (80%) / placebo | v0.4 active (80%) / placebo | v0.5 active (80%) / placebo |
|---|---|---|---|
| Ruxolitinib 1.5% cream, children, F-VASI75 wk 24 (NCT06548360) | 24.0% (6–57) / 2.8% | 12.8% (3–34) / 1.9% | 20.3% (6–44) / 4.2% |
| Ruxolitinib 0.75% cream, children, F-VASI75 wk 24 (NCT06804811) | 20.3% (5–53) / 2.8% | 9.8% (2–29) / 1.9% | 16.0% (5–38) / 4.2% |
| Ruxolitinib 1.5% cream, children, F-VASI75 wk 24 (NCT06804811) | 24.0% (6–57) / 2.8% | 12.8% (3–34) / 1.9% | 20.3% (6–44) / 4.2% |
| Ritlecitinib 50 mg, F-VASI75 wk 24 (Tranquillo) | 16.6% (3–49) / 2.9% | 8.0% (2–25) / 1.9% | 5.4% (1–17) / 1.2% |
| Ritlecitinib 50 mg, T-VASI50 wk 24 (Tranquillo) | 5.0% (1–18) / 6.9% | 7.9% (2–23) / 3.7% | 6.7% (1–20) / 2.9% |
| Ritlecitinib 50 mg, F-VASI75 wk 52 (Tranquillo 2) | 45.8% (14–84) / 9.5% | 22.7% (7–51) / 5.6% | 18.1% (6–42) / 4.0% |
| Ritlecitinib 50 mg, T-VASI50 wk 52 (Tranquillo 2) | 11.2% (2–41) / 15.5% | 14.4% (4–38) / 6.3% | 12.4% (3–35) / 5.1% |

v0.2's two Tranquillo week-24 forecasts have no sealed draws, so they are shown but not scored.

## What the change did (post-freeze note; the sealed files are unchanged)

- **As intended,** separating the baselines lifted the topical forecasts back up: pediatric ruxolitinib to 20% (v0.4 13%, v0.2 24%), and vehicle to 4.2%.
- **Oral forecasts went lower still:** ritlecitinib at week 24, 5.4% vs placebo 1.2%. They now follow the low oral phase 3 placebo rates.
- **The pediatric trials separate the three models.** If they come in near 25–30% F-VASI75, v0.2 is closest; near 15–20%, v0.5; near 10%, v0.4.

## Leave one oral programme out (report only, not first-look)

Summed log score on the 6 pairs with v0.2 draws (`lopo.json`, all fits converged): **v0.5 −49.18, v0.4 −49.23, v0.2 −54.13.** On held-out oral phase 3 programmes, v0.5 and v0.4 are equivalent. The per-route baseline mainly changes topical forecasts, which these pairs do not test; only the pediatric ruxolitinib trials will.
