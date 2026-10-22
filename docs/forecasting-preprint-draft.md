# Forecasting Preprint — Draft Text

**Status:** Draft v0.1 (October 2026). Abstract written; the other sections are notes. Every number cites the file it comes from. Companion to the engine paper ([`methods-preprint-draft.md`](methods-preprint-draft.md)).
**Working title:** *Sealed forecasts and pre-registered models: an open, self-checking evaluation of JAK-inhibitor evidence in vitiligo*
**Authors:** [TBD]

---

## Abstract

**Background.** Phase 2 results shape what phase 3 trials of JAK inhibitors in vitiligo are expected to show, but models built on them are rarely tested on results they have not seen, and their forecasts are rarely fixed in advance. We built an open pipeline that forecasts unreported trials before their results are known, seals each forecast, and scores it automatically when results appear.

**Methods.**
- **Data.** We linked every registered vitiligo trial of a JAK-family drug across registries and harmonized posted results into one arm × endpoint × week table. Results that only papers or public toplines report were added with their sources.
- **Model.** A Bayesian ordered-probit model-based meta-analysis predicts F-VASI and T-VASI responder rates by drug, dose and week.
- **Sealing.** Each forecast is sealed with a SHA-256 hash of its content: the predictive draws, a data fingerprint, the git commit of the code, and a recorded search for already-public results.
- **Model changes.** Each was pre-registered and hash-sealed before its first fit; adoption follows a pre-registered rule.
- **Value of information.** An engine estimating how much evidence would change the model's answers was validated retrospectively, then used under a further pre-registration to rank pending trials, with a prospective test of its own predictions.

**Results.**
- **Data.** The atlas covers 45 studies of 14 drugs; 14 have posted results, which yield 830 comparable rows.
- **The default model.** Its forecasts of oral phase 3 trials were 13–34 percentage points too high on F-VASI75 at week 48–52.
- **Missed public results.** Twelve of the first 15 sealed forecasts turned out to have public toplines that registry status did not reveal. One sponsor's phase 3 toplines went unnoticed for six months.
- **Models.**
  - A pre-registered structural change, fitted without phase 3 oral data, was not adopted (summed log score −54.29 vs −54.13).
  - Two challengers trained on the public toplines scored −49.2 against −54.1 when one oral programme was held out (report only).
  - On a third oral programme, which none of the models had facial data for, they scored −16.0 and −15.9 against −17.5 (post hoc).
- **Other pre-registered attempts.** A mechanistic simulator failed its locked exam. A discovery loop with false-discovery-rate control made 4 discoveries in its first run (ruxolitinib cream beats vehicle), then abstained on all 188 open comparisons (drug vs placebo, dose vs dose, regimen vs regimen) for lack of power.
- **Value of information.** The engine passed its retrospective gate narrowly (Spearman 0.53, 0.68 after a bug fix reported as post hoc).
- **Reproducibility.** Refitting sealed forecasts showed that some had been sealed on uncommitted code; their medians moved by at most 0.6 points.
- **Pending.** 41 sealed response-rate forecasts and 1 sealed durability forecast await results; 7 of the first kind decide the default model.

**Conclusions.**
- Sealing and pre-registration turned several plausible improvements into recorded failures, and exposed a large phase 2 → phase 3 gap for oral JAK inhibitors that the default model misses.
- The pipeline's main output so far is a verifiable record: which forecasts were truly prospective, what changed and why, and which pending results matter most.
- Code, data and every sealed record are public.

**Availability.** https://github.com/recepsirin/vitiligo-initiative (Apache 2.0).

---

## 1. Introduction (notes)

- **The question:** how well do phase 2 results of JAK inhibitors in vitiligo predict phase 3? Model-based meta-analysis is the standard tool, but its validation is usually retrospective and its forecasts can be revised after the fact.
- **The gap:** forecasts fixed before results exist are rare in this field; so are model changes made under a pre-registered rule. Registry status is often used as the marker of "unreported", which we show to be unreliable.
- **Contribution:**
  1. an open, automated pipeline from registries to sealed forecasts;
  2. a record of every forecast, model change and test, including failures;
  3. a value-of-information engine that is itself tested prospectively.

## 2. Methods (notes)

### 2.1 Evidence base
- Atlas and arm table: [`docs/jak-scenario-model.md`](jak-scenario-model.md), `vitiligo report jak`, `report jak-arms`. Counts: [`findings.md`](findings.md).
- Curated paper rows tied to printed table cells, tagged by analysis population (`nri` vs as observed): [`curation/README.md`](../curation/README.md).
- Public phase 3 toplines with sources (`curation/topline-results.json`, frozen; pending ones in `topline-pending.json`).

### 2.2 Scenario model
- Ordered probit over responder thresholds; drug effects with log-dose slopes, route-level class priors, an Emax-type time course, trial random effects.
- Versions:
  - v0.2: default;
  - v0.3: adds a trial-by-treatment effect and a phase 3 shift per route;
  - v0.4: v0.3 trained on toplines;
  - v0.5: adds per-route baselines.

  Pre-registrations: [`model-v0.3`](model-v0.3-preregistration.md), [`v0.4`](model-v0.4-preregistration.md), [`v0.5`](model-v0.5-preregistration.md).
- Convergence gate: R-hat ≤ 1.01, bulk ESS ≥ 400, no divergences.

### 2.3 Sealed forecasts
- Targets come from registered designs (`registry_targets`): randomized active arm with a placebo arm, a disclosed dose, and a VASI responder endpoint.
- **The record:**
  - posterior summaries and predictive draws (hash-sealed `.npz`);
  - the data fingerprint and fit settings;
  - a written search for already-public results;
  - the git commit (since 2026-10-21; sealing refuses uncommitted model code).
