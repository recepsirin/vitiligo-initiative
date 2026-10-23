"""Mechanistic hypotheses: the chain from biology to a clinical outcome.

A candidate score says how well studied a drug is. It cannot say *why* a
treatment should work, nor what would show that it does not. A mechanism
record carries that: one falsifiable claim, the chain it belongs to
(biological state -> mechanism -> intervention -> experimental outcome ->
clinical outcome), the evidence for and against it, the strongest competing
explanation, and the test that would separate them.

Two rules the records exist to enforce:

- **A claim may not outrank its evidence.** Each piece of evidence carries
  where it sits on the causal ladder (an association, a perturbation in
  cells, in animals, or in people). ``causal_support`` is computed from the
  supporting evidence, never curated, so a hypothesis resting on expression
  data cannot read as a demonstrated mechanism.
- **A claim must be able to fail.** Every record names what we expect to see
  if it is right, what we expect if it is wrong, and which test tells them
  apart. ``verify`` rejects a record that cannot.

Records live in ``curation/mechanisms.json`` and are checked by
``vitiligo mechanism verify``, which also resolves every citation against the
local corpus.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

CURATION_PATH = Path("curation/mechanisms.json")

# How directly a source speaks to cause, weakest first. ``causal_support`` is
# the strongest rung any supporting evidence reaches.
CAUSAL_LADDER = (
    "association",  # observed together: expression, abundance, correlation
    "human_genetics",  # an inherited variant associates with the disease
    "perturbation_in_vitro",  # the pathway was altered in cells
    "perturbation_in_animal",  # altered in an animal model, with an effect
    "perturbation_in_human",  # altered in people, with a measured effect
)

CAUSAL_LABELS: dict[str, str] = {
    "association": "Association",
    "human_genetics": "Human genetics",
    "perturbation_in_vitro": "Perturbation in vitro",
    "perturbation_in_animal": "Perturbation in animals",
    "perturbation_in_human": "Perturbation in people",
}

# ``bounds``: relevant and must be read, but it tests a different question or
# context. It limits what the claim may assume without supporting or
# contradicting it.
STANCES = ("supports", "contradicts", "bounds")

# draft -> sealed, then one of the three outcomes once its test has run.
STATUSES = ("draft", "sealed", "supported", "refuted", "dropped")

# Outcomes of docs/success.md.
OUTCOMES: dict[int, str] = {
    1: "Stop spread",
    2: "Restore pigment",
    3: "Last",
    4: "Safe and reachable",
}


def causal_rank(level: str) -> int:
    """Position on the ladder; -1 for an unknown level."""
    return CAUSAL_LADDER.index(level) if level in CAUSAL_LADDER else -1


@dataclass(frozen=True)
class Evidence:
    """One source, what it shows, and how directly it speaks to cause."""

    ref: str = ""  # pubmed:30021889 | pmc:PMC11851260 | geo:GSE203262 | trial:NCT04338581
    stance: str = ""  # supports | contradicts | bounds
    causal_level: str = ""  # a rung of CAUSAL_LADDER
    shows: str = ""  # what this source actually reports, in one line


@dataclass(frozen=True)
class Competing:
    """A rival explanation of the same observations, and how to tell them apart."""

    explanation: str = ""
    distinguished_by: str = ""


@dataclass(frozen=True)
class Context:
    """Where the claim is meant to hold. A mechanism without a context is untestable."""

    subtype: str = ""  # non-segmental | segmental | both
    tissue: str = ""
    cell_type: str = ""
    disease_stage: str = ""


@dataclass(frozen=True)
class Test:
    """The experiment that decides the hypothesis."""

    question: str = ""
    data: str = ""  # the dataset, trial or sample that would answer it
    if_correct: str = ""  # what we expect to see if the claim holds
    if_incorrect: str = ""  # what we expect if it does not
    decides: str = ""  # which hypothesis survives which result


@dataclass(frozen=True)
class Mechanism:
    """One mechanistic hypothesis, from biological state to clinical outcome."""

    id: str = ""
    title: str = ""
    status: str = ""
    outcome: int = 0  # 1-4, the outcome of docs/success.md it serves
    # The chain. Each level is one sentence.
    biological_state: str = ""
    mechanistic_claim: str = ""
    intervention: str = ""
    experimental_outcome: str = ""
    clinical_outcome: str = ""
    context: Context = field(default_factory=Context)
    upstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    competing: list[Competing] = field(default_factory=list)
    test: Test = field(default_factory=Test)
    uncertainty: str = ""  # what could make this wrong beyond the competing explanations
    last_reviewed: str = ""  # ISO date
    note: str = ""
    seal: dict[str, Any] | None = None

    @property
    def causal_support(self) -> str:
        """The strongest rung the supporting evidence reaches, or ``none``."""
        levels = [e.causal_level for e in self.evidence if e.stance == "supports"]
        return max(levels, key=causal_rank, default="none")

    def supporting(self) -> list[Evidence]:
        return [e for e in self.evidence if e.stance == "supports"]

    def against(self) -> list[Evidence]:
        return [e for e in self.evidence if e.stance == "contradicts"]

    def bounding(self) -> list[Evidence]:
        return [e for e in self.evidence if e.stance == "bounds"]


def _build(cls: type, record: Any) -> Any:
    """Build a record, ignoring unknown keys. Anything unusable yields an empty one,
    so ``verify`` reports the problem instead of the loader raising."""
    if not isinstance(record, dict):
        return cls()
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in record.items() if k in names})


def load(path: Path = CURATION_PATH) -> list[Mechanism]:
    """Read the curation file. Unknown keys are ignored, as in the other curations."""
    records = json.loads(path.read_text())["mechanisms"]
    return [from_dict(r) for r in records]


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def from_dict(record: dict[str, Any]) -> Mechanism:
    names = {f.name for f in fields(Mechanism)}
    data = {k: v for k, v in record.items() if k in names}
    data["context"] = _build(Context, record.get("context") or {})
    data["test"] = _build(Test, record.get("test") or {})
    data["evidence"] = [_build(Evidence, e) for e in _as_list(record.get("evidence"))]
    data["competing"] = [_build(Competing, c) for c in _as_list(record.get("competing"))]
    return Mechanism(**data)


def to_dict(mechanism: Mechanism) -> dict[str, Any]:
    return asdict(mechanism)


# ----------------------------------------------------------------------- seals

# The seal covers what must not move once the test is agreed: the claim, the
# context and the test. Evidence and notes stay editable, because sources
# accumulate; the hash is over the falsifiable core alone.
SEALED_FIELDS = (
    "id",
    "biological_state",
    "mechanistic_claim",
    "intervention",
    "experimental_outcome",
    "clinical_outcome",
    "context",
    "test",
)


def seal_core(mechanism: Mechanism) -> dict[str, Any]:
    """The part of a record its seal covers."""
    data = to_dict(mechanism)
    return {k: data[k] for k in SEALED_FIELDS}


def seal_hash(mechanism: Mechanism) -> str:
    """SHA-256 of the falsifiable core, canonically encoded (as forecast seals are)."""
    canonical = json.dumps(seal_core(mechanism), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class SealResult:
    """Outcome of sealing one record."""

    id: str
    sha256: str
    sealed_at: str
    commit: str | None = None
    problems: list[str] = field(default_factory=list)
