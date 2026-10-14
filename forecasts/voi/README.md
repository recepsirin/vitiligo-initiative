# Value-of-information engine: core results (2026-10-14)

Pre-registration: [`docs/voi-preregistration.md`](../../docs/voi-preregistration.md), sealed before any value was computed. Code: `src/vitiligo/discovery/voi.py` (tested against exact Beta-Binomial answers) and `scripts/model/voi_core.py`.

## Retrospective gate: passed, narrowly

11 pieces of evidence we have already seen. Their value was predicted from a registry-only model (M0), and their actual impact was measured by refitting with each one added (`gate.json`, `retro-*.json`; all 13 fits converged).

| Criterion | Result |
|---|---|
| G1: every phase 3 topline is predicted to be worth more than every paper item (oral question) | **Passed** in both instruments; on F-VASI by a factor of more than 200 |
| G2: predicted value tracks realized impact (Spearman ≥ 0.5) | **Passed, narrowly:** ρ = 0.53 |

**Calibration: good on F-VASI, poor on T-VASI.**
- `realized shift² / predicted EVR` should average about 1.
- F-VASI: 0.29–1.25. The large F-VASI shifts from the ritlecitinib toplines (−0.18 to −0.19) were anticipated.
- T-VASI: 0.02–0.13. Realized shifts were far smaller than predicted.
- The cause is visible in the diagnostics. The fast reweighting estimate of the same shifts was much larger than the refits (for example −0.12 vs −0.02 for Tranquillo T-VASI). Data from a new trial mostly updates that trial's own effects (its baseline and trial-by-treatment term), and reweighting with a few replicates of those effects does not fully absorb them.

**What this means:** the engine can **rank** evidence, but it **overstates** how much a new trial will move T-VASI answers. Treat its absolute values as upper bounds until the replicate count or the approximation is improved, and check it prospectively.

## Model discrimination of the sealed targets

`discrimination.json`: how much each pending result can tell us about which sealed model (v0.2, v0.4, v0.5) is right, at the registered arm sizes.
- **Most informative:** Tranquillo 2's T-VASI50, at 0.30 of a possible 1.10 nats.
- **Pediatric trials:** about 0.09 each.
- **No single result is decisive;** the comparison will take several.

## Next

Automatic weekly discovery of candidate evidence (new trials, new open-access papers) and a ranked report. That work should also fix the T-VASI over-estimate before the rankings are relied on.