- **Scoring:** a weekly workflow scores records against ClinicalTrials.gov by the log probability of the observed counts. Only the 7 pre-registered targets decide the default model.

### 2.4 Pre-registration practice
- Each plan is hashed before its first fit, and later changes are allowed only as appended amendments. `scripts/model/verify_preregistrations.py` re-checks all seals.

### 2.5 Value of information
- Expected variance reduction (EVR) of fixed questions by posterior reweighting. Arms of one trial share new-trial effects.
- **Retrospective gate:** [`voi-preregistration.md`](voi-preregistration.md).
- **Prospective ranking:** [`voi-ranking-preregistration.md`](voi-ranking-preregistration.md).
- Model discrimination by mutual information on sealed draws.

### 2.6 Weekly watch
- Every week the watch ranks pending results by how well they would separate the models. It lists new Europe PMC papers, new or updated ClinicalTrials.gov trials and, optionally, SEC filings.
- Each lead is triaged on record ([`forecasts/watch-triage.md`](../forecasts/watch-triage.md)).

## 3. Results (notes)

| Result | Numbers | Source |
|---|---|---|
| Prospective status of the first 15 forecasts | 12 had public toplines before sealing | [`TOPLINE-CHECK-2026-10-14.md`](../forecasts/TOPLINE-CHECK-2026-10-14.md) |
| v0.2 against oral phase 3 toplines | F-VASI75 13–34 points too high; placebo 9–15% forecast vs 2–7% observed | same |
| v0.3 (structure only) | E1 −54.29 vs v0.2 −54.13; not adopted | [`forecasts/v0.3/`](../forecasts/v0.3/README.md) |
| v0.4, v0.5, one oral programme held out (report only) | −49.23, −49.18 vs v0.2 −54.13 | `forecasts/v0.4/lopo.json`, `v0.5/lopo.json` |
| Povorcitinib phase 3, F-VASI75 week 52 (post hoc) | −16.0, −15.9 vs v0.2 −17.5; all observed rates inside every 80% range | [`povorcitinib-phase3/`](../forecasts/povorcitinib-phase3/README.md) |
| Simulator, locked exam | log score −170.6 vs benchmark −124.0; coverage 0.56 vs 0.80 | [`lab/simulator/`](../lab/simulator/README.md) |
| Discovery loop | v0.1: 4 discoveries (ruxolitinib cream beats vehicle, TRuE-V); v1: 188 comparisons, 0 tests run (all underpowered) | [`discovery-loop-plan.md`](discovery-loop-plan.md) |
| VOI retrospective gate | passed; Spearman 0.53 (0.68 after a post-hoc fix) | [`forecasts/voi/`](../forecasts/voi/README.md) |
| VOI ranking of pending evidence | pediatric ruxolitinib trials and STOP-V lead on F-VASI75; pediatric trials lead on T-VASI50 | [`voi/ranking/`](../forecasts/voi/ranking/README.md) |
| Durability after stopping an oral JAK inhibitor (sealed, pending) | Tranquillo LTE: still responding after stopping 42% (80%: 14–76%); hazard ratio continue vs stop 0.35 (0.17–0.69) | [`docs/durability/`](durability/README.md) |
| Reproducibility of sealed forecasts | v0.2, v0.4 within 1.4 points; v0.5 exact | [`forecasts/README.md`](../forecasts/README.md#reproducibility) |

Figures to make from these files:
1. Forecast vs observed for the oral phase 3 toplines (v0.2, v0.4, v0.5).
2. The model-change timeline with each pre-registration and its outcome.
3. The value-of-information ranking with its Monte Carlo ranges.

## 4. Discussion (notes)

- **The phase 2 → phase 3 gap for oral JAK inhibitors** is the main substantive finding. Possible drivers (disease activity mix, extent, prior therapy, how responders were counted) need experts and patient-level data.
- **Structure cannot learn a bias the data do not contain** (v0.3). Adding the phase 3 data did help on a held-out programme (v0.4, v0.5).
- **Registry status is not a reliable marker of "unreported".** Sealing must record a search of press releases, conferences and filings.
- **Sealing needs code provenance as well as data provenance:** the drift we found was small, but it would have been undetectable without refits.
- **Value-of-information estimates are noisy** at the top of the ranking; the prospective test will show whether they track realized change.

## 5. Limitations (notes)

- Few phase 3 programmes. Prospective results resolve slowly: the deciding trials reach primary completion between February 2026 (Tranquillo) and mid-2028, and results post later.
- **Assumptions about the toplines.** We assume they count missing patients as non-responders, and derive arm sizes from reports or registered allocation.
- **Missing covariates.** The models have no term for population or region, so a new trial of a known drug gets the same forecast anywhere.
- **T-VASI value-of-information figures are upper bounds;** the base model's phase 3 shift has a wide prior.
- **Author knowledge.** The author designed the challenger models after seeing the topline results; only prospective targets test them cleanly.

## Writing plan

- [ ] Expand Methods 2.2–2.6 into prose, with the model specification and priors
- [ ] Make figures 1–3 from the committed result files
- [ ] Update the Results table as pending targets resolve (weekly check)
- [ ] Expert review of the findings ([`findings.md`](findings.md), questions at the end)
- [ ] Authors, contributions, funding and conflicts of interest
- [ ] Zenodo snapshot of the sealed records, then medRxiv
