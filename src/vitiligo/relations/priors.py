"""Drug priors PubTator never tags, found by their names.

PubTator tags no mention of six of the corpus's Open Targets drug priors in the
documents that name them -- afamelanotide in 21, etanercept in 11, povorcitinib
in 6, abatacept, ifidancitinib and ordesekimab in one each -- so no relation of
theirs reached the graph, and the candidate report scored none of their papers.
A prior is a drug by definition and its names are curated, so where PubTator
never tags one, its name marks it, and the relation model reads the passage as
it reads any other. Only the relations a prior takes part in are kept: the rest
PubTator, or the model, read before.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from vitiligo.sources.mesh import normalise
from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Mention
from vitiligo.storage import Prior

# The identifier a prior's concept carries: "PRIOR:" and its Open Targets id.
PREFIX = "PRIOR:"
# A shorter name ("TNF") is more often something else than the drug.
_MIN_NAME = 5


def untagged_priors(
    priors: Iterable[Prior], documents: Iterable[AnnotatedDocument]
) -> dict[str, Concept]:
    """Each written form of a prior no document has PubTator tag, with its concept.

    A prior counts as tagged when PubTator marks any of its names, or the drug
    its salt is named after, as a chemical anywhere: "RITLECITINIB TOSYLATE" is
    ritlecitinib, which PubTator tags 579 times. Its forms are then left to it.
    """
    concepts: dict[str, Concept] = {}
    claims: dict[str, str] = {}  # a form or a stem PubTator may tag -> the prior's id
    for prior in priors:
        concept = Concept(type="Chemical", identifier=PREFIX + prior.source_id, name=prior.name)
        forms = {normalise(name) for name in [prior.name, *(prior.synonyms or [])]}
        forms = {form for form in forms if len(form) >= _MIN_NAME}
        stem = next((w for w in normalise(prior.name).split() if len(w) >= _MIN_NAME), "")
        for form in forms:
            concepts.setdefault(form, concept)
        for written in (*forms, stem):
            if written:
                claims.setdefault(written, concept.identifier)
    tagged: set[str] = set()
    for doc in documents:
        for mention in doc.mentions:
            if mention.concept.type == "Chemical" and normalise(mention.text) in claims:
                tagged.add(claims[normalise(mention.text)])
    return {form: c for form, c in concepts.items() if c.identifier not in tagged}


def with_priors(doc: AnnotatedDocument, forms: dict[str, Concept]) -> AnnotatedDocument | None:
    """The document with a mention for each place it names an untagged prior.

    None when it names none. PubTator's own mentions stay, as the other end of
    every relation read here, and a name inside one of them is left to it:
    "NDP-alpha-MSH" holds PubTator's gene alpha-MSH.
    """
    if not forms:
        return None
    pattern = re.compile(
        r"(?<![a-z0-9])("
        + "|".join(map(re.escape, sorted(forms, key=len, reverse=True)))
        + r")(?![a-z0-9])"
    )
    taken = [(m.offset, m.offset + len(m.text)) for m in doc.mentions]
    added: list[Mention] = []
    for passage in doc.passages:
        text = passage.text
        lowered = normalise_spaced(text)
        for match in pattern.finditer(lowered):
            start, end = match.span()
            at, until = passage.offset + start, passage.offset + end
            if any(s < until and at < e for s, e in taken):
                continue
            added.append(
                Mention(
                    forms[match.group(1)],
                    text[start:end],
                    passage.section,
                    passage.offset + start,
                    text[end : end + 24],
                )
            )
    if not added:
        return None
    return AnnotatedDocument(
        pmid=doc.pmid,
        pmcid=doc.pmcid,
        mentions=(*doc.mentions, *added),
        relations=(),
        passages=doc.passages,
    )


def normalise_spaced(text: str) -> str:
    """Lower case with punctuation as spaces, one character for one, so offsets hold."""
    return re.sub(r"[^a-z0-9]", " ", text.lower())


def prior_relations(doc: AnnotatedDocument) -> AnnotatedDocument:
    """The document with only the relations a prior takes part in."""
    kept = tuple(
        relation
        for relation in doc.relations
        if relation.first.identifier.startswith(PREFIX)
        or relation.second.identifier.startswith(PREFIX)
    )
    return AnnotatedDocument(
        pmid=doc.pmid,
        pmcid=doc.pmcid,
        mentions=doc.mentions,
        relations=kept,
        passages=doc.passages,
    )
