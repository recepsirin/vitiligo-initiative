# JAK inhibitors in vitiligo: what we found (October 2026)

Open research by the Vitiligo Initiative, for expert review. Not medical advice.

## What we built

- **Atlas.** 45 vitiligo studies of 14 JAK-family drugs, linked across registries. 14 have posted results.
- **Arm table.** Those results turned into 830 comparable rows (arm × endpoint × week), plus results that only papers report, each tied to its printed table cell.
- **Scenario model.** Predicts responder rates by drug, dose and week. It is judged only on trials it has not seen, and its forecasts are sealed before we look at their results.
- **Discovery loop.** Tests claims on held-out trials with false-discovery-rate control.
- **Simulator trial run.** A mechanistic, patient-level model of repigmentation, searched under a pre-registered plan.

Every forecast, test and model change is recorded, including the ones that failed.

## What we found

1. **Phase 3 oral programmes responded far less than phase 2 suggested.**
   - Upadacitinib F-VASI75: at least 51% at week 52 in phase 2, about 25% at week 48 in phase 3.
   - Our v0.2 model forecast the oral phase 3 trials 13–34 points too high.
   - Topical ruxolitinib shows no such gap (about 30% at week 24 in both phases).
2. **Response keeps rising long after week 24.** Ruxolitinib 1.5% BID F-VASI75: 30% at week 24, 52% at week 52, then 74% and 89% at weeks 104 and 156 among patients still treated. A model that read slow responders as non-responders failed its locked exam.
3. **Placebo response at one year is low,** 2–7% in phase 3, below what models extrapolate from week 24.
4. **Phase 2 dose comparisons are too small to settle dose questions.** On the current data the discovery loop abstained on all 188 open comparisons (drug vs placebo, dose vs dose, regimen vs regimen), because no test had a reasonable chance of a valid discovery.
5. **Registry status misses public results.** 12 of our 15 sealed forecasts turned out to have public toplines before sealing. Sealing now requires recording a search of press releases and conference abstracts.
6. **Model structure alone could not learn the phase 3 gap.** A pre-registered v0.3, fitted without phase 3 oral data, did no better than v0.2, so it was not adopted. Two challengers trained on the toplines (v0.4, v0.5) now forecast beside v0.2 and are scored as results post. Their median forecasts differ most for ruxolitinib cream in children (24%, 13% and 20% F-VASI75 at week 24), but their intervals overlap, so it will take several results to tell them apart ([scoreboard](../forecasts/README.md#scoreboard)).

Details: [forecasts and scoreboard](../forecasts/README.md) · [topline check](../forecasts/TOPLINE-CHECK-2026-10-14.md) · [curated paper results](../curation/README.md) · [scenario model](jak-scenario-model.md) · [simulator](../lab/simulator/README.md) · [discovery loop](discovery-loop-plan.md)

## What we need from experts

1. **The phase 2 → 3 gap for oral drugs.** Is it real, and what drives it? For example, the active/stable disease mix, disease extent, prior therapy, or how responders were counted.
2. **Ruxolitinib phase 2 (NCT03099304).** Did the 1.5% BID arm continue unchanged through week 52? We assume it did.
3. **Topline numbers.** Do sponsors count missing patients as non-responders, or impute them? We assume non-responders.
4. **The question that matters most.** Tapering, stopping, maintenance or combinations: which should a model try to answer first?
5. **Missing data.** Which trials, sponsor datasets or registries are we not seeing?
