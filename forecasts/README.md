# Forecasts

Sealed forecasts of unreported JAK-inhibitor trials. Each `.json` carries a SHA-256 of its content; predictive draws (`.npz`) are hash-sealed inside it. `vitiligo discover check-forecasts forecasts` re-verifies every seal and scores the forecasts against ClinicalTrials.gov results. A weekly workflow runs it, together with `vitiligo discover watch`, which ranks pending results by how much they would tell us and lists new papers, trials and SEC filings.

| Folder | Contents |
|---|---|
| [`2026-10-14-tranquillo/`](2026-10-14-tranquillo/README.md) | v0.2, ritlecitinib Tranquillo (4); not prospective |
| [`2026-10-14-auto/`](2026-10-14-auto/README.md) | v0.2, every other unreported trial the registry describes well enough (11) |
| [`TOPLINE-CHECK-2026-10-14.md`](TOPLINE-CHECK-2026-10-14.md) | Which forecasts were really prospective, and how the others scored against public toplines |
| [`v0.3/`](v0.3/README.md) | Pre-registered evaluation of model v0.3 (not adopted) |
| [`v0.4/`](v0.4/README.md), [`v0.5/`](v0.5/README.md) | Challenger models, sealed for the same 7 targets as v0.2 |
| [`povorcitinib-phase3/`](povorcitinib-phase3/README.md) | Out-of-sample check of v0.2, v0.4 and v0.5 against povorcitinib's phase 3 F-VASI75 (post-hoc), and sealed T-VASI50 forecasts |
| [`voi/`](voi/README.md) | Value-of-information engine: pre-registered gate (passed narrowly) and how much each pending result can tell |

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

**Sealed with the direction public** (2026-10-21; [details](povorcitinib-phase3/README.md)). Povorcitinib 30 mg, T-VASI50 at week 52, STOP-V1 and STOP-V2 (same forecast for both):

| Target | v0.2 (default) | v0.4 | v0.5 |
|---|---|---|---|
| Povorcitinib 30 mg, T-VASI50 wk 52 | 16.7% (3–52) / 15.7% | 21.5% (5–54) / 6.3% | 19.8% (4–50) / 5.1% |

**Rule** (pre-registered): once at least 4 targets that every compared model has scored have resolved, the model with the highest summed log score becomes the default.

**How much one result can tell us** ([`voi/discrimination.json`](voi/discrimination.json)): little. The models' medians differ, but their intervals overlap, so no single target is decisive. The most informative, Tranquillo 2's T-VASI50, carries 0.30 of a possible 1.10 nats about which model is right; each pediatric trial carries about 0.09. The comparison will take several results.

## Reproducibility

The 2026-10-14 forecasts were sealed before their code was committed. Refitting them with the committed code ([`scripts/model/reproduce_sealed.py`](../scripts/model/reproduce_sealed.py), [`reproducibility-2026-10-21.json`](reproducibility-2026-10-21.json)) gives the same data hashes and these differences:

| Model | Targets | Largest shift of a median | Largest shift of a 10% or 90% point |
|---|---|---|---|
| v0.2 | 11 | 0.6 points | 1.4 points |
| v0.4 | 7 | 0.4 points | 1.2 points |
| v0.5 | 7 | none | none |

v0.5 was sealed last, on the code that was committed; v0.2 and v0.4 were sealed on earlier versions of it. The differences are far smaller than the forecasts' intervals, so no sealed forecast changes meaning. Since 2026-10-21, sealing records the git commit and refuses to run while the model code has uncommitted changes.
