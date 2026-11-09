"""From an annotated text to what the model reads: marked mentions and entity pairs.

The model reads one stretch of text at a time -- an abstract with its title,
or one passage of a full text -- with every entity mention wrapped in a ``*``
on either side, and classifies every pair of entities in it into one of the
eight BioRED relation types or none. An entity is a concept, not a mention:
"IL-6" in the title and "interleukin 6" in the results are one entity, and
the model pools all its mentions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from vitiligo.sources.pubtator import AnnotatedDocument, Mention

LABELS = (
    "None",
    "Association",
    "Positive_Correlation",
    "Negative_Correlation",
    "Bind",
    "Cotreatment",
    "Comparison",
    "Drug_Interaction",
    "Conversion",
)
ENTITY_TYPES = ("Chemical", "Disease", "Gene", "Variant")

# The type pairs BioRED annotates relations between; any other pair is never
# a candidate. Species and cell lines are in no relation at all.
RELATABLE = frozenset(
    {
        ("Chemical", "Disease"),
        ("Chemical", "Gene"),
        ("Chemical", "Chemical"),
        ("Chemical", "Variant"),
        ("Disease", "Gene"),
        ("Disease", "Variant"),
        ("Gene", "Gene"),
        ("Gene", "Variant"),
        ("Variant", "Variant"),
    }
)
ALLOWED_LABELS_BY_TYPE_PAIR: dict[tuple[str, str], tuple[str, ...]] = {
    ("Chemical", "Chemical"): LABELS,
    ("Chemical", "Disease"): (
        "None",
        "Association",
        "Positive_Correlation",
        "Negative_Correlation",
    ),
    ("Chemical", "Gene"): (
        "None",
        "Association",
        "Positive_Correlation",
        "Negative_Correlation",
        "Bind",
        "Cotreatment",
    ),
    ("Chemical", "Variant"): (
        "None",
        "Association",
        "Positive_Correlation",
        "Negative_Correlation",
    ),
    ("Disease", "Gene"): (
        "None",
        "Association",
        "Positive_Correlation",
        "Negative_Correlation",
    ),
    ("Disease", "Variant"): (
        "None",
        "Association",
        "Positive_Correlation",
        "Negative_Correlation",
    ),
    ("Gene", "Gene"): (
        "None",
        "Association",
        "Positive_Correlation",
        "Negative_Correlation",
        "Bind",
    ),
    ("Gene", "Variant"): ("None", "Association"),
    ("Variant", "Variant"): ("None", "Association"),
}
MARKER = "*"
WINDOW = 512  # tokens an encoder reads at once, its two special tokens included
STRIDE = 256
SNIPPET_LIMIT = 400


class Tokenizer(Protocol):
    def __call__(self, text: str, **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    concepts: tuple[str, ...]
    type: str


@dataclass
class Unit:
    """One input: a text, the entity mentions in it, and the known relations."""

    doc_id: str
    section: str
    text: str
    spans: list[Span]
    labels: dict[tuple[str, str], str] = field(default_factory=dict)
    target_type_pairs: frozenset[tuple[str, str]] | None = None


@dataclass
class Encoded:
    unit: Unit
    input_ids: list[int]  # no special tokens; the model adds them per window
    entities: list[str]  # concept ids, in the order the positions below follow
    entity_types: list[int]
    mention_tokens: list[list[int]]  # per entity, the token of each mention's opening marker
    pairs: list[tuple[int, int]]
    labels: list[int]
    mention_end_tokens: list[list[int]] = field(default_factory=list)
    pair_features: list[tuple[int, int, int, int]] = field(default_factory=list)


def concepts_of(identifier: str, kind: str) -> tuple[str, ...]:
    """The concepts a mention names.

    A gene or disease mention may name several ("3172,3651,6927" in BioRED,
    "7306;1638" in PubTator). A variant's identifier is one concept even
    though it contains both separators.
    """
    if kind == "Variant":
        return (identifier,)
    return tuple(part for part in re.split(r"[,;]", identifier) if part)


def pair_key(a: str, a_type: str, b: str, b_type: str) -> tuple[str, str]:
    """The same key for A-B and B-A: BioRED's relations have no direction."""
    first, second = sorted(((a_type, a), (b_type, b)))
    return first[1], second[1]


