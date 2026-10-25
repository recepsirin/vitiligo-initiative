"""What a reported rate could be on the group it was reported from.

A trial that counts only the patients assessed at a visit leaves the rest
unaccounted for, and the published figure is then a rate over a group chosen
partly by who stayed. TRuE-V2 reports 48.0% of the 177 patients with data at
week 52, out of 222 in the analysis set at week 24. The 45 who are missing
either reached the threshold or did not, and nothing in the record says which.

That brackets the answer without assuming anything. If every missing patient
failed, 85 of 222 reached F-VASI75, which is 38.3%. If every one succeeded,
130 of 222 did, which is 58.6%. The true figure is inside, and the width of
the bracket is the price of the missing data.

This is worth more than it looks. A point estimate taken from the assessed
patients alone is not conservative — it is the most favourable reading
available — while a non-responder-imputed figure is the least. Reporting both
ends says what the trial can and cannot establish, and a model's prediction
can be checked against the bracket even where there is no figure to fit.

The bracket is only as good as the group it is taken over, which is why
``group`` is named rather than assumed: a rate bounded over an arm's week-24
analysis set is a statement about that set, not about everyone randomised, and
the two differ whenever a trial dropped a site or a visit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bounds:
    """A rate's range over ``group``, given that only ``analysed`` were counted."""

    responders: int
    analysed: int
    group: int

    @property
    def missing(self) -> int:
        """Patients in the group whose outcome the figure does not cover."""
        return max(0, self.group - self.analysed)

    @property
    def reported(self) -> float:
        """The rate as published: over the patients who were counted."""
        return 0.0 if not self.analysed else round(100.0 * self.responders / self.analysed, 1)

    @property
    def floor(self) -> float:
        """Every uncounted patient treated as not having responded."""
        return 0.0 if not self.group else round(100.0 * self.responders / self.group, 1)

    @property
    def ceiling(self) -> float:
        """Every uncounted patient treated as having responded."""
        if not self.group:
            return 0.0
        return round(100.0 * (self.responders + self.missing) / self.group, 1)

    @property
    def width(self) -> float:
        """Percentage points the missing data leave undetermined."""
        return round(self.ceiling - self.floor, 1)

    @property
    def identified(self) -> bool:
        """Whether the figure covers the whole group, leaving nothing to bound."""
        return self.missing == 0

    def covers(self, percent: float) -> bool:
        """Whether a rate is one the group could have produced."""
        return self.floor <= percent <= self.ceiling


def bound_rate(responders: int | None, analysed: int | None, group: int | None) -> Bounds | None:
    """Bounds for a reported count, or None where the record cannot support them.

    ``group`` must be at least ``analysed``: a reference smaller than the set
    actually counted means the two are not the group and a subset of it, and a
    bracket computed from them would be narrower than the truth — which is the
    one direction a bound must never be wrong in.
    """
    if responders is None or not analysed or not group:
        return None
    if responders < 0 or responders > analysed or group < analysed:
        return None
    return Bounds(responders=int(responders), analysed=int(analysed), group=int(group))
