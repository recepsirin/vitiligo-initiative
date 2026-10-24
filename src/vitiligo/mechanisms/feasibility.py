"""Can this hypothesis be tested with data that exists?

The question a ranking engine is supposed to answer, asked directly. Twice in
one week a test here looked ready and was not: GSE203262 merges each patient's
lesional and non-lesional samples with no record of which is which, and only
one vitiligo dataset in the world carries a treatment-response label, with
eight samples. Both walls were found by hand, months after the hypothesis was
written.

Two parts, kept apart because only one of them can be computed.

**Which datasets a test names, and whether we hold them** is read off the
record and checked against the corpus. Nothing is asserted.

**Whether the test needs data that does not exist yet** cannot be computed —
no corpus knows that skin sampled after treatment stops has never been
deposited. The record declares it, with the reason, and ``verify`` refuses a
declaration without one.

The binding constraint is what the status reports. A test needing samples
nobody has collected is blocked whether or not we also hold its reference
datasets, so that answer wins.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from vitiligo.mechanisms.schema import Mechanism

# Accessions a test can name: GEO series and trial registrations.
_IDENTIFIER = re.compile(r"\b(?:GSE\d+|NCT\d{8})\b")

TESTABLE_NOW = "testable_now"
BLOCKED_ON_NEW_DATA = "blocked_on_new_data"
MISSING_DATASET = "missing_dataset"
NO_DATA_NAMED = "no_data_named"


@dataclass(frozen=True)
class Feasibility:
    """What stands between a hypothesis and its test."""

    status: str
    held: list[str]
    missing: list[str]
    needs_new_data: bool
    note: str

    @property
    def can_start(self) -> bool:
        return self.status == TESTABLE_NOW


def named_datasets(mechanism: Mechanism) -> list[str]:
    """Accessions the test names, in the order written, without repeats."""
    found = _IDENTIFIER.findall(mechanism.test.data or "")
    return list(dict.fromkeys(found))


def assess(mechanism: Mechanism, held_identifiers: Iterable[str]) -> Feasibility:
    """Whether the test could run today, and what stops it if not."""
    held_set = {i.upper() for i in held_identifiers}
    named = named_datasets(mechanism)
    held = [n for n in named if n.upper() in held_set]
    missing = [n for n in named if n.upper() not in held_set]
    needs_new = bool(mechanism.test.needs_new_data)

    if needs_new:
        status, note = BLOCKED_ON_NEW_DATA, mechanism.test.new_data.strip()
    elif missing:
        status = MISSING_DATASET
        note = f"not in the corpus: {', '.join(missing)}"
    elif not named:
        status, note = NO_DATA_NAMED, "the test names no dataset to check"
    else:
        status, note = TESTABLE_NOW, f"every dataset it names is held: {', '.join(held)}"

    return Feasibility(
        status=status, held=held, missing=missing, needs_new_data=needs_new, note=note
    )


def corpus_identifiers() -> set[str]:
    """GEO series and trials the corpus holds, for checking a test against."""
    from sqlmodel import select

    from vitiligo.storage import Document, SourceKind, Trial, init_db, session_scope

    init_db()
    with session_scope() as session:
        geo = session.exec(
            select(Document.source_id).where(Document.source == SourceKind.GEO)
        ).all()
        trials = session.exec(select(Trial.source_id)).all()
    return {str(i).upper() for i in [*geo, *trials]}
