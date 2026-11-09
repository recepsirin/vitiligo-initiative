"""The relation model's inputs and outputs, without the model.

Each test is a way the extractor could be wrong without failing: a mention
marked one character off still trains, a pair whose label is filed under the
reverse order is still a pair, a window that misses the end of a long passage
still returns states. None of these needs torch, so all of them run in CI.
"""

from __future__ import annotations

import re
from typing import Any

from vitiligo.relations.apply import paper_relations
from vitiligo.relations.data import (
    LABELS,
    WINDOW,
    Span,
    Unit,
    concepts_of,
    document_unit,
    encode,
    snippet,
    window_starts,
)
from vitiligo.relations.scoring import score, untyped
from vitiligo.sources.biored import _document
from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Mention, Passage, Relation

VOCABULARY: dict[str, int] = {}


def _whitespace(text: str, **_: Any) -> dict[str, list[Any]]:
    """A tokenizer that splits on spaces and reports where each token sits."""
    tokens = list(re.finditer(r"\S+", text))
    return {
        "input_ids": [VOCABULARY.setdefault(t.group(), len(VOCABULARY)) for t in tokens],
        "offset_mapping": [(t.start(), t.end()) for t in tokens],
    }


def _mention(text: str, at: int, kind: str, identifier: str) -> Mention:
    return Mention(Concept(kind, identifier, text), text, "", at)


def test_a_variant_identifier_is_one_concept_and_a_gene_list_is_several() -> None:
    variant = "tmVar:c|SUB|G|1021|A;HGVS:c.1021G>A;CorrespondingGene:1644;RS#:1195471902"
    assert concepts_of(variant, "Variant") == (variant,)
    assert concepts_of("7306;1638", "Gene") == ("7306", "1638")
    assert concepts_of("D001943,D010051", "Disease") == ("D001943", "D010051")


def test_each_mention_is_marked_and_each_candidate_pair_labelled() -> None:
    title = "NR3C1 in vitiligo."
    abstract = "Tacrolimus lowered NR3C1 in mice, and TYRP1/DCT in psoriasis."
    start = len(title) + 1
    doc = AnnotatedDocument(
        pmid="1",
        pmcid=None,
        passages=(Passage("title", 0, title), Passage("abstract", start, abstract)),
        mentions=(
            _mention("NR3C1", 0, "Gene", "2908"),
            _mention("vitiligo", 9, "Disease", "MESH:D014820"),
            _mention("Tacrolimus", start, "Chemical", "MESH:D016559"),
            _mention("NR3C1", start + 19, "Gene", "2908"),
            _mention("mice", start + 28, "Species", "10090"),
            _mention("TYRP1/DCT", start + 38, "Gene", "7306;1638"),
            _mention("psoriasis", start + 51, "Disease", "MESH:D011565"),
        ),
        relations=(
            # Filed gene-first; the pair is the same whichever way round.
            Relation(
                "Association",
                0.99,
                Concept("Gene", "2908", ""),
                Concept("Disease", "MESH:D014820", ""),
            ),
            Relation(
                "Negative_Correlation",
                0.97,
                Concept("Chemical", "MESH:D016559", ""),
                Concept("Gene", "2908", ""),
            ),
        ),
    )
    unit = document_unit(doc)
    assert [unit.text[s.start : s.end] for s in unit.spans] == [
        "NR3C1",
        "vitiligo",
        "Tacrolimus",
        "NR3C1",
        "TYRP1/DCT",
        "psoriasis",
    ]
    encoded = encode(unit, _whitespace)
    assert encoded is not None
    marker = VOCABULARY["*"]
    assert all(encoded.input_ids[t] == marker for tokens in encoded.mention_tokens for t in tokens)
    assert len(encoded.mention_tokens[encoded.entities.index("2908")]) == 2
    assert set(encoded.entities) == {
        "2908",
        "MESH:D014820",
        "MESH:D016559",
        "7306",
        "1638",
        "MESH:D011565",
    }
    pairs = {
        frozenset((encoded.entities[i], encoded.entities[j])): LABELS[label]
        for (i, j), label in zip(encoded.pairs, encoded.labels, strict=True)
    }
    assert len(pairs) == 14  # every pair of the six but disease with disease
    assert frozenset(("MESH:D014820", "MESH:D011565")) not in pairs
    assert {pair: label for pair, label in pairs.items() if label != "None"} == {
        frozenset(("2908", "MESH:D014820")): "Association",
        frozenset(("MESH:D016559", "2908")): "Negative_Correlation",
    }