def _spans(mentions: Iterable[Mention], start: int, end: int) -> list[Span]:
    spans: list[Span] = []
    for mention in mentions:
        kind = mention.concept.type
        if kind not in ENTITY_TYPES:
            continue
        begin = mention.offset - start
        if begin < 0 or mention.offset + len(mention.text) > end:
            continue
        spans.append(
            Span(
                begin,
                begin + len(mention.text),
                concepts_of(mention.concept.identifier, kind),
                kind,
            )
        )
    spans.sort(key=lambda s: (s.start, -(s.end - s.start)))
    kept: list[Span] = []
    for span in spans:  # an overlapping mention cannot be marked; the longer one is kept
        if kept and span.start < kept[-1].end:
            continue
        kept.append(span)
    return kept


def document_unit(
    doc: AnnotatedDocument,
    *,
    min_score: float = 0.5,
    target_type_pairs: frozenset[tuple[str, str]] | None = None,
) -> Unit:
    """A title and abstract as one input, with the relations asserted in it."""
    text = ""
    for passage in doc.passages:
        text = text.ljust(passage.offset) + passage.text
    spans = _spans(doc.mentions, 0, len(text))
    kinds = {c: s.type for s in spans for c in s.concepts}
    labels: dict[tuple[str, str], str] = {}
    for relation in doc.relations:
        a, b = relation.first.identifier, relation.second.identifier
        if relation.score < min_score or a not in kinds or b not in kinds:
            continue
        pkey = pair_key(a, kinds[a], b, kinds[b])
        if relation.type == "Ignore" and pkey in labels:
            continue
        labels[pkey] = relation.type
    if target_type_pairs is None and hasattr(doc, "target_type_pairs"):
        target_type_pairs = doc.target_type_pairs
    return Unit(doc.pmid, "abstract", text, spans, labels, target_type_pairs=target_type_pairs)


def passage_units(doc: AnnotatedDocument, *, skip: frozenset[str] = frozenset()) -> Iterator[Unit]:
    """Each passage of a full text as its own input, if it holds two entities."""
    for passage in doc.passages:
        if passage.section in skip:
            continue
        spans = _spans(doc.mentions, passage.offset, passage.offset + len(passage.text))
        if len({c for s in spans for c in s.concepts}) >= 2:
            yield Unit(doc.pmid, passage.section, passage.text, spans)


def _dist_bucket(gap: int) -> int:
    if gap <= 0:
        return 0
    if gap <= 3:
        return 1
    if gap <= 7:
        return 2
    if gap <= 15:
        return 3
    if gap <= 31:
        return 4
    if gap <= 63:
        return 5
    if gap <= 127:
        return 6
    return 7


