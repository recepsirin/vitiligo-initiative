"""Trials the literature names but the registries will not give us.

Most vitiligo trials run in India, China and Iran, and their registries —
CTRI, ChiCTR, IRCT — publish no API we may use. WHO's ICTRP aggregates them
but its search refuses programmatic access, so those trials are invisible to
every ingest we have.

They are not invisible to the corpus. A paper reporting a trial prints its
registration number, and we hold 2,587 full texts. Scanning them recovers
the identifier, the paper that describes the trial, and the sentence around
it — enough to read the evidence and to ask the registry by hand.

The filter that matters is proximity. A review of cell-sheet therapies cited
sixteen Japanese trial numbers while mentioning vitiligo twice, in passing;
none of them was a vitiligo trial. So an identifier counts only when the
paper's title is about vitiligo, or the word appears within
``CONTEXT_WINDOW`` characters of the number itself.

What comes out is a lead, not a trial record: the registry's own fields —
arms, outcomes, dates, results — are not here, and nothing in this report
should be counted as evidence until the registry entry is read.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from vitiligo.storage import Document

# How far from a registration number the word "vitiligo" may sit.
CONTEXT_WINDOW = 400
# How much of the sentence around it to keep, for judging the lead.
CONTEXT_CHARS = 150

# Registry identifier formats, as the registries print them.
REGISTRY_PATTERNS: dict[str, re.Pattern[str]] = {
    "CTRI (India)": re.compile(r"CTRI/\d{4}/\d{2}/\d{6,}", re.IGNORECASE),
    "ChiCTR (China)": re.compile(r"ChiCTR[-A-Za-z]{0,4}\d{6,}", re.IGNORECASE),
    "IRCT (Iran)": re.compile(r"IRCT\d*[A-Z0-9]*N\d+", re.IGNORECASE),
    "UMIN (Japan)": re.compile(r"UMIN\d{9}", re.IGNORECASE),
    "jRCT (Japan)": re.compile(r"jRCTs?\d{9,}", re.IGNORECASE),
    "DRKS (Germany)": re.compile(r"DRKS\d{8}", re.IGNORECASE),
    "ANZCTR (Australia, NZ)": re.compile(r"ACTRN\d{14}", re.IGNORECASE),
    "CRIS (Korea)": re.compile(r"\bKCT\d{7}\b", re.IGNORECASE),
    "TCTR (Thailand)": re.compile(r"\bTCTR\d{11}\b", re.IGNORECASE),
    "PACTR (Africa)": re.compile(r"PACTR\d{12,}", re.IGNORECASE),
    "ReBEC (Brazil)": re.compile(r"\bRBR-[a-z0-9]{6,}\b", re.IGNORECASE),
    "NTR (Netherlands)": re.compile(r"\bNTR\d{3,5}\b"),
    "ISRCTN": re.compile(r"ISRCTN\d{8}", re.IGNORECASE),
}


@dataclass(frozen=True)
class CitedTrial:
    """One registration number found in a paper, with where it was found."""

    registry: str
    identifier: str
    cited_by: str
    paper_title: str
    context: str
    # True when the citing paper's own title names the disease. Those leads
    # are almost certainly vitiligo trials; the rest may be a study of several
    # skin diseases that happens to include it, so the two are not mixed.
    paper_title_names_disease: bool = False


def document_text(document: Document) -> str:
    """Title, abstract and body, which is where a registration number appears."""
    body = (document.raw_metadata or {}).get("full_text") or ""
    return f"{document.title or ''}\n{document.abstract or ''}\n{body}"


def _reference(document: Document) -> str:
    source = document.source.value if hasattr(document.source, "value") else str(document.source)
    return f"{source}:{document.source_id}"


def find_in_text(
    text: str,
    *,
    title_is_about_vitiligo: bool,
    term: str = "vitiligo",
    window: int = CONTEXT_WINDOW,
) -> Iterator[tuple[str, str, str]]:
    """``(registry, identifier, context)`` for each number the text ties to the disease."""
    needle = term.lower()
    for registry, pattern in REGISTRY_PATTERNS.items():
        for match in pattern.finditer(text):
            near = text[max(0, match.start() - window) : match.end() + window].lower()
            if not title_is_about_vitiligo and needle not in near:
                continue
            context = text[max(0, match.start() - CONTEXT_CHARS) : match.end() + CONTEXT_CHARS]
            yield registry, match.group(0).upper().replace(" ", ""), " ".join(context.split())


def scan(
    documents: Iterable[Document],
    known_identifiers: Iterable[str] = (),
    *,
    term: str = "vitiligo",
    window: int = CONTEXT_WINDOW,
) -> list[CitedTrial]:
    """Registration numbers in the corpus that are not already held as trials.

    The first paper to cite an identifier is the one reported, so a number
    repeated across a field's literature appears once.
    """
    known = {i.upper() for i in known_identifiers}
    seen: dict[str, CitedTrial] = {}
    for document in documents:
        text = document_text(document)
        if term.lower() not in text.lower():
            continue
        title_match = term.lower() in (document.title or "").lower()
        for registry, identifier, context in find_in_text(
            text, title_is_about_vitiligo=title_match, term=term, window=window
        ):
            if identifier in known or identifier in seen:
                continue
            seen[identifier] = CitedTrial(
                registry=registry,
                identifier=identifier,
                cited_by=_reference(document),
                paper_title=(document.title or "").strip(),
                context=context,
                paper_title_names_disease=title_match,
            )
    return sorted(seen.values(), key=lambda t: (t.registry, t.identifier))


def split_by_confidence(
    trials: Iterable[CitedTrial],
) -> tuple[list[CitedTrial], list[CitedTrial]]:
    """``(solid, needs_checking)``.

    A lead is solid when the citing paper's title is about the disease. The
    rest were kept because the word sits near the number, which also catches a
    study of several skin diseases that enrolled vitiligo patients among
    others — a real registration, but not a vitiligo trial.
    """
    items = list(trials)
    return (
        [t for t in items if t.paper_title_names_disease],
        [t for t in items if not t.paper_title_names_disease],
    )


def by_registry(trials: Iterable[CitedTrial]) -> dict[str, list[CitedTrial]]:
    """Leads grouped by the registry that holds them."""
    grouped: dict[str, list[CitedTrial]] = {}
    for trial in trials:
        grouped.setdefault(trial.registry, []).append(trial)
    return dict(sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])))
