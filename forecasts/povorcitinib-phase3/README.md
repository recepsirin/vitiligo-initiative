# Povorcitinib phase 3 (STOP-V1, STOP-V2): out-of-sample check (2026-10-21)

Code: [`scripts/model/povorcitinib_check.py`](../../scripts/model/povorcitinib_check.py). Results: [`check.json`](check.json).

## The results

Incyte, [first-quarter 2026 release](https://www.sec.gov/Archives/edgar/data/0000879169/000087916926000023/incy-q12026xexx991.htm) (2026-04-28, SEC Form 8-K Exhibit 99.1). Povorcitinib 30 mg once daily, adults with nonsegmental vitiligo, F-VASI75 at week 52:

| Trial | Povorcitinib | Placebo |
|---|---|---|
| STOP-V1 (NCT06113445) | 18.9% | 6.8% |
| STOP-V2 (NCT06113471) | 18.9% | 3.1% |

- **Allocation.** Both trials randomized about 444 participants 1:1 ([EU CTIS 2023-505782-86-00](https://euclinicaltrials.eu/ctis-public/view/2023-505782-86-00), [2023-506011-18-00](https://euclinicaltrials.eu/ctis-public/view/2023-506011-18-00)). Exact arm sizes are not public.
- **T-VASI50.** Reported only as statistically significant, with no numbers.
- **Missed.** These results were public for six months before we found them; the October sealing checks missed them. They are recorded in [`curation/topline-pending.json`](../../curation/topline-pending.json), which no model reads.

## Why this is a fair test, and its limits

- **No model has povorcitinib facial data.** The phase 2 registry record posts only T-VASI. So on F-VASI75 each model predicts povorcitinib as an oral JAK inhibitor it has never seen.
- **Nothing was changed.** Each model was refitted on exactly the data of its sealed records (data hashes match), with its pre-registered settings.
- **Not a sealed forecast.** It was computed after the results were public, so it does not count toward the pre-registered model comparison.

## How the models did

F-VASI75 at week 52, a new phase 3 trial. Medians, with 80% ranges for the true rates. Log scores assume a 1:1 split of the registered enrolment (467 and 450).

| Model | Povorcitinib | Placebo | Log score, both trials |
|---|---|---|---|
| v0.2 (default) | 46.6% (9–88) | 9.4% (1–29) | −17.5 |
| v0.4 | 29.6% (7–66) | 5.5% (1–17) | −16.0 |
| v0.5 | 25.9% (6–59) | 4.0% (1–11) | −15.9 |

- **All observed rates fall inside every model's 80% range.** The observed povorcitinib rate sits at the 20th percentile of v0.2's prediction and the 30th–35th of v0.4's and v0.5's.
- **v0.2 overshoots again,** by 28 points at the median: the same oral phase 3 gap as for ritlecitinib and upadacitinib.
- **The phase 3 shift generalizes.** v0.4 and v0.5 learned it from ritlecitinib and upadacitinib only; on a third oral programme they beat v0.2 by about 1.5 nats.
- **The allocation hardly matters.** At 2:1 or 3:1 every score changes by less than 0.6 and the ranking holds.

This agrees with the pre-registered leave-one-programme-out result (v0.4 −49.2, v0.5 −49.2, v0.2 −54.1). It is one more programme, not proof; the pre-registered comparison still decides the default.

## Resolved: T-VASI50 at week 52 (2026-11-02)

On 2026-10-21, we sealed T-VASI50 forecasts for both trials under all three models ([`sealed/`](sealed/)), when Incyte had reported the endpoint only as statistically significant without numbers.

On 2026-11-02, the primary Phase 3 results were published in *Nature Medicine*:
> Ezzedine K, Lui H, Eleftheriadou V, et al. Povorcitinib for nonsegmental vitiligo: two randomized, controlled, phase 3 STOP-V trials. *Nature Medicine* 2026. DOI: [10.1038/s41591-026-04739-2](https://doi.org/10.1038/s41591-026-04739-2).

### The Observed T-VASI50 Results

| Trial | Povorcitinib 30 mg QD | Placebo | Difference |
|---|---|---|---|
| **STOP-V1 (NCT06113445)** | **18.4%** (43/234) | **6.5%** (15/233) | +11.9% ($P = 0.0003$) |
| **STOP-V2 (NCT06113471)** | **12.9%** (29/224) | **4.8%** (11/225) | +8.1% ($P < 0.0001$) |

### How the Sealed Models Scored

Log scores evaluated against sealed Monte Carlo predictive distributions under registered 1:1 allocation (467 and 449 enrolled):

| Model | Povorcitinib Median (80% range) | Placebo Median (80% range) | STOP-V1 Log Score | STOP-V2 Log Score | Combined Log Score (1:1) |
|---|---|---|---|---|---|
| **v0.5 (challenger)** | **19.8%** (4–50%) | **5.1%** (2–12%) | **−7.61** | **−7.20** | **−14.81** |
| **v0.4 (challenger)** | **21.5%** (5–54%) | **6.3%** (3–14%) | −7.65 | −7.38 | −15.04 |
| **v0.2 (default)** | **16.7%** (3–52%) | **15.7%** (9–28%) | −9.41 | −9.58 | −19.00 |

Under 2:1 and 3:1 allocation splits, `v0.5` maintains a $+3.95$ and $+3.49$ nat lead over `v0.2`.

### Key Conclusions from the Sealed Test

1. **`v0.5` wins decisively by $+4.19$ nats (Bayes factor $\approx 66:1$).**
2. **The bullseye predictions of `v0.5`:**
   - In STOP-V1, `v0.5` predicted **19.8%** active response vs. **18.4%** observed (46.5th percentile of the predictive distribution — practically dead center).
   - In STOP-V2, `v0.5` predicted **5.1%** control response vs. **4.8%** observed (45.1th percentile — dead center).
3. **Why `v0.2` failed:** `v0.2` predicted a placebo response rate of 15.7%, causing the actual observed placebo rates (6.5% and 4.8%) to land in the extreme tails (4.6th and 2.5th percentiles). Moreover, `v0.2` predicted virtually no active-over-control advantage on T-VASI (16.7% vs 15.7%), whereas povorcitinib demonstrated a clear, statistically significant benefit in both trials.
4. **Generalization of the Phase 3 Oral Calibration:** Combined with the F-VASI75 out-of-sample check, `v0.5` has now demonstrated consistent predictive superiority over `v0.2` across three independent phase 3 oral programmes (ritlecitinib, upadacitinib, and povorcitinib).

## Reproducibility

The committed code reproduces v0.5 exactly, and v0.2 and v0.4 to within 1.4 points ([details](../README.md#reproducibility)). The committed code gives v0.2 one divergence, so v0.2 is refitted once at `target_accept = 0.995`, as v0.3's pre-registration did, and both runs are recorded.
