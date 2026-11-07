"""Finding entities in text PubTator never annotated, in PubTator's own words.

PubTator annotates PubMed and PMC. The Crossref papers, the registry
summaries and the NIH project abstracts are none of those, so their
chemicals, diseases and genes are found with a lexicon of the surface forms
PubTator normalised in the abstracts it did annotate here -- "8-MOP" as
methoxsalen -- keeping a form only when

- it named one concept at least nine times in ten, and at least twice; and
- PubTator annotated it in at least 70% of the places it occurs. A word
  PubTator marks only in some contexts ("lesions", "pigmentation") fails
  this, and was most of what the lexicon got wrong without it: disease
  precision rose from 0.47 to 0.95, chemical from 0.83 to 0.93.

Against PubTator's own annotations of 300 abstracts the lexicon was not
built from: chemicals precision 0.93, recall 0.78; diseases 0.95 and 0.80;
genes 0.85 and 0.36. Genes are written in too many ways for a lexicon to find
most of them, so the relations they are in are mostly missed, not invented.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Mention, Passage

TYPES = frozenset({"Chemical", "Disease", "Gene"})
MIN_SHARE = 0.9
MIN_RATE = 0.7
_TOKEN = re.compile(r"[A-Za-z0-9][\w\-/+.]*[\w+]|[A-Za-z0-9]")


def _key(text: str) -> str:
    """Short forms keep their case: CAT the gene is not "cat"."""
    return text if len(text) <= 4 else text.lower()


@dataclass(frozen=True)
class Entry:
    concept: Concept
    annotated: int  # how many times PubTator marked this form


class Lexicon:
    def __init__(self, entries: dict[str, Entry]) -> None:
        self._entries = entries
        self._longest = max((len(form.split()) for form in entries), default=1)

    def __len__(self) -> int:
        return len(self._entries)

    def matches(self, text: str) -> Iterator[tuple[int, int, Entry]]:
        """Longest-first matches over the text's tokens, never overlapping."""
        tokens = [(m.start(), m.end()) for m in _TOKEN.finditer(text)]
        i = 0
        while i < len(tokens):
            for n in range(min(self._longest, len(tokens) - i), 0, -1):
                start, end = tokens[i][0], tokens[i + n - 1][1]
                entry = self._entries.get(_key(text[start:end]))
                if entry is not None:
                    yield start, end, entry
                    i += n
                    break
            else:
                i += 1

    def without_rare(self, texts: Iterable[str]) -> Lexicon:
        """Only the forms PubTator marked in at least MIN_RATE of their occurrences."""
        occurs: Counter[str] = Counter()
        for text in texts:
            for start, end, _ in self.matches(text):
                occurs[_key(text[start:end])] += 1
        return Lexicon(
            {
                form: entry
                for form, entry in self._entries.items()
                if occurs[form] and entry.annotated / occurs[form] >= MIN_RATE
            }
        )

    def annotate(self, doc_id: str, sections: Sequence[tuple[str, str]]) -> AnnotatedDocument:
        """The document's (section, text) passages, with every entity found in each."""
        passages: list[Passage] = []
        mentions: list[Mention] = []
        offset = 0
        for section, text in sections:
            passages.append(Passage(section, offset, text))
            # The words after a mention travel with it, as in a PubTator export:
            # "CO2" followed by "laser" is a laser, not carbon dioxide.
            mentions.extend(
                Mention(
                    entry.concept, text[start:end], section, offset + start, text[end : end + 24]
                )
                for start, end, entry in self.matches(text)
            )
            offset += len(text) + 1
        return AnnotatedDocument(
            pmid=doc_id,
            pmcid=None,
            mentions=tuple(mentions),
            relations=(),
            passages=tuple(passages),
        )


def full_text(doc: AnnotatedDocument) -> str:
    text = ""
    for passage in doc.passages:
        text = text.ljust(passage.offset) + passage.text
    return text


def build(documents: Iterable[AnnotatedDocument]) -> Lexicon:
    """The lexicon of PubTator's surface forms in these documents, filtered."""
    documents = list(documents)
    concepts: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    names: dict[tuple[str, str], str] = {}
    for doc in documents:
        for mention in doc.mentions:
            concept = mention.concept
            # A mention naming several genes ("7306;1638") is no one form's meaning.
            if concept.type not in TYPES or ";" in concept.identifier:
                continue
            concepts[_key(mention.text.strip())][(concept.type, concept.identifier)] += 1
            names.setdefault((concept.type, concept.identifier), concept.name)
    entries: dict[str, Entry] = {}
    for form, counts in concepts.items():
        (kind, identifier), n = counts.most_common(1)[0]
        total = sum(counts.values())
        if len(form) >= 3 and n >= 2 and n / total >= MIN_SHARE:
            entries[form] = Entry(Concept(kind, identifier, names[(kind, identifier)]), total)
    return Lexicon(entries).without_rare(full_text(d) for d in documents)
