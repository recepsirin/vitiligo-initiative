"""How a relation extractor is scored: BioRED's relation-type evaluation.

A prediction counts when its entity pair and its relation type both match a
gold relation; precision, recall and F1 are micro-averaged over those. The
same relations with their types forgotten say whether the pair was found at
all.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from vitiligo.sources.pubtator import AnnotatedDocument

Key = tuple[str, str, str, str]  # document, concept, concept, relation type


@dataclass(frozen=True)
class Score:
    precision: float
    recall: float
    f1: float
    correct: int
    predicted: int
    gold: int


def score(gold: set[Key], predicted: set[Key]) -> Score:
    correct = len(gold & predicted)
    precision = correct / len(predicted) if predicted else 0.0
    recall = correct / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return Score(precision, recall, f1, correct, len(predicted), len(gold))


def untyped(keys: set[Key]) -> set[Key]:
    """The same relations with their type forgotten: was the pair found at all."""
    return {(d, a, b, "") for d, a, b, _ in keys}


def gold_keys(documents: Iterable[AnnotatedDocument]) -> set[Key]:
    """Every relation the annotators recorded, including any no candidate could reach."""
    keys: set[Key] = set()
    for doc in documents:
        for relation in doc.relations:
            a, b = sorted((relation.first.identifier, relation.second.identifier))
            keys.add((doc.pmid, a, b, relation.type))
    return keys
