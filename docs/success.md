# What success means

Every piece of work in this initiative is judged against this page. It answers two questions: what would "solved" mean for vitiligo, and what counts as our contribution.

## The problem

Vitiligo is three problems at once. A treatment that solves the disease has to beat all three:

1. **The attack.** Immune cells keep destroying melanocytes, so the disease spreads.
2. **The loss.** Destroyed melanocytes must be regrown. Hands and feet, with few hair follicles to regrow from, respond worst.
3. **The memory.** Immune cells that stay resident in the skin bring the disease back when treatment stops.

Today's best treatments, JAK inhibitors, suppress the attack. After they are stopped, the best results fade for many patients, and body response fades more.

## The north star

Four outcomes, each measurable. The targets are proposals, to be set with clinicians and patients.

| Outcome | Measure | Best today | Target (proposed) |
|---|---|---|---|
| **1. Stop spread** | In patients with **active** disease: no new or growing lesions at 1 year | Rarely measured (15 of 320 registered trials measure it directly; none posted a proportion stable). Tranquillo, active and stable disease: about 80% stable on ritlecitinib vs 60% on placebo. No placebo-controlled results in active disease ([`spread/`](spread/README.md)) | Most patients with active disease stable at 1 year |
| **2. Restore pigment** | Face: F-VASI75. Body: T-VASI50. Hands | **Face:** ruxolitinib cream about 30% at week 24 (of all randomised, missing results imputed) and 48–53% at week 52 — but that counts only the patients assessed then, 173–177 of the 221–222 at week 24, so over the group that started it is somewhere in **38–59%**; oral JAK inhibitors 12.5–25% at week 48–52 in phase 3. **Body:** 9–21.5% (oral, week 48–52). **Hands:** poor | Most patients reach F-VASI75 and T-VASI50 within a year, with meaningful response on the hands |
| **3. Last** | Response kept ≥1 year after stopping or tapering | **Cream, near-complete responders who stopped:** most kept F-VASI75 for a year (time to relapse below F-VASI75, hazard ratio 0.42, 95% CI 0.18–0.99, median not reached in either arm). Near-complete response itself went sooner: F-VASI90 was lost after a median of 195 days, hazard ratio 0.32 (0.17–0.61). The two are different endpoints and their figures do not pair. **Oral:** no data yet; a forecast is sealed ([`durability/`](durability/README.md)) | Most patients keep it off continuous treatment |
| **4. Safe and reachable** | Long-term safety; cost and access | **Cream:** no treatment-related serious events over 2 years. **Oral:** no excess cardiovascular events or clots in skin-disease trials, but only about 5 months of follow-up; boxed warnings apply to both. **Access:** cream about $2,100–2,800 per tube in the US; in England funded for facial vitiligo only after first-line topicals ([`safety-access/`](safety-access/README.md)) | Acceptable for years of use, and accessible |

Sources for "best today": [topline check](../forecasts/TOPLINE-CHECK-2026-10-14.md), [povorcitinib check](../forecasts/povorcitinib-phase3/README.md), [simulator exam](../lab/simulator/README.md) (TRuE-V week 52), [curated results](../curation/README.md).

## What counts as our contribution

We do not make drugs. We count as successful when the field reaches the north star faster because of our work, in one of three ways:

1. **Answers that change decisions.**
   - The answer is to a question a clinician, patient or trialist actually faces.
   - It is stated in advance with an effect size and the result that would prove it wrong, sealed before the data that test it exist, and then confirmed by those data.
   - It must not be what experts already expected.
2. **Candidates aimed at the gaps.** Treatments or combinations targeting what current drugs cannot do: regrowing melanocytes (problem 2) and preventing relapse (problem 3). Success means validated in a lab, then in a trial.
3. **Better trials.** Trial designs we influence: endpoints that capture durability and hands, realistic sample sizes, the right patients.

**Does not count:** more code, more documents, better fits to data already seen, or any claim not tested on data that came later.

## The test for any piece of work

- **Which outcome above does it move?**
- **How will we know?**

If neither has an answer, the work is infrastructure, and infrastructure should be the minimum the answer needs.

## Current focus: outcome 3, durability

Relapse after stopping is the largest unmet need with the least randomized evidence, and new data on it are arriving. Work in progress: [`durability/`](durability/README.md). The first forecast, of stopping oral ritlecitinib, is sealed. The order of work across all four outcomes: [`roadmap.md`](roadmap.md).

**First goal:** a pre-registered answer to this question, confirmed by data that do not yet exist:

> **What happens to repigmentation when JAK treatment is reduced or stopped, and who keeps it?**
