"""Policy: which hypothesis template to try next (Thompson-sampling bandit).

Each *arm* is a template — a claim family x endpoint threshold x margin (or
retained fraction), e.g. ``k75-d0.05`` = "beats placebo on VASI75 by more than
5 points", ``contrast:k50-d0.10`` = "the higher dose beats the lower dose on
VASI50 by more than 10 points", ``retain:k75-r0.50`` = "the lower dose keeps more
than half of the higher dose's VASI75 response rate".
The reward is held-out evidence (e >= 2) from the ledger, so the policy learns
which kinds of claims tend to survive tests on data the generator never saw.
The snapshot used for a trial leaves out that trial's own earlier rewards.

A bandit is the right policy at this data scale; the plan
(docs/discovery-loop-plan.md) replaces it with a learned value model and
then a policy network once the ledger holds enough resolved tests.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

# Reward = 1 when the held-out evidence for the claim reaches e >= 2.
EVIDENCE_REWARD_LOG_E = float(np.log(2.0))


def arm_name(threshold: int, margin: float) -> str:
    """Superiority over control (the v0 family keeps its original arm names)."""
    return f"k{threshold}-d{margin:.2f}"


def contrast_arm_name(threshold: int, margin: float) -> str:
    """A more intensive regimen beats a less intensive one by more than ``margin``."""
    return f"contrast:k{threshold}-d{margin:.2f}"


def retention_arm_name(threshold: int, ratio: float) -> str:
    """A less intensive regimen keeps more than ``ratio`` of a more intensive one's response."""
    return f"retain:k{threshold}-r{ratio:.2f}"


class ThompsonPolicy:
    """Beta(1 + reward, 1 + pulls - reward) per arm, from a frozen snapshot of the ledger."""

    def __init__(self, stats: Mapping[str, tuple[float, float]], rng: np.random.Generator) -> None:
        self._stats = dict(stats)
        self._rng = rng

    def choose(self, eligible: Sequence[str]) -> tuple[str, dict[str, float]]:
        """Pick an arm among ``eligible``; also return the sampled values (for the log)."""
        if not eligible:
            raise ValueError("no eligible arms")
        samples: dict[str, float] = {}
        for arm in eligible:
            reward, pulls = self._stats.get(arm, (0.0, 0.0))
            samples[arm] = float(self._rng.beta(1.0 + reward, 1.0 + pulls - reward))
        best = max(samples, key=lambda a: (samples[a], a))
        return best, samples
