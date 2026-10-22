# Ranking pending evidence by value of information: pre-registration

Written 2026-10-22, before any value in it was computed. The SHA-256 of this file is recorded in `forecasts/voi-ranking-preregistration.sha256`.

## Why

The weekly watch ranks pending results only by how well they would separate the sealed models, and only for targets those models have forecast. This plan ranks all pending randomized evidence by how much it is expected to move the answers we care about, using the engine that passed its gate ([`voi-preregistration.md`](voi-preregistration.md)). The ranking then becomes a prospective test of that engine: each result, once public, shows whether its predicted value was right.

## Base model and questions

- **Base model B:** v0.3 structure at `target_accept = 0.995`, fitted on the v0.4 data (`model_inputs_v03(with_toplines=True)`). These are the same data as the sealed v0.4 records: data hashes `48a62f5f4f62` (F-VASI) and `249569d81638` (T-VASI). The gate validated the engine on this structure (its M0 was v0.3 fitted on registry data only); B adds the curated papers and phase 3 toplines.
- **Questions:** the gate's questions, unchanged. The expected responder rate in a new phase 3 trial of ritlecitinib 50 mg QD at week 52 (`Q_oral`) and of ruxolitinib 1.5% cream BID at week 24 (`Q_topical`), as F-VASI75 in the F-VASI model and T-VASI50 in the T-VASI model.
- **Value of an item:** its expected variance reduction (EVR) of `Q_oral + Q_topical`, in each instrument's model. 1,000 simulated outcomes, seed 1; 64 shared replicates of new-trial effects; 32 replicates averaged into each question. EVR of `Q_oral` alone is reported too.

## Items

**Which trials.** JAK-family vitiligo trials in the ClinicalTrials.gov snapshot of 2026-10-22 (`forecasts/voi/ranking/registry-2026-10-22.json`, 42 records). A trial qualifies if it:
- has no posted results and is not terminated, withdrawn, suspended or of unknown status;
- is randomized, with a placebo or vehicle arm;
- has at least one active monotherapy arm whose drug is identified. For a drug the base model has data for, the daily dose must also be known. For a drug it has no data for, the dose does not enter its predictions, so it may be undisclosed.

**Which results.** For each qualifying trial, the item holds:
- one result per randomized arm and instrument (F-VASI75 or T-VASI50);
- at the week of the trial's primary VASI responder endpoint;
- only where the registry states that endpoint at that week (not a range such as "up to 48 weeks"), and the placebo arm is still on placebo then;
- minus arm-weeks already in B's data.

Why one week per arm, and only these thresholds:
- **One week.** The model treats different weeks of one arm as independent observations, so counting several would inflate a trial's value merely for reporting more often.
- **Two thresholds.** F-VASI75 and T-VASI50 are the questions' endpoints, so every item is valued on them.

**Arm sizes.** Registered enrolment split equally over the randomized arms, unless a public source gives them.

**Simulation.**
- Arms of a new trial share its baseline, trial effect, phase 3 shift, drug effect and time course, and get independent arm deviations (`predict_trial_draws`).
- Arms of a trial already in B's data use its fitted effects.
- An item is phase 3 if the registry says so.

The items, derived by these rules:

| # | Trial | Arms (daily dose, size) | Week | Judgement calls |
|---|---|---|---|---|
| 1 | NCT06113445, STOP-V1, phase 3 | povorcitinib 30 mg (222), placebo (222) | 52 | "Dose A" is 30 mg QD (Incyte, 2026-04-28); 1:1 (EU CTIS); 222 per arm reproduces the published percentages. **F-VASI75 outcome already public** |
| 2 | NCT06113471, STOP-V2, phase 3 | povorcitinib 30 mg (222), placebo (222) | 52 | As item 1 |
| 3 | NCT07865312, povorcitinib, China, phase 3 | povorcitinib 30 mg (87), placebo (87) | 52 | |
| 4 | NCT06548360, ruxolitinib cream, children, phase 3 | 1.5% BID (90), vehicle (90) | 24 | |
| 5 | NCT06804811, ruxolitinib cream, children, phase 3 | 0.75% BID (83), 1.5% BID (83), vehicle (84) | 24 | |
| 6 | NCT06072183, Tranquillo 2, phase 3 | ritlecitinib 50 mg (206) | 52 | Week 52 of 100 mg and placebo is already in B, so the item is the 50 mg arm alone, in a trial B has fitted. Size as in `forecasts/voi/discrimination.json` |
| 7 | NCT07108283, zasocitinib, phase 2 | 3 doses (40 each), placebo groups 1 and 2 pooled (80) | 24 | Doses undisclosed; no data on the drug, so the three arms differ only by their arm deviations. The placebo groups switch to drug after week 24 |

All seven register both F-VASI75 and T-VASI50 at the stated week.

**Not items:**
- **Primary week already in B:** NCT05583526 (Tranquillo, week 52); NCT06118411 (Viti-Up, week 48).
- **No placebo-controlled VASI responder result at the primary week:**
  - NCT06327321 (deucravacitinib): T-VASI50 only at week 48, after the 24-week placebo period;
  - NCT07251595 (ivarmacitinib): responder endpoints only "up to 48 weeks";
  - NCT06719024, NCT04103060, NCT05872477, NCT04822584, NCT07554222: no VASI responder endpoint parsed from the registry.
- **No randomized placebo arm:** NCT06163326, the single-arm studies, and the active-comparator studies.

## What is reported

For each item and instrument:
- the EVR of `Q_oral + Q_topical` and of `Q_oral`;
- the prior variance, and the mean and minimum effective sample size of the reweighting.

Items are ranked by F-VASI EVR, and T-VASI is reported beside it. T-VASI values are **upper bounds** (the gate's finding).

## Prospective test

The test covers items whose outcomes were not public on 2026-10-22: every item-instrument pair except the F-VASI75 of items 1 and 2.

**Scoring each item.** When an item's results become public and are curated, B is refitted with them. Its realized shift of `Q_oral + Q_topical` is then compared with the predicted EVR (`shift² / EVR`).

**The criterion.** Once at least 5 item-instrument pairs have resolved, the engine **passes prospectively** if the Spearman correlation between EVR and shift² is at least 0.5. It is reported again at every further result.

## Disclosure

- **What the author knew.**
  - The STOP-V F-VASI75 result. This is why the F-VASI75 of items 1 and 2 is excluded from the prospective test.
  - The pattern that phase 3 oral toplines moved the models most (the gate's G1). The test therefore asks whether values track realized shifts across items, not whether phase 3 items rank first.
  - No EVR for these items had been computed.
- **What the item table uses.** It was derived from the registry snapshot and the sources named above, before any fit of B was run for this plan.

## Amendments

None yet.
