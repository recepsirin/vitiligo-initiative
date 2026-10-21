# Topline check of the sealed forecasts (2026-10-14)

Written after sealing; the sealed files are unchanged.

## Which forecasts are prospective

All 15 forecasts were sealed on 2026-10-14 without consulting results. But for 12 of them, topline results had **already been made public** before that date. Those 12 are therefore **not prospective**: we did not look, but no outsider can verify that.

| Trial | Forecasts | Public before sealing | Status |
|---|---|---|---|
| Tranquillo, NCT05583526 (ritlecitinib 50 mg) | 4 | Direction: Pfizer, 2026-07-30. Week-52 numbers: EADV 2026 LB-161, 2026-10-03 | **Not prospective** |
| Tranquillo 2, NCT06072183 (ritlecitinib 100 / 50 mg) | 4 | Same; numbers for 100 mg only | **Not prospective** |
| Viti-Up, NCT06118411 (upadacitinib 15 mg) | 4 | AbbVie topline, 2025-10-29 | **Not prospective** |
| NCT06548360, NCT06804811 (ruxolitinib cream, children) | 3 | Nothing found | **Prospective** |

**Lesson:** registry status alone does not tell whether results are public. Before any future sealing, also search sponsor press releases and conference abstracts, and record that search in the sealed record.

## Retrospective scoring against the public numbers

Week 52 (Tranquillo trials) or 48 (Viti-Up), active arm vs placebo. "80% range" is the forecast's range for the observed rate (with sampling noise for the arm's size where sealed draws exist). "P(beats placebo)" is the forecast probability that the drug beats placebo.

| Forecast | Observed active / placebo | Forecast median active / placebo | 80% range (active) | In range | P(beats placebo) | Direction |
|---|---|---|---|---|---|---|
| Tranquillo 50 mg, F-VASI75 | 12.5% / 2.5% | 45.8% / 9.5% | 14–84% | **No** | 0.99 | Right |
| Tranquillo 50 mg, T-VASI50 | 9.0% / 2.0% | 11.2% / 15.5% | 2–41% | Yes | 0.37 | **Wrong** |
| Tranquillo 2 100 mg, F-VASI75 | 21.9% / 2.4% | 56.0% / 9.5% | 19–91% | Yes | 0.99 | Right |
| Tranquillo 2 100 mg, T-VASI50 | 13.0% / 2.4% | 15.0% / 15.5% | 2–53% | Yes | 0.49 | **Wrong** |
| Viti-Up 1, F-VASI75 | 25.2% / 5.9% | 37.9% / 8.6% | 9–77% | Yes | 0.98 | Right |
| Viti-Up 1, T-VASI50 | 19.4% / 5.9% | 15.1% / 14.5% | 1–61% | Yes | 0.52 | Right |
| Viti-Up 2, F-VASI75 | 23.4% / 6.9% | 37.9% / 8.6% | 9–77% | Yes | 0.98 | Right |
| Viti-Up 2, T-VASI50 | 21.5% / 5.9% | 15.1% / 14.5% | 1–61% | Yes | 0.52 | Right |

Observed rates come from secondary reports of the EADV 2026 late-breaker (HCPLive, 2026-10-03) and AbbVie's press release (2025-10-29). They will be re-scored against posted ClinicalTrials.gov results when those appear (`vitiligo discover resolve`).

## What this shows

- **Wide ranges, weak information.** 7 of 8 observed rates fall inside the 80% ranges, but those ranges often span 10–80%. The forecasts were honest about their uncertainty, not sharp.
- **Facial response biased high.** F-VASI75 medians were 13–34 points above the observed rates, the same week-52 over-prediction found in the back-tests and the simulator exam.
- **Placebo biased high.** 9–15% forecast against 2–7% observed. Placebo data end at week 24, and the later placebo response is extrapolated.
- **Whole-body direction missed for ritlecitinib.** The model gave the drug a 37–49% chance of beating placebo on T-VASI50; it beat placebo in both trials. The post-freeze assessment had flagged this: the model cannot represent late onset for oral drugs.
- The only forecasts still able to test the model prospectively are the three pediatric ruxolitinib forecasts.

Sources: [Pfizer topline, 2026-07-30](https://www.biospace.com/press-releases/pfizer-announces-positive-topline-phase-3-results-for-litfulo-in-patients-with-nonsegmental-vitiligo) · [EADV 2026 report, 2026-10-03](https://www.hcplive.com/view/phase-3-ritlecitinib-results-vitiligo-iltefat-hamzavi-md) · [AbbVie topline, 2025-10-29](https://news.abbvie.com/2025-10-29-AbbVie-Announces-Positive-Topline-Results-from-Phase-3-Pivotal-Studies-Evaluating-Upadacitinib-RINVOQ-R-in-Adults-and-Adolescents-with-Vitiligo)

## Addendum, 2026-10-21: povorcitinib

This search also missed povorcitinib's phase 3 toplines (STOP-V1 and STOP-V2, F-VASI75 at week 52), which Incyte published on 2026-04-28. No forecast had been sealed for these trials: the registry does not disclose the dose ("Dose A"), so automatic forecasting skipped them. The [povorcitinib check](povorcitinib-phase3/README.md) scores the models against them post hoc.
