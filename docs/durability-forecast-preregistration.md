# Durability forecast 1, stopping an oral JAK inhibitor: pre-registration

Written 2026-10-23, before the forecast was computed. The SHA-256 of this file is recorded in `forecasts/durability-forecast-preregistration.sha256`. Background: [`durability/README.md`](durability/README.md).

## The claim being tested

**Does what happened when patients stopped ruxolitinib cream (TRuE-V) predict what happens when they stop oral ritlecitinib?** If it does, the topical evidence can guide decisions about stopping oral treatment until oral data exist. If it does not, it cannot.

## Target

**Tranquillo LTE** ([NCT06163326](https://clinicaltrials.gov/study/NCT06163326)), randomized withdrawal (design: registry and [PMC13280265](https://europepmc.org/article/PMC/PMC13280265)):
- **Who.** Patients who responded to ritlecitinib 50 mg QD at week 52 of Tranquillo (≥ F-VASI75 and/or ≥ T-VASI50).
- **Randomization.** 1:1 to continue 50 mg or switch to placebo, for 52 weeks.
- **Loss of response.** < F-VASI75 and < T-VASI50 at the same visit.
- **Status on 2026-10-23.** Not completed (primary completion estimated 2027-03); no results public.

**Forecast quantities** (true values for that randomized population):
- `S_w`: the probability of no loss of response through 52 weeks after switching to placebo;
- `S_c`: the same when continuing 50 mg;
- `HR`: the hazard ratio of loss, continuing vs stopping.

Hazards are taken as proportional, so `S_c = S_w ^ HR`.

## The forecast

Derived only from TRuE-V's posted results ([`truev-reference.json`](durability/data/truev-reference.json), from `scripts/durability/truev_reference.py`). Two analogs from TRuE-V bound the answer:

| | Analog | One-year retention after stopping | HR, continue vs stop |
|---|---|---|---|
| A | Loss of F-VASI90, which patients entered just above (median 195 days, constant hazard) | 0.274 | 0.316 (SE of log 0.332) |
| B | Relapse below F-VASI75, entered at ≥ F-VASI90, so with a buffer (Schoenfeld events, 14.9 of 56) | 0.734 | 0.422 (SE of log 0.435) |

Tranquillo LTE's responders enter at the thresholds they are judged against, like analog A. But a patient responding on both face and body must lose both to count as a loss, which pushes toward analog B. **A is weighted 2, B is weighted 1**, on the logit and log-hazard-ratio scales.

| Quantity | Distribution | Centre | Spread |
|---|---|---|---|
| `logit(S_w)` | Normal | (2·logit 0.274 + logit 0.734) / 3 | SD = √(b² + 0.5²). b puts the farther analog on the edge of the 80% interval, so both lie within it (b = distance to the farther analog / 1.2816); 0.5 is the added uncertainty of transfer from topical to oral |
| `log HR` | Normal | (2·log 0.316 + log 0.422) / 3 | SD = √(s² + 0.4²), where s = (2·0.332 + 0.435) / 3 (the analogs' weighted standard error) and 0.4 is transfer uncertainty |

- **Independence.** `S_w` and `HR` are independent; `S_c = S_w ^ HR`.
- **Sampling.** 20,000 draws, seed 20261023.
- **What is sealed.** The draws, saved as `.npz` with their hash, and their 10%, 50% and 90% quantiles.

## Scoring, when results are public

Results come from the registry, or else the primary publication.

1. **Primary: the hazard ratio** for loss of response, continuing 50 mg vs placebo (inverted if posted the other way).
   - **Only the randomized withdrawal counts.** That is, responders to 50 mg randomized to continue or stop. A hazard ratio pooled with the dose-up arms or the non-randomized placebo group is not used.
   - **Log score.** The posted estimate's density under the forecast, widened by its own sampling error: `log N(posted log HR; m, s² + SE²)`, with SE taken from the posted 95% CI.
   - **Benchmark.** An uninformed forecast, `log HR ~ N(0, 1)`, scored the same way.
   - **Criterion.** **The topical evidence transfers if the forecast's log score beats the benchmark's.**
2. **Secondary: one-year retention per arm** (Kaplan–Meier at week 52), if reported with a 95% CI. It is scored by the forecast's average density of the posted estimate (normal, SE from the CI), against a uniform benchmark on `S`.
3. **Reported:** whether each posted value falls inside the forecast's 80% interval.

**If no hazard ratio and no week-52 retention is reported,** the forecast stays unresolved. Response rates by visit are not substituted: they mix patients who entered on face, body or both, and they cannot be mapped onto loss of response without patient-level data.

## Disclosure

- **What the author knows of the oral data.** Tranquillo's week-52 toplines are public: ritlecitinib 50 mg F-VASI75 12.5%, T-VASI50 9.0%. They set the size of the randomized population, not the forecast.
- **What the author has seen.** TRuE-V's posted results, and the titles of two 2026 papers on its withdrawal (Br J Dermatol; J Am Acad Dermatol), but not their full text.
- **No other inputs.** No oral withdrawal data exist in the registry or in open-access papers as of 2026-10-23.
- **Judgements, stated in advance:**
  - the 2:1 weighting of the analogs;
  - the transfer standard deviations (0.5 on the logit scale and 0.4 on the log hazard ratio scale);
  - proportional hazards.
- **Not attempted:** "who keeps their response" needs patient-level data.

## Amendments

None yet.
