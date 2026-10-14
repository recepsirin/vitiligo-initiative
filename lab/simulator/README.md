# Repigmentation simulator (trial run)

A mechanistic, patient-level model of repigmentation under JAK inhibition, found by program search and judged against the current scenario model on a locked exam. Everything is pre-registered in [`PREREGISTRATION.md`](PREREGISTRATION.md) (hash in `results/preregistration.sha256`).

**Status: stopped (2026-10-14).** The selected program beat the benchmark on the search data but failed the locked exam. Under the pre-registered rule, this attempt ends here.

## Result

79 programs were evaluated (`results/programs.jsonl`), including 3 proposed in-session. The selection (program #68: free cut-points, onset lag, face/body-specific spread and non-responder fraction) was sealed in `results/selection.json` before the exam ran once (`results/exam.json`).

| | Simulator #68 | Benchmark (scenario model v0.2) |
|---|---|---|
| Search score: held-out trials, weeks ≤ 24 (nats per arm-week) | **−3.53** | −3.61 |
| Exam log score: 17 arm-weeks after week 24 (sum) | −170.6 | **−124.0** |
| Exam 80% interval coverage | 0.56 | **0.80** |
| Exam mean signed error | −13.8 points | +6.9 points |

| Criterion | Result |
|---|---|
| 1. Exam log score beats the benchmark | **Failed** |
| 2. Exam coverage ≥ 0.70 | **Failed** |
| 3. Search score within 0.05 of the benchmark | Passed |

## Why it failed (exploratory, after the exam)

- **A false ceiling.** Fitted on weeks ≤ 24, the program put 26% of patients' facial vitiligo beyond reach. That caps F-VASI25 at about 73%; at week 52, 83–90% responded. Patients who are slow by week 24 look like non-responders. The long-term extension data (still improving at week 104) say the same.
- **Over-confidence.** With no arm-level variation and a Laplace approximation, the 80% intervals were about ±5 points, while the misses were 10–15. The benchmark is biased upward (TRuE-V F-VASI75 at week 52: 78–79% predicted vs 48–53% observed), but its wide intervals kept its log score higher.
- **One thing it did better:** its means for the phase 3 TRuE-V arms at week 52 were closer than the benchmark's (F-VASI75: 58–60% vs 78–79%, observed 48–53%). That alone is not a win under the pre-registered scoring, and it is reported for the record only.

## What this means

- A search score on 6 held-out trials up to week 24 was not enough to pick a model that extrapolates. The locked exam caught it, which is what it was for.
- **The exam rows are now spent.** Any new attempt needs a new pre-registration and a new locked exam. The natural one is prospective, but only 3 of the 15 sealed forecasts are truly prospective ([topline check](../../forecasts/TOPLINE-CHECK-2026-10-14.md)), so new trials will have to supply it.
- A future attempt would model slow responders as a rate distribution rather than a hard cap, include arm-level variation, and use full Bayesian uncertainty.

## Layout

| Path | Role |
|---|---|
| `data/arms-snapshot.json` | Hash-sealed arm table snapshot (the only data source) |
| `vsim/data.py` | Search set (weeks ≤ 24) and exam set, selected exactly as the benchmark selects them |
| `vsim/program.py` | Programs: closed-form responder probabilities, marginal likelihood, Laplace fit, prediction |
| `vsim/score.py` | One metric for every model: log predictive probability, interval coverage, bias |
| `vsim/benchmark.py` | The current scenario model on the same splits |
| `vsim/search.py` | Held-out-trial search score and the evolution loop; every program goes to `results/programs.jsonl` |
| `vsim/exam.py` | Sealed selection, then the locked exam |
| `tests/` | Closed form vs brute-force patient simulation, integration accuracy, parameter recovery |

## Run

From this folder, with the repository's virtualenv (needs the `[model]` extra):

```bash
python -m pytest tests
python -m vsim.benchmark       # ~45 min (MCMC)
python -m vsim.search          # evolution; resumes from the log
python -m vsim.exam select     # seals the selection (once)
python -m vsim.exam run        # locked exam and decision
```
