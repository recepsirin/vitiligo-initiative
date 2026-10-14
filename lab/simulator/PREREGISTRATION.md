# Repigmentation simulator — pre-registration

Written 2026-10-14, before any simulator program was fitted. The SHA-256 of this file is recorded in `results/preregistration.sha256`. Any later change is listed under *Amendments* with its reason.

## Question

Can a mechanistic, patient-level model of repigmentation, found by program search, predict held-out JAK-inhibitor outcomes better than the current statistical scenario model (the "benchmark": `vitiligo.models.jak_mbma`, v0.2)?

## Data

- `data/arms-snapshot.json` (SHA-256 in `data/arms-snapshot.sha256`): the harmonized arm table, 830 rows.
- Rows are selected exactly as the benchmark selects them (`build_dataset`). Same exclusions: extension studies, within-arm treatment switches, the NCT03099304 design cap, and local reads where central reads exist.
- **Search set S:** F-VASI and T-VASI observations up to week 24. The search code refuses any row after week 24.
- **Exam set E:** observations after week 24 of active arms, which are exactly the rows of the benchmark's time-extrapolation back-test. These are TRuE-V1/2 week 52 and NCT05247489 weeks 32–48 (both instruments), and NCT05750823 week 48 (T-VASI).

## Programs

A program maps a patient's latent repigmentation over time to responder rates. Baseline structure:

- Patient *i* in trial *t*, region *g* (face or body): `R_i(w) = 1 − exp(−Λ_i(w)^γ)`, with cumulative exposure `Λ_i(w) = exp(θ_g + u_t + η_i) · ∫_τ^w e_arm(s) ds`.
- `η_i ~ N(0, σ²)` is patient heterogeneity. `u_t ~ N(0, σ_u²)` is the trial effect, integrated out by Gauss–Hermite quadrature.
- `e_arm = 1` on vehicle or placebo. On drug, `e_arm = exp(E)`, with `E = α_route + δ_agent + β_route · log(dose / reference dose)` + phototherapy `φ`. Loading doses act for the first 4 weeks (registry: "induction dose QD for 4 weeks followed by maintenance").
- This gives, in closed form, `P(VASI-k at w) = Φ((θ_g + u_t + log A(w) − c_k / γ) / σ)` with `c_k = log(−log(1 − k/100))`. The cut-points are therefore fixed by the mechanism, and F-VASI100 maps to a fitted ceiling κ > 0.90.

The search varies these components:

| Component | Options |
|---|---|
| Kinetics | γ fixed at 1, or free |
| Onset lag τ | 0, or free in [0, 3.5] weeks |
| Thresholds | mechanistic `c_k / γ`, or free ordered cut-points (an empirical control) |
| Heterogeneity σ | shared, or one per region |
| Non-responders | none, a shared fraction q, or one per region (`P = (1 − q) · Φ(·)`) |
| Dose response | log-linear, or Emax |
| Trial effect | shared across regions, or independent per region |
| Placebo | one baseline, or an offset for oral placebo vs topical vehicle |

Fixed choices:
- **Agent deviations** `δ_agent ~ N(0, 0.75²)`, with the SD fixed rather than fitted. An agent missing from a fold's training data is drawn from this distribution.
- **Reference dose** for each agent: the highest daily dose in the snapshot's design. This is design information, not outcomes.
- **Fitting:** maximum a posteriori estimation of the marginal likelihood, with weakly informative priors listed in `vsim/program.py`. Parameter uncertainty comes from a Laplace approximation (400 draws).

## Search

- **Search score:** leave-one-trial-out with the control arm kept (the benchmark's design), on S. For each controlled trial, its active arms are removed from both instruments, the program is fitted, and that trial's active arm-weeks are predicted, conditioned on its control arm.
  - Score: the mean log predictive probability of each arm-week's observed counts, as a multinomial over threshold bins.
  - Predictive probabilities average over parameter uncertainty.
- **Evolution:** start from the baseline. Each generation evaluates all one-component mutations of the current top 3 that haven't been evaluated yet. Proposals written in-session (new components) are allowed and logged. The search stops after a generation that improves the best score by less than 0.005 nats per arm-week, or after **500 programs**.
- **Log:** every program and its score go to `results/programs.jsonl`.
- **Selection:** the program with the best search score. Programs within 0.01 nats per arm-week of the best count as tied, and the one with fewer parameters wins. The selection is sealed (hash plus timestamp) in `results/selection.json` before the exam runs. The exam code refuses to run without that file and scores only the selected program.

## Exam and decision

The selected program and the benchmark are scored on E with identical metrics:
- the log predictive probability of each arm-week, summed;
- the share of rows whose observed rate falls inside the 80% predictive interval;
- the mean signed error.

The benchmark is fitted on S (up to week 24) and conditioned on trial and arm, as in its own back-test.

**Continue** only if all three hold:
1. The simulator's summed exam log score is higher than the benchmark's.
2. The simulator's exam coverage at 80% is at least 0.70.
3. The simulator's search score is no worse than the benchmark's on the same leave-one-trial-out design over S, by more than 0.05 nats per arm-week.

Otherwise, stop and write up the failure. Bootstrap intervals over trials are reported as exploratory only.

## Exploratory only (not part of the decision)

The long-term extension cohorts (NCT04530344), the vehicle-to-ruxolitinib crossover arms, and responder withdrawal. Only a patient-level simulator can model their selection rules. Results on these are labelled exploratory.

## Disclosure

- The benchmark is already known to over-predict TRuE-V week 52 (by about 20 points on F-VASI75).
- The author has seen the published week-52 results and, while planning this run, the extension-study rows.
- The search code cannot read the exam rows, but the exam is not first-look for the people running it.

## Amendments

1. **2026-10-14, before any exam scoring.** The benchmark's F-VASI fit on S had 1 divergent transition, so it fails the benchmark's own convergence gate. All 9 leave-one-trial-out folds converged. The F-VASI fit on S is redone once with `target_accept = 0.995`, and that fit is used whatever its diagnostics; they are reported. The original fit is kept as `results/benchmark/posterior_s_F-VASI.divergent.pkl`. This touches convergence only; no exam score had been computed for either model.
2. **2026-10-14, in-session proposal (search data only).** On the search set, the benchmark outscored the best program mainly on the ritlecitinib phase 2b trial, which is the only oral drug with weeks 4–24 data. The simulator shared one onset curve across routes, while the benchmark has a time course per route. New component **kinetics**: `shared` (as before) or `route` (γ and lag per route of the trial, active only where γ or lag is free). Existing programs are unchanged. After the first search stops, evolution resumes from the log with this component, under the same stopping rule and budget.
