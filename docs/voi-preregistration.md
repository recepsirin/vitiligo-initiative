# Value-of-information engine, core: pre-registration

Written 2026-10-14, before any value of information was computed. The SHA-256 of this file is recorded in `forecasts/voi-preregistration.sha256`.

## What the engine scores

For a piece of evidence (a set of arm-level results of given sizes), it scores how much the evidence is expected to change answers to fixed questions, before we see it.

**Questions Q** (per instrument model): the expected responder rate in a **new phase 3 trial**, averaged over new-trial variation (the part evidence can reduce):
- **F-VASI model:** ritlecitinib 50 mg QD, F-VASI75 at week 52 (`Q_oral`); ruxolitinib cream 1.5% BID, F-VASI75 at week 24 (`Q_topical`).
- **T-VASI model:** the same two drugs, T-VASI50 at the same weeks.

**Predicted value** of an evidence item is the expected variance reduction of Q (EVR), estimated by simulating the item's outcomes from the current posterior and reweighting the draws. By the law of total variance, EVR is also the expected squared shift of Q's mean. So `realized shift² / EVR` should be about 1 on average. Values far above 1 mean the model did not see the surprise coming.

**Model discrimination** for a pending target: the mutual information between its outcome (at the registered size) and which sealed model (v0.2, v0.4, v0.5) is right, computed from the sealed predictive draws with equal prior weights.

## Retrospective gate (decides whether the engine is trusted)

**Base model M0:** v0.3 structure, `target_accept = 0.995`, fitted on registry data only (no paper rows, no toplines).

**Evidence items:** 11, each with the outcome actually observed.
- **8 topline items:** (Tranquillo 50 mg, Tranquillo 2 100 mg, Viti-Up 1, Viti-Up 2) × (F-VASI75 week 52 or 48, T-VASI50 same week), each an active/placebo pair at its reported size.
- **3 paper items** (curated `nri` rows only):
  - ruxolitinib phase 2 1.5% BID F-VASI rows;
  - the same arm's T-VASI rows;
  - upadacitinib phase 2 T-VASI50 at week 24 (4 arms).

**Predicted value:** EVR of `Q_oral + Q_topical` for each item, from M0.

**Realized impact:** refit M0 with the item added; the squared shift of `Q_oral + Q_topical`'s posterior mean.

**The engine passes only if both hold:**
- **G1.** For `Q_oral`, every topline item's predicted value exceeds every paper item's predicted value in the same instrument.
- **G2.** The Spearman correlation between predicted value and realized impact across the 11 items is at least 0.5.

**Reported but not part of the gate:** `realized shift² / EVR` per item, and the effective sample size of the reweighting.

If the engine fails, it is not used to rank evidence until the failure is understood and a new pre-registration is written.

## Disclosure

The author knows the toplines changed v0.2's forecasts far more than the paper rows did; that is why G1 is a minimum bar, not a discovery. G2 and the surprise ratios are the informative parts.

## Amendments

None yet.
