"""The gate every mechanistic hypothesis must pass.

``verify`` is mechanical, in the spirit of ``vitiligo papers verify``: it reads
the curation file and reports problems, so a record cannot quietly become a
story. It checks three things that matter and one that is easy to get wrong:

1. **The chain is complete and the claim can fail.** Every level is filled in,
   the expected observations differ, and the test says which hypothesis
   survives which result.
2. **Every citation resolves** to a record in the local corpus, so a claim
   cannot cite a paper that is not there.
3. **A claim does not outrank its evidence.** A curated causal level is
   checked against what the corpus says the source is: a mouse study cannot
   carry a claim of perturbation in people.
4. **Seals still match.** A sealed record's claim, context and test are
   unchanged since it was sealed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import date

from sqlmodel import select

from vitiligo.evidence import EvidenceLevel, classify_document
from vitiligo.mechanisms.schema import (
    CAUSAL_LADDER,
    OUTCOMES,
    STANCES,
    STATUSES,
    Mechanism,
    seal_hash,
)
from vitiligo.storage import Document, GeneticAssociation, SourceKind, Trial, session_scope

_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_REF_RE = re.compile(r"^(pubmed|pmc|geo|trial|gwas):(.+)$")

_DOCUMENT_SOURCES = {
    "pubmed": SourceKind.PUBMED,
    "pmc": SourceKind.PMC,
    "geo": SourceKind.GEO,
}

# What a source cannot support, whatever the curator wrote. A mouse study is
# not evidence of a perturbation in people; a cell study is neither.
_FORBIDDEN: dict[EvidenceLevel, set[str]] = {
    EvidenceLevel.MOUSE: {"perturbation_in_human", "human_genetics"},
    EvidenceLevel.IN_VITRO: {"perturbation_in_human", "perturbation_in_animal", "human_genetics"},
}


def resolve_ref(ref: str) -> str | None:
    """``None`` if the citation resolves in the corpus, else why it does not."""
    match = _REF_RE.match(ref)
    if match is None:
        return f"malformed citation {ref!r} (expected pubmed:, pmc:, geo:, trial: or gwas:)"
    kind, source_id = match.group(1), match.group(2)
    found: Trial | Document | GeneticAssociation | None
    with session_scope() as session:
        if kind == "gwas":
            found = session.exec(
                select(GeneticAssociation).where(GeneticAssociation.study_accession == source_id)
            ).first()
        elif kind == "trial":
            found = session.exec(select(Trial).where(Trial.source_id == source_id)).first()
        else:
            found = session.exec(
                select(Document).where(
                    Document.source == _DOCUMENT_SOURCES[kind],
                    Document.source_id == source_id,
                )
            ).first()
    return None if found is not None else f"{ref} is not in the corpus"


def corpus_evidence_level(ref: str) -> EvidenceLevel | None:
    """What the corpus says a cited document is. ``None`` for trials and misses."""
    match = _REF_RE.match(ref)
    if match is None or match.group(1) in {"trial", "gwas"}:
        return None
    with session_scope() as session:
        document = session.exec(
            select(Document).where(
                Document.source == _DOCUMENT_SOURCES[match.group(1)],
                Document.source_id == match.group(2),
            )
        ).first()
        return classify_document(document) if document is not None else None


def _blank(value: object) -> bool:
    """True when a field is missing, is not text, or holds only whitespace."""
    return not isinstance(value, str) or not value.strip()


def check_structure(mechanisms: Iterable[Mechanism]) -> list[str]:
    """Problems that need no corpus: the chain, falsifiability and seals."""
    problems: list[str] = []
    seen: set[str] = set()
    for m in mechanisms:
        where = f"{m.id or '(no id)'}"
        if _blank(m.id) or not _ID_RE.match(m.id):
            problems.append(f"{where}: id must be kebab-case")
        if m.id in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(m.id)
        if m.status not in STATUSES:
            problems.append(f"{where}: unknown status {m.status!r}")
        if m.outcome not in OUTCOMES:
            problems.append(f"{where}: outcome must be one of {sorted(OUTCOMES)} (docs/success.md)")

        for level in (
            "title",
            "biological_state",
            "mechanistic_claim",
            "intervention",
            "experimental_outcome",
            "clinical_outcome",
            "uncertainty",
        ):
            if _blank(getattr(m, level)):
                problems.append(f"{where}: {level} is empty")
        for part in ("subtype", "tissue", "cell_type", "disease_stage"):
            if _blank(getattr(m.context, part)):
                problems.append(f"{where}: context.{part} is empty — a claim needs a context")

        problems.extend(_check_test(m, where))
        problems.extend(_check_evidence(m, where))

        if not m.competing:
            problems.append(f"{where}: no competing explanation — name the strongest rival")
        for i, c in enumerate(m.competing):
            if _blank(c.explanation) or _blank(c.distinguished_by):
                problems.append(
                    f"{where}: competing[{i}] needs an explanation and distinguished_by"
                )

        problems.extend(_check_date(m, where))
        problems.extend(_check_seal(m, where))
    return problems


def _check_test(m: Mechanism, where: str) -> list[str]:
    problems = []
    for part in ("question", "data", "if_correct", "if_incorrect", "decides"):
        if _blank(getattr(m.test, part)):
            problems.append(f"{where}: test.{part} is empty")
    if (
        not _blank(m.test.if_correct)
        and m.test.if_correct.strip() == str(m.test.if_incorrect).strip()
    ):
        problems.append(
            f"{where}: test.if_correct and test.if_incorrect are the same — it cannot fail"
        )
    # A test blocked on samples nobody has collected is a different thing from
    # one waiting on a download, and only the record can say which it is.
    if m.test.needs_new_data and _blank(m.test.new_data):
        problems.append(
            f"{where}: test.needs_new_data is set, so test.new_data must say what has to be"
            " collected and why it does not exist"
        )
    return problems


def _check_evidence(m: Mechanism, where: str) -> list[str]:
    problems = []
    for i, e in enumerate(m.evidence):
        if e.stance not in STANCES:
            problems.append(f"{where}: evidence[{i}] unknown stance {e.stance!r}")
        if e.causal_level not in CAUSAL_LADDER:
            problems.append(f"{where}: evidence[{i}] unknown causal level {e.causal_level!r}")
        if _blank(e.shows):
            problems.append(f"{where}: evidence[{i}] does not say what the source shows")
    if not m.supporting():
        problems.append(f"{where}: no supporting evidence")
    return problems


def _check_date(m: Mechanism, where: str) -> list[str]:
    try:
        date.fromisoformat(m.last_reviewed)
    except (TypeError, ValueError):
        return [f"{where}: last_reviewed {m.last_reviewed!r} is not an ISO date"]
    return []


def _check_seal(m: Mechanism, where: str) -> list[str]:
    sealed_statuses = {"sealed", "supported", "refuted"}
    if not isinstance(m.seal, dict):
        return [f"{where}: status {m.status!r} needs a seal"] if m.status in sealed_statuses else []
    if m.seal.get("sha256") != seal_hash(m):
        return [f"{where}: seal does not match the claim, context or test (they changed)"]
    return []


def verify(
    mechanisms: Iterable[Mechanism],
    *,
    resolve: Callable[[str], str | None] = resolve_ref,
    level_of: Callable[[str], EvidenceLevel | None] = corpus_evidence_level,
) -> list[str]:
    """Every problem found: structure, falsifiability, citations and causal levels."""
    records = list(mechanisms)
    problems = check_structure(records)
    for m in records:
        for i, e in enumerate(m.evidence):
            unresolved = resolve(e.ref)
            if unresolved is not None:
                problems.append(f"{m.id}: evidence[{i}] {unresolved}")
                continue
            level = level_of(e.ref)
            if level is not None and e.causal_level in _FORBIDDEN.get(level, set()):
                problems.append(
                    f"{m.id}: evidence[{i}] {e.ref} is {level.value} in the corpus, "
                    f"so it cannot carry {e.causal_level!r}"
                )
    return problems
