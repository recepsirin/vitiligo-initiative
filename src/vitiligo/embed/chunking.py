"""Split a paper's full text into passages small enough to embed.

Search covers titles and abstracts, which is why a result that is only
discussed in a paper's Results section cannot be found. The body is already
in the corpus; it is simply too long to embed as one vector, because a single
embedding of 20,000 characters averages away whatever made the passage
specific.

So the body is cut into passages. Three rules:

- **Cut at paragraph boundaries.** A passage that starts mid-sentence embeds
  badly, and the paragraph is the unit authors already write in. A paragraph
  longer than the limit is split at sentence ends instead.
- **Overlap a little.** A fact stated across a paragraph break would
  otherwise be lost at the seam, so each passage repeats the tail of the one
  before it.
- **Keep offsets and the section name.** A hit has to be quotable: the
  passage is identified by where it sits in the source text, not by a copy of
  it, so nothing is stored twice and a snippet can be sliced out on demand.

The text handed in is ``raw_metadata["full_text"]`` as the PMC parser built
it: sections introduced by a ``## Name`` heading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TARGET_CHARS = 900
OVERLAP_CHARS = 150
MIN_CHARS = 120

_HEADING = re.compile(r"^## (?P<name>.+)$", re.MULTILINE)
# A sentence end followed by a capital letter, digit or opening bracket.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


@dataclass(frozen=True)
class Chunk:
    """One passage, and where it came from in the source text."""

    index: int
    section: str | None
    char_start: int
    char_end: int
    text: str


def _sections(text: str) -> list[tuple[str | None, int, int]]:
    """``(name, start, end)`` for each ``## Section``; one unnamed span if there are none."""
    headings = list(_HEADING.finditer(text))
    if not headings:
        return [(None, 0, len(text))]
    spans: list[tuple[str | None, int, int]] = []
    if headings[0].start() > 0:
        spans.append((None, 0, headings[0].start()))
    for i, match in enumerate(headings):
        body_start = match.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        spans.append((match.group("name").strip(), body_start, body_end))
    return spans


def _paragraphs(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Offsets of the non-empty paragraphs between ``start`` and ``end``."""
    out: list[tuple[int, int]] = []
    cursor = start
    for part in re.split(r"\n\s*\n", text[start:end]):
        begin = cursor
        cursor += len(part)
        stripped = part.strip()
        if stripped:
            lead = len(part) - len(part.lstrip())
            out.append((begin + lead, begin + lead + len(stripped)))
        cursor += 2  # the separator that re.split consumed
    return out


def _split_long(text: str, start: int, end: int, limit: int) -> list[tuple[int, int]]:
    """Break one over-long paragraph at sentence ends, falling back to hard cuts."""
    pieces: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        if end - cursor <= limit:
            pieces.append((cursor, end))
            break
        window = text[cursor : cursor + limit]
        breaks = [m.start() for m in _SENTENCE_END.finditer(window)]
        cut = cursor + (breaks[-1] if breaks else limit)
        pieces.append((cursor, cut))
        cursor = cut
        while cursor < end and text[cursor].isspace():
            cursor += 1
    return pieces


def chunk_text(
    text: str,
    *,
    target_chars: int = TARGET_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
    min_chars: int = MIN_CHARS,
) -> list[Chunk]:
    """Cut ``text`` into overlapping passages that keep their section and offsets."""
    if not text or not text.strip():
        return []

    spans: list[tuple[str | None, int, int]] = []
    for section, start, end in _sections(text):
        pending: list[tuple[int, int]] = []
        for para_start, para_end in _paragraphs(text, start, end):
            pieces = (
                _split_long(text, para_start, para_end, target_chars)
                if para_end - para_start > target_chars
                else [(para_start, para_end)]
            )
            for piece_start, piece_end in pieces:
                if pending and (piece_end - pending[0][0]) > target_chars:
                    spans.append((section, pending[0][0], pending[-1][1]))
                    pending = _overlap_tail(text, spans[-1], overlap_chars, piece_start)
                pending.append((piece_start, piece_end))
        if pending:
            spans.append((section, pending[0][0], pending[-1][1]))

    chunks = []
    for section, begin, finish in spans:
        body = text[begin:finish].strip()
        if body:
            lead = len(text[begin:finish]) - len(text[begin:finish].lstrip())
            chunks.append(Chunk(0, section, begin + lead, begin + lead + len(body), body))

    kept = [c for c in chunks if len(c.text) >= min_chars] or chunks[:1]
    return [Chunk(i, c.section, c.char_start, c.char_end, c.text) for i, c in enumerate(kept)]


def _overlap_tail(
    text: str, previous: tuple[str | None, int, int], overlap_chars: int, next_start: int
) -> list[tuple[int, int]]:
    """Repeat the tail of the passage just closed, so a fact at the seam survives.

    The tail starts at the next word boundary, because a passage beginning
    with half a word embeds worse than one beginning a little later.
    """
    if overlap_chars <= 0:
        return []
    _section, begin, finish = previous
    tail = max(begin, finish - overlap_chars)
    while tail < finish and not text[tail].isspace():
        tail += 1
    while tail < finish and text[tail].isspace():
        tail += 1
    return [(tail, finish)] if tail < next_start else []


def snippet(text: str, chunk_start: int, chunk_end: int, limit: int = 320) -> str:
    """A short, readable quote from a passage, for showing next to a hit."""
    body = " ".join(text[chunk_start:chunk_end].split())
    if len(body) <= limit:
        return body
    cut = body.rfind(" ", 0, limit)
    return body[: cut if cut > 0 else limit] + "…"
