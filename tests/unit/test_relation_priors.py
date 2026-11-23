"""Drug priors PubTator never tags are found by their names."""

from __future__ import annotations

from vitiligo.relations.priors import PREFIX, prior_relations, untagged_priors, with_priors
from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Mention, Passage, Relation
from vitiligo.storage import Prior, PriorKind, PriorSourceKind

VITILIGO = Concept("Disease", "MESH:D014820", "Vitiligo")


def _prior(name: str, source_id: str, *synonyms: str) -> Prior:
    return Prior(
        source=PriorSourceKind.OPENTARGETS,
        kind=PriorKind.DRUG,
        source_id=source_id,
        disease_id="EFO_0004208",
        name=name,
        synonyms=list(synonyms),
    )


def _doc(text: str, *mentions: tuple[str, Concept]) -> AnnotatedDocument:
    found = []
    for written, concept in mentions:
        at = text.index(written)
        found.append(Mention(concept, written, "abstract", at, text[at + len(written) :][:24]))
    return AnnotatedDocument(
        pmid="1",
        pmcid=None,
        mentions=tuple(found),
        relations=(),
        passages=(Passage("abstract", 0, text),),
    )


def test_a_prior_pubtator_tags_by_name_or_by_its_drug_is_left_to_it() -> None:
    priors = [
        _prior("POVORCITINIB", "CHEMBL5095203", "INCB054707", "ABCD"),
        _prior("UPADACITINIB", "CHEMBL3622821"),
        _prior("RITLECITINIB TOSYLATE", "CHEMBL4594420"),
    ]
    tagged = _doc(
        "Upadacitinib and ritlecitinib in vitiligo.",
        ("Upadacitinib", Concept("Chemical", "MESH:C000613732", "upadacitinib")),
        ("ritlecitinib", Concept("Chemical", "MESH:C000614924", "PF-06651600")),
    )
    forms = untagged_priors(priors, [tagged])
    # Povorcitinib is never tagged; "ABCD" is too short to be its name alone.
    assert sorted(forms) == ["incb054707", "povorcitinib"]
    assert forms["povorcitinib"].identifier == PREFIX + "CHEMBL5095203"


def test_a_name_inside_one_of_pubtators_mentions_is_left_to_it() -> None:
    forms = untagged_priors([_prior("AFAMELANOTIDE", "CHEMBL5", "NDP-alpha-MSH")], [])
    text = "Afamelanotide, or NDP-alpha-MSH, repigmented vitiligo."
    doc = _doc(text, ("alpha-MSH", Concept("Gene", "4157", "MC1R")), ("vitiligo", VITILIGO))
    marked = with_priors(doc, forms)
    assert marked is not None
    added = marked.mentions[len(doc.mentions) :]
    assert [(m.text, m.offset) for m in added] == [("Afamelanotide", 0)]
    assert (
        with_priors(_doc("No prior is named in vitiligo here.", ("vitiligo", VITILIGO)), forms)
        is None
    )


def test_only_the_relations_a_prior_takes_part_in_are_kept() -> None:
    prior = Concept("Chemical", PREFIX + "CHEMBL5095203", "POVORCITINIB")
    other = Concept("Chemical", "MESH:C540383", "ruxolitinib")
    doc = AnnotatedDocument(
        pmid="1",
        pmcid=None,
        mentions=(),
        relations=(
            Relation("Negative_Correlation", 0.9, prior, VITILIGO),
            Relation("Negative_Correlation", 0.9, other, VITILIGO),
        ),
    )
    assert [r.first.name for r in prior_relations(doc).relations] == ["POVORCITINIB"]
