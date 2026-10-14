# Curated results from open-access papers

`paper-results.json` holds results that papers report but trial registries do not. Each number cites its printed table cell: PMCID, table, section, row, column and the verbatim cell. Checks:

```bash
vitiligo papers verify                      # re-fetches each article; every cell and number must match
vitiligo papers tables PMC11169949          # print an article's tables while curating
vitiligo report jak-arms --with-papers      # append rows the registry lacks; cross-check the overlap
```

Every row is tagged with its **analysis population**:
- `nri`: missing patients counted as non-responders over the randomized arm, as in registry results.
- `as_observed`: only patients still assessed. These rates run higher and must not be pooled with `nri` rows as if they were the same.

The scenario model does not use these rows. Adding them is a model change, so it needs its own pre-registered plan.

## Contents (2026-10-14)

| Paper | Trial | What it adds | Population |
|---|---|---|---|
| PMC11169949, Table 3 | Upadacitinib phase 2 (NCT04927975) | Week 52, 6/11/22 mg, F-VASI75/50 and T-VASI50 | as observed |
| PMC11169949, Table 2 | Same | Week 24 T-VASI50 (absent from the registry); F-VASI rows for cross-checking | nri |
| PMC11608864, Table 1 | Ruxolitinib phase 2 (NCT03099304), 1.5% BID from day 1 | Weeks 24–156, F-VASI50/75/90 and T-VASI50/75 | nri to week 52, then as observed |

**Checks so far:** all 41 cells match the articles, and all 12 numbers that the registry also reports agree exactly. 29 rows are new.

Most other new results (povorcitinib body regions, PMC13619760; late ruxolitinib responders, PMC13425443; ruxolitinib body regions, PMC11851260) are only in figures. They are not curated, because reading values off plots is not reliable enough.

## What the new rows show (exploratory)

- **Oral response keeps rising after week 24.** Upadacitinib 11 mg reached F-VASI75 in 19.1% at week 24 (registry). At week 52 it was 24 of 38 still assessed (63.2%). Counting the 9 dropouts as non-responders still gives at least 51%.
- **The scenario model extrapolates this trial reasonably.** Fitted on registry data and conditioned on the trial, it predicts 44.7% at week 52 (80% range 31–63%).
- **Phase 3 is the problem, not the time course.** The same drug reached F-VASI75 in about 25% at week 48 in phase 3 (Viti-Up, intention-to-treat). Ritlecitinib's phase 3 results were also far below the forecasts ([topline check](../forecasts/TOPLINE-CHECK-2026-10-14.md)). A plausible reason is that phase 3 programs enrol broader populations that respond less. The model, built mostly on phase 2 trials, treats a new trial as typical of those.
- **Ruxolitinib does not show this gap:** F-VASI75 at week 24 was 30% in phase 2 and 30–31% in phase 3. These are single comparisons with small arms; they suggest a question, not an answer.