def test_windows_cover_every_token() -> None:
    size = WINDOW - 2
    for length in (1, size - 1, size, size + 1, size + 256, 2 * size + 7, 3000):
        starts = window_starts(length)
        covered = {i for s in starts for i in range(s, min(s + size, length))}
        assert covered == set(range(length)), length
        assert all(s + size <= max(length, size) for s in starts), length


def test_a_relation_is_quoted_from_the_sentence_that_holds_both_mentions() -> None:
    text = "Melanocytes die. IL-15 drives TRM cells in vitiligo lesions. Unrelated."
    il15 = Span(17, 22, ("3600",), "Gene")
    vitiligo = Span(43, 51, ("MESH:D014820",), "Disease")
    assert snippet(text, [il15], [vitiligo]) == "IL-15 drives TRM cells in vitiligo lesions."


def test_a_pair_a_paper_repeats_is_one_relation_from_its_surest_passage() -> None:
    def unit(text: str, spans: list[Span], section: str) -> Unit:
        return Unit("1", section, text, spans)

    vitiligo = ("MESH:D014820",)
    first = encode(
        unit(
            "CXCL10 is raised in vitiligo.",
            [Span(0, 6, ("3627",), "Gene"), Span(20, 28, vitiligo, "Disease")],
            "INTRO",
        ),
        _whitespace,
    )
    second = encode(
        unit(
            "In vitiligo, CXCL10 and TYRP1/DCT rise.",
            [
                Span(3, 11, vitiligo, "Disease"),
                Span(13, 19, ("3627",), "Gene"),
                Span(24, 33, ("7306", "1638"), "Gene"),
            ],
            "RESULTS",
        ),
        _whitespace,
    )
    assert first is not None and second is not None

    def rows(item: Any, surest: float) -> list[list[float]]:
        association = LABELS.index("Association")
        out = []
        for _ in item.pairs:  # every pair an association, each as sure as the passage
            row = [0.0] * len(LABELS)
            row[association] = surest
            row[0] = 1 - surest
            out.append(row)
        return out

    names = {"3627": "CXCL10", "MESH:D014820": "Vitiligo"}  # 7306 and 1638 have none
    [relation] = paper_relations([first, second], [rows(first, 0.6), rows(second, 0.9)], names)
    assert relation.score == 0.9
    assert relation.section == "RESULTS"
    assert relation.snippet == "In vitiligo, CXCL10 and TYRP1/DCT rise."


def test_a_prediction_counts_only_with_its_pair_and_its_type() -> None:
    gold = {("1", "a", "b", "Association"), ("1", "a", "c", "Bind")}
    predicted = {
        ("1", "a", "b", "Positive_Correlation"),
        ("1", "a", "c", "Bind"),
        ("1", "b", "c", "Bind"),
    }
    typed = score(gold, predicted)
    assert (typed.correct, typed.precision, typed.recall) == (1, 1 / 3, 1 / 2)
    paired = score(untyped(gold), untyped(predicted))
    assert (paired.correct, paired.precision, paired.recall) == (2, 2 / 3, 1.0)


def test_biored_is_read_in_pubtator_s_names() -> None:
    doc = _document(
        {
            "id": "123",
            "passages": [
                {
                    "offset": 0,
                    "text": "TYR and OCA2 in vitiligo.",
                    "annotations": [
                        {
                            "infons": {"identifier": "7299,4948", "type": "GeneOrGeneProduct"},
                            "text": "TYR and OCA2",
                            "locations": [{"offset": 0, "length": 12}],
                        },
                        {
                            "infons": {"identifier": "-", "type": "ChemicalEntity"},
                            "text": "and",
                            "locations": [{"offset": 4, "length": 3}],
                        },
                        {
                            "infons": {
                                "identifier": "D014820",
                                "type": "DiseaseOrPhenotypicFeature",
                            },
                            "text": "vitiligo",
                            "locations": [{"offset": 16, "length": 8}],
                        },
                    ],
                }
            ],
            "relations": [
                {"infons": {"entity1": "4948", "entity2": "D014820", "type": "Association"}}
            ],
        }
    )
    assert [m.concept.type for m in doc.mentions] == ["Gene", "Disease"]
    [relation] = doc.relations
    assert (relation.first.type, relation.second.type) == ("Gene", "Disease")