def encode(unit: Unit, tokenizer: Tokenizer) -> Encoded | None:
    """The unit as token ids, with each mention's marker located among them.

    Returns None when the unit has no candidate pair.
    """
    pieces: list[str] = []
    markers: list[tuple[int, int, Span]] = []
    cursor = 0
    length = 0
    for span in unit.spans:
        before = unit.text[cursor : span.start] + " "
        pieces.append(before)
        length += len(before)
        open_pos = length
        mention_str = unit.text[span.start : span.end]
        close_pos = length + len(MARKER) + 1 + len(mention_str) + 1
        markers.append((open_pos, close_pos, span))
        piece = f"{MARKER} {mention_str} {MARKER} "
        pieces.append(piece)
        length += len(piece)
        cursor = span.end
    pieces.append(unit.text[cursor:])
    marked = "".join(pieces)

    encoding = tokenizer(marked, add_special_tokens=False, return_offsets_mapping=True)
    input_ids = [int(i) for i in encoding["input_ids"]]
    token_at: dict[int, int] = {}
    for index, (begin, finish) in enumerate(encoding["offset_mapping"]):
        for position in range(int(begin), int(finish)):
            token_at.setdefault(position, index)

    order: dict[str, int] = {}
    entity_types: list[int] = []
    mention_tokens: list[list[int]] = []
    mention_end_tokens: list[list[int]] = []
    entity_char_spans: list[list[Span]] = []
    for open_pos, close_pos, span in markers:
        token = token_at.get(open_pos)
        if token is None:
            continue
        end_token = token_at.get(close_pos, token)
        for concept in span.concepts:
            if concept not in order:
                order[concept] = len(order)
                entity_types.append(ENTITY_TYPES.index(span.type))
                mention_tokens.append([])
                mention_end_tokens.append([])
                entity_char_spans.append([])
            ent_idx = order[concept]
            mention_tokens[ent_idx].append(token)
            mention_end_tokens[ent_idx].append(max(token, end_token))
            entity_char_spans[ent_idx].append(span)

    num_tokens = max(1, len(input_ids))
    entities = list(order)
    pairs: list[tuple[int, int]] = []
    labels: list[int] = []
    pair_features: list[tuple[int, int, int, int]] = []
    for i, a in enumerate(entities):
        for j in range(i + 1, len(entities)):
            b = entities[j]
            a_type, b_type = ENTITY_TYPES[entity_types[i]], ENTITY_TYPES[entity_types[j]]
            if tuple(sorted((a_type, b_type))) not in RELATABLE:
                continue
            key = pair_key(a, a_type, b, b_type)
            first, second = (i, j) if key == (a, b) else (j, i)
            pairs.append((first, second))
            if (
                unit.target_type_pairs is not None
                and tuple(sorted((a_type, b_type))) not in unit.target_type_pairs
            ):
                labels.append(-100)
            else:
                raw_label = unit.labels.get(key, "None")
                labels.append(-100 if raw_label == "Ignore" else LABELS.index(raw_label))

            spans_f = list(
                zip(
                    mention_tokens[first],
                    mention_end_tokens[first],
                    entity_char_spans[first],
                    strict=True,
                )
            )
            spans_s = list(
                zip(
                    mention_tokens[second],
                    mention_end_tokens[second],
                    entity_char_spans[second],
                    strict=True,
                )
            )
            (sf, ef, cf), (ss, es, cs) = min(
                ((xf, xs) for xf in spans_f for xs in spans_s),
                key=lambda p: abs(p[0][0] - p[1][0]),
            )
            lo_end, hi_start = min(ef, es), max(sf, ss)
            gap = max(0, hi_start - lo_end - 1)
            if lo_end + 1 < hi_start:
                b_start, b_end = lo_end + 1, min(num_tokens, hi_start)
            else:
                b_start = max(0, min(sf, ss) - 4)
                b_end = min(num_tokens, max(ef, es) + 5)
            if b_end <= b_start:
                b_start = max(0, min(sf, ss))
                b_end = min(num_tokens, b_start + 1)

            c_lo, c_hi = min(cf.end, cs.end), max(cf.start, cs.start)
            between_txt = unit.text[c_lo:c_hi] if c_lo < c_hi else ""
            same_sent = not bool(re.search(r"[.!?]\s|\n", between_txt))
            if not same_sent:
                co_sent = 0
            elif cf.start <= cs.start:
                co_sent = 2
            else:
                co_sent = 1
            pair_features.append((b_start, b_end, _dist_bucket(gap), co_sent))

    if not pairs:
        return None
    return Encoded(
        unit,
        input_ids,
        entities,
        entity_types,
        mention_tokens,
        pairs,
        labels,
        mention_end_tokens,
        pair_features,
    )


def window_starts(length: int, size: int = WINDOW - 2, stride: int = STRIDE) -> list[int]:
    """Where each window begins, so that every token is in at least one."""
    if length <= size:
        return [0]
    starts = list(range(0, length - size, stride))
    return [*starts, length - size]


def snippet(text: str, first: Sequence[Span], second: Sequence[Span]) -> str:
    """The sentences that carry the closest mentions of the two entities."""
    a, b = min(
        ((x, y) for x in first for y in second),
        key=lambda pair: abs(pair[0].start - pair[1].start),
    )
    start, end = min(a.start, b.start), max(a.end, b.end)
    begin = max((m.end() for m in re.finditer(r"[.!?]\s", text[:start])), default=0)
    stop = re.search(r"[.!?](\s|$)", text[end:])
    finish = end + stop.end() if stop else len(text)
    found = text[begin:finish].strip()
    return found if len(found) <= SNIPPET_LIMIT else found[: SNIPPET_LIMIT - 1] + "…"
