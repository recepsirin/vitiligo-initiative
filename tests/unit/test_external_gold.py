"""Unit tests for external gold datasets parsing and domain masking."""

from __future__ import annotations

from vitiligo.sources.external_gold import (
    CHEMPROT_CPR_MAP,
    _parse_bc5cdr_txt,
    _parse_chemprot,
)


def test_parse_bc5cdr_txt() -> None:
    sample_txt = (
        "1001|t|Aspirin causes asthma.\n"
        "1001|a|Aspirin ingestion triggered severe asthma in patients.\n"
        "1001\t0\t7\tAspirin\tChemical\tD001241\n"
        "1001\t15\t21\tasthma\tDisease\tD001249\n"
        "1001\tCID\tD001241\tD001249\n"
    )
    docs = _parse_bc5cdr_txt(sample_txt, exclude_pmids=frozenset())
    assert len(docs) == 1
    doc = docs[0]
    assert doc.pmid == "1001"
    assert doc.target_type_pairs == frozenset({("Chemical", "Disease")})
    assert len(doc.relations) == 1
    rel = doc.relations[0]
    assert rel.type == "Positive_Correlation"
    assert rel.first.type == "Chemical"
    assert rel.second.type == "Disease"


def test_parse_chemprot() -> None:
    abss = "1002\tImatinib inhibits BCR-ABL.\tImatinib binds and downregulates BCR-ABL kinase."
    ents = (
        "1002\tT1\tCHEMICAL\t0\t8\tImatinib\n"
        "1002\tT2\tGENE-Y\t17\t24\tBCR-ABL\n"
        "1002\tT3\tCHEMICAL\t26\t34\tImatinib\n"
        "1002\tT4\tGENE-Y\t60\t67\tBCR-ABL\n"
    )
    rels = "1002\tCPR:4\tY\tINHIBITOR\tArg1:T1\tArg2:T2\n"

    docs = _parse_chemprot(abss, ents, rels, exclude_pmids=frozenset())
    assert len(docs) == 1
    doc = docs[0]
    assert doc.pmid == "1002"
    assert doc.target_type_pairs == frozenset({("Chemical", "Gene")})
    assert len(doc.relations) == 1
    rel = doc.relations[0]
    assert rel.type == "Negative_Correlation"
    assert rel.first.type in ("Chemical", "Gene")
    assert rel.second.type in ("Chemical", "Gene")


def test_chemprot_cpr_mapping() -> None:
    assert CHEMPROT_CPR_MAP["CPR:3"] == "Positive_Correlation"
    assert CHEMPROT_CPR_MAP["CPR:4"] == "Negative_Correlation"
    assert CHEMPROT_CPR_MAP["CPR:9"] == "Bind"