def test_a_markdown_body_is_read_by_section_and_keeps_its_tables() -> None:
    """A table's rows sit directly under its caption heading, in the same
    paragraph; reading the heading as the whole paragraph lost every table."""
    from vitiligo.ingest.pipeline import _body_passages

    body = (
        "## 1. Introduction\n\nVitiligo is common.\n\n"
        "## 3. Results\n\nCXCL10 rose.\n\n"
        "## Case presentation\n\nDrug | Indication\nDupilumab | Atopic dermatitis\n\n"
        "## Author contributions\n\nAB wrote it.\n\n"
        "## Tables\n\n### Table 1 Responders\nDrug | Rate\nRuxolitinib | 30%"
    )
    assert _body_passages(body) == [
        ("INTRO", "Vitiligo is common."),
        ("RESULTS", "CXCL10 rose."),
        ("TABLE", "Drug | Indication\nDupilumab | Atopic dermatitis"),  # a table, under any heading
        ("TABLE", "Drug | Rate\nRuxolitinib | 30%"),
    ]


def test_a_lexicon_mention_carries_the_words_after_it() -> None:
    """Without them "fractional CO2 laser" in a registry title was carbon dioxide."""
    from vitiligo.relations.lexicon import Entry, Lexicon

    lexicon = Lexicon({"CO2": Entry(Concept("Chemical", "MESH:D002245", "Carbon Dioxide"), 9)})
    doc = lexicon.annotate("ctgov:NCT1", [("REGISTRY", "Fractional CO2 laser for vitiligo")])
    [mention] = doc.mentions
    assert mention.text == "CO2"
    assert mention.after.startswith(" laser")


def test_lexicon_unifies_homologous_gene_ids_across_species() -> None:
    """Human TYR (7299) and mouse Tyr (22173) share 'tyrosinase'; without
    homolog unification, mouse papers split the count below MIN_SHARE."""
    from vitiligo.relations.lexicon import build

    human = AnnotatedDocument(
        pmid="1",
        pmcid=None,
        passages=(Passage("abstract", 0, "Human tyrosinase is lost in vitiligo."),),
        mentions=(Mention(Concept("Gene", "7299", "TYR"), "tyrosinase", "abstract", 6),),
        relations=(),
    )
    mouse = AnnotatedDocument(
        pmid="2",
        pmcid=None,
        passages=(Passage("abstract", 0, "Mouse tyrosinase in B16 cells."),),
        mentions=(Mention(Concept("Gene", "22173", "Tyr"), "tyrosinase", "abstract", 6),),
        relations=(),
    )
    lex = build([human, mouse])
    ann = lex.annotate("3", [("abstract", "Inhibition of tyrosinase activity.")])
    assert len(ann.mentions) == 1
    assert ann.mentions[0].concept.identifier == "7299"
    assert ann.mentions[0].concept.name == "TYR"


def test_encoded_tracks_closing_markers_and_pair_context_features() -> None:
    unit = Unit(
        "1",
        "RESULTS",
        "IFNG potently induces CXCL10 in keratinocytes.",
        [
            Span(0, 4, ("3458",), "Gene"),
            Span(22, 28, ("3627",), "Gene"),
        ],
    )
    encoded = encode(unit, _whitespace)
    assert encoded is not None
    marker = VOCABULARY["*"]
    assert all(
        encoded.input_ids[t] == marker for tokens in encoded.mention_end_tokens for t in tokens
    )
    assert len(encoded.pair_features) == 1
    b_start, b_end, dist_bucket, co_sent = encoded.pair_features[0]
    assert b_end > b_start
    assert dist_bucket == 1  # two words ("potently", "induces") between the markers
    assert co_sent == 2  # same sentence, first precedes second
