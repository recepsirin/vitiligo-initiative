# Discovery loop

A system that keeps proposing claims about JAK-inhibitor response in vitiligo, tests each one on evidence it was not built from, records every result in a ledger, and learns which kinds of claims hold up. Endless generation also produces endless flukes, so the loop controls the false discovery rate.

The design follows AlphaEvolve (generate → evaluate → keep the best → learn). One part differs: AlphaEvolve's evaluator is exact and unlimited, while ours is held-out trial data, which is scarce and can be used only once.

## Guarantees

1. **Valid held-out evidence.** A claim about trial *T* comes from a model fitted without *T*. It is tested on *T* with a universal-inference mixture e-value, `e = mean_j L(θ_j) / sup_null L`. The θ_j are the held-out model's predictive draws in which the claim holds, so `E[e] ≤ 1` when the claim is false.
2. **Online FDR control (e-LOND).** Test *t* is a discovery if `e_t ≥ 1/α_t`, with `α_t = α · γ_t · (discoveries so far + 1)` and `γ_t = 6/(π² t²)`. This controls the false discovery rate at α = 0.10 under any dependence between tests, including tests on overlapping data.
3. **Evidence is spent once.** Each unit (two arms of one trial at one week) is tested at most once, ever. What to test on *T* is chosen without *T*'s data: the policy and the discovery count used for planning exclude *T*'s own history. New data creates new units.
4. **Testing must be worth it.** A claim is tested only if the held-out model believes it (probability ≥ 0.8) and predicts at least a 50% chance of a discovery. Abstaining is free. Units with the best chance go first, because earlier tests face a lower bar.

## Claim families

All three compare two independent arms against a linear null `p_x − ρ·p_y ≤ m`:

| Family | Arms | Claim |
|---|---|---|
| `superiority_margin` | active vs control | the active arm beats control by more than *m* |
| `regimen_contrast` | more vs less intensive regimen of one drug | the more intensive one wins by more than *m* |
| `dose_retention` | same pair | the less intensive one keeps more than ρ (50% or 75%) of the response rate |

- **More intensive** means the same drug, at least as high in daily dose, loading dose and phototherapy, and higher in at least one.
- **Retention, not "within 10 points".** Additive non-inferiority is nearly free to show when hardly anyone responds, and each such discovery would loosen later tests. A retained fraction needs real response rates to be shown.
- **No between-drug family.** No head-to-head trials are registered; cross-trial comparisons stay with the scenario model's forecasts.
- **Joint predictions.** The two arms of a pair share one draw of the trial baseline and drug effect, with independent arm deviations (`predict_pair_draws`).

## Results so far

| Run | Units | Tests | Discoveries |
|---|---|---|---|
| v0.1 (superiority only) | 64 | 4 | 4: ruxolitinib cream beats vehicle in both TRuE-V trials (F-VASI and T-VASI, week 24) |
| v1 (all three families) | 188 | 0 | — |

In v1 every unit abstained. A discovery at test 5 needs e ≥ 82, and the phase 2 dose-ranging arms (about 40–65 patients each) are too small to reach it. The best pair reaches 40% predicted power. The gate was not loosened. Phase 3 trials that randomize two doses of one drug will make these families testable: ritlecitinib 100 vs 50 mg (Tranquillo 2) and ruxolitinib cream 0.75% vs 1.5% (NCT06804811). Their results will be first-look evidence.

**Disclosures** (also recorded in the ledger's `meta` table):
- A v0 development run examined every existing unit, and its results shaped v0.1.
- The v1 families were designed by people who had seen these trials' published results.
- Evidence from units already in the corpus is therefore not strictly first-look; units from new data are.

## Code

| Module | Role |
|---|---|
| `discovery/evidence.py` | Mixture e-values, discovery-power simulation, e-LOND |
| `discovery/ledger.py` | SQLite ledger: hypotheses, tests, consumed units, policy events, forecasts |
| `discovery/policy.py` | Thompson-sampling bandit over claim templates |
| `discovery/loop.py` | Rounds: hold out a trial → fit without it → propose → test → record → update the policy |
| `discovery/forecasts.py` | Sealed forecasts for unreported trials, and their scoring when results post (`check-forecasts` runs weekly in CI) |
| `discovery/watch.py` | Weekly watch: ranks pending results by what they would tell us; lists new Europe PMC papers, ClinicalTrials.gov trials and SEC filings (`watch` runs weekly in CI) |
| `discovery/voi.py` | Value of information: how much evidence would move an answer, or separate models, before it is seen ([results](../forecasts/voi/README.md)) |

## Phases

| Phase | Adds | Status |
|---|---|---|
| v0 | Loop, ledger, e-values, e-LOND, bandit; superiority claims | Done |
| v1 | Three claim families; automatic sealed forecasts and their scoring | Done |
| v1 (rest) | Wider claim families from the arm table | Open |
| v2 | Value model trained on the ledger, to predict which claims survive | Needs hundreds of resolved tests |
| v3 | Evolution of the scenario model's own structure against held-out scores, with a locked exam | First trial run stopped: it failed its locked exam ([`lab/simulator/`](../lab/simulator/README.md)) |
| v4 | Mechanistic simulator plus treatment-schedule optimization | Depends on v3 |

## Limits

- **Data is the binding constraint, not compute.** About nine held-out trial × instrument combinations exist today.
- **A neural policy would only memorize noise** until the ledger holds hundreds of tests; a bandit is the right policy now.
- **Statistical, not clinical, validity.** A discovery is a research finding for expert review, not medical advice.
