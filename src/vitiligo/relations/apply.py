"""Reading the bodies of the full texts with the trained model.

PubTator annotates every entity in the 2,712 full texts it holds and reads
relations only out of their abstracts. This reads the rest, a passage at a
time, using PubTator's own entity annotations, and returns each paper as an
annotated document whose relations the graph loader can check exactly as it
checks PubTator's.

Passages are skipped when PubTator already read them (the title and
abstract) or when they are not the paper's own claims: the reference list
is other papers' titles, and author contributions, competing interests,
funding, abbreviations, keyword lists, supplementary listings and replies
to reviewers assert nothing about biology.

A pair the model finds in several passages of one paper is one relation, from
the passage it was surest of, so a paper counts once per edge however often
it repeats itself.

What the model is trusted with was measured by reading 120 of its relations,
drawn at random from everything it read, against the sentences they came
from: 82 were right (68%), where PubTator's own abstract relations were right
about 85-90% of the time. Four things separated the wrong ones:

- a score below 0.8, right 26 times in 46 (56 in 74 at or above it);
- tables and figure captions, 5 in 12: a row of a table is not a sentence;
- its combinations, 2 in 6 (0 in 4 in a second sample): drugs in a list, a
  switch from one to another, a comparison;
- a drug treating a disease other than vitiligo, 7 in 13 (1 in 4): a case
  history's "she was not on medications except furosemide".

Without them 48 of 61 were right (79%), and 17 of 20 where vitiligo is one
end -- in the sample the rule was drawn from. A fresh sample of 60, read after
the rule was set, had 45 right (75%), 15 of 17 where vitiligo is one end.
Its edges carry a confidence below PubTator's for the same reason.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from typing import TYPE_CHECKING

from vitiligo.graph.literature_seed import Node
from vitiligo.graph.normalize import VITILIGO_ENTITY_NAME
from vitiligo.relations.data import (
    ENTITY_TYPES,
    LABELS,
    Encoded,
    Span,
    Tokenizer,
    encode,
    passage_units,
    snippet,
)
from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Relation
from vitiligo.storage.models import RelationKind

if TYPE_CHECKING:
    from vitiligo.relations.model import RelationModel

READ_BY_PUBTATOR = frozenset({"TITLE", "ABSTRACT", "title", "abstract"})
NOT_CLAIMS = frozenset(
    {"REF", "ABBR", "REVIEW_INFO", "SUPPL", "COMP_INT", "AUTH_CONT", "ACK_FUND", "KEYWORD"}
)
UNRELIABLE = frozenset({"TABLE", "FIG"})
SKIP = READ_BY_PUBTATOR | NOT_CLAIMS | UNRELIABLE
MIN_SCORE = 0.8
CONFIDENCE = 0.4


def trusted(subject: Node, predicate: RelationKind, obj: Node) -> bool:
    """Whether the model is trusted with this kind of claim (see above)."""
    if predicate == RelationKind.COMBINED_WITH:
        return False
    return predicate != RelationKind.TREATS or obj.name == VITILIGO_ENTITY_NAME


def paper_relations(
    encoded: Sequence[Encoded],
    probabilities: Sequence[Sequence[Sequence[float]]],
    names: dict[str, str],
) -> list[Relation]:
    """One relation per entity pair the model found, from its surest passage.

    ``probabilities`` holds, for each input, a row over LABELS per candidate
    pair, with the tuned bias already applied; a pair is a relation when its
    likeliest label is not "None".
    """
    best: dict[tuple[str, str], Relation] = {}
    for item, rows in zip(encoded, probabilities, strict=True):
        spans: dict[str, list[Span]] = {}
        for span in item.unit.spans:
            for concept in span.concepts:
                spans.setdefault(concept, []).append(span)
        for (i, j), row in zip(item.pairs, rows, strict=True):
            label = max(range(len(row)), key=row.__getitem__)
            if not label:
                continue
            a, b = item.entities[i], item.entities[j]
            # A gene known only from a mention naming several ("7306;1638") has no
            # name of its own to give a node.
            if a not in names or b not in names:
                continue
            key = (min(a, b), max(a, b))
            if key in best and best[key].score >= row[label]:
                continue
            best[key] = Relation(
                type=LABELS[label],
                score=float(row[label]),
                first=Concept(ENTITY_TYPES[item.entity_types[i]], a, names[a]),
                second=Concept(ENTITY_TYPES[item.entity_types[j]], b, names[b]),
                section=item.unit.section,
                snippet=snippet(item.unit.text, spans[a], spans[b]),
            )
    return list(best.values())


def read_documents(
    model: RelationModel,
    tokenizer: Tokenizer,
    bias: float,
    documents: Iterable[AnnotatedDocument],
    *,
    skip: frozenset[str] = SKIP,
    batch_size: int = 16,
) -> Iterator[AnnotatedDocument]:
    """Each paper with the relations the model read in its passages.

    ``skip`` names the sections left unread; the default suits PubTator's
    full texts.
    """
    from vitiligo.relations.train import logits_for

    for doc in documents:
        encoded = [
            e for u in passage_units(doc, skip=skip) if (e := encode(u, tokenizer)) is not None
        ]
        if not encoded:
            continue
        probabilities = []
        for logits in logits_for(model, encoded, batch_size):
            shifted = logits.clone()
            shifted[:, 0] += bias
            probabilities.append(shifted.softmax(dim=-1).tolist())
        names = {m.concept.identifier: m.concept.name for m in doc.mentions}
        relations = paper_relations(encoded, probabilities, names)
        if relations:
            yield AnnotatedDocument(
                pmid=doc.pmid,
                pmcid=doc.pmcid,
                mentions=doc.mentions,
                relations=tuple(relations),
            )
