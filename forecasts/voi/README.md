# Value-of-information engine: core results (2026-10-14)

Pre-registration: [`docs/voi-preregistration.md`](../../docs/voi-preregistration.md), sealed before any value was computed. Code: `src/vitiligo/discovery/voi.py` (tested against exact Beta-Binomial answers) and `scripts/model/voi_core.py`.

## Retrospective gate: passed, narrowly

11 pieces of evidence we have already seen. Their value was predicted from a registry-only model (M0), and their actual impact was measured by refitting with each one added (`gate.json`, `retro-*.json`; all 13 fits converged).

| Criterion | Result |
|---|---|
| G1: every phase 3 topline is predicted to be worth more than every paper item (oral question) | **Passed** in both instruments; on F-VASI by a factor of more than 200 |
| G2: predicted value tracks realized impact (Spearman ≥ 0.5) | **Passed, narrowly:** ρ = 0.53 |

**Calibration: good on F-VASI, poor on T-VASI.** `realized shift² / predicted EVR` should average about 1. It ranged from 0.29 to 1.25 on F-VASI, and from 0.02 to 0.13 on T-VASI.

## Bug found and fixed (v1.1, post-hoc)

The investigation of the T-VASI gap found a real bug:
- **The bug.** The engine integrated each arm's new-trial random effects (baseline, trial-by-treatment effect) separately, although the arms of one trial share them. So a low placebo arm and a moderate active arm could each use a different "trial".
- **How it was found.** Refits were stable across seeds, the reweighting looked reliable (Pareto k < 0.25), and simulated outcomes agreed with refits. Only the real Tranquillo outcome, a very low placebo that forces a low shared baseline and therefore a larger drug effect, exposed it.
- **The fix.** Arms are summed within each shared replicate before averaging; this is tested against exact integration. Reweighted shifts now match the refits within about 0.01 on all 11 items. Before the fix, Tranquillo T-VASI was −0.12 vs −0.02.

Re-scored with the fixed engine (`gate-v1.1.json`). This is post-hoc and recorded as an amendment to the pre-registration:

| | v1.0 (pre-registered) | v1.1 (post-hoc) |
|---|---|---|
| G1 | Passed | Passed |
| G2 (Spearman) | 0.53 | 0.68 |
| Surprise ratios, F-VASI | 0.29–1.25 | 0.34–1.28 |
| Surprise ratios, T-VASI | 0.02–0.13 | 0.02–0.17 |

**The T-VASI gap remains, and it is not the bug.** With the likelihood now matching refits, the remaining cause is the registry-only model itself. With no phase 3 oral data, its phase 3 shift κ sits at a wide prior, so it expects large swings in T-VASI answers, and the real results moved them little. Six correlated items cannot settle this. **Treat T-VASI values as upper bounds** until prospective results show otherwise.

## Model discrimination of the sealed targets

`discrimination.json`: how much each pending result can tell us about which sealed model (v0.2, v0.4, v0.5) is right, at the registered arm sizes.
- **Most informative:** Tranquillo 2's T-VASI50, at 0.30 of a possible 1.10 nats.
- **Pediatric trials:** about 0.09 each.
- **No single result is decisive;** the comparison will take several.

## Next

Automatic weekly discovery of candidate evidence (new trials, new open-access papers) and a ranked report. Each new result also tests calibration prospectively, which is what can settle the T-VASI question.
