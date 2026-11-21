"""The gene explorer's rows: every measurement of a gene, under one symbol."""

from __future__ import annotations

import json

from vitiligo.reports.space_genes import gene_table, gwas_genes

VITILIGO = {"id": 1, "kind": "disease", "name": "Vitiligo"}


def _expression(relation_id: int, source: str, log2fc: float) -> dict[str, object]:
    details = {"direction": "lower", "log2fc": log2fc, "fdr": 0.01, "cohorts_agreeing": 1}
    return {
        "relation_id": relation_id,
        "source_kind": "expression",
        "source": source,
        "details": json.dumps(details),
    }


def test_catalog_placeholders_are_not_genes_and_a_pair_between_genes_names_both() -> None:
    assert gwas_genes({"mapped_gene": "NR", "reported_genes": "Intergenic, TYR"}) == {"TYR"}
    assert gwas_genes({"mapped_gene": "HLA-DRB1 - HLA-DQA1"}) == {"HLA-DRB1", "HLA-DQA1"}


def test_expression_evidence_counts_wherever_it_sits() -> None:
    # The gene was first linked to vitiligo by a paper; the GEO result joined that relation.
    entities = [VITILIGO, {"id": 2, "kind": "target", "name": "PMEL"}]
    relations = [{"id": 10, "subject_id": 2, "object_id": 1, "extraction_method": "pubtator3"}]
    table = gene_table(entities, relations, [_expression(10, "geo:GSE65127", -4.1)], [], {})
    assert table["genes"][0]["expression"][0]["log2fc"] == -4.1


def test_entities_sharing_a_symbol_are_one_gene() -> None:
    entities = [
        VITILIGO,
        {"id": 2, "kind": "target", "name": "TYR"},
        {"id": 3, "kind": "biomarker", "name": "TYR"},
    ]
    relations = [
        {"id": 10, "subject_id": 2, "object_id": 1, "extraction_method": "expression"},
        {"id": 11, "subject_id": 3, "object_id": 1, "extraction_method": "expression"},
    ]
    evidence = [_expression(10, "geo:GSE65127", -5.0), _expression(11, "geo:GSE75819", -3.0)]
    genes = gene_table(entities, relations, evidence, [], {})["genes"]
    assert [g["symbol"] for g in genes] == ["TYR"]
    assert {r["source"] for r in genes[0]["expression"]} == {"geo:GSE65127", "geo:GSE75819"}


def test_the_most_significant_cohort_comes_first_even_at_an_fdr_of_zero() -> None:
    entities = [VITILIGO, {"id": 2, "kind": "target", "name": "TYR"}]
    relations = [{"id": 10, "subject_id": 2, "object_id": 1, "extraction_method": "expression"}]
    evidence = [_expression(10, "geo:GSE75819", -3.0), _expression(10, "geo:GSE65127", -5.0)]
    evidence[1]["details"] = json.dumps({"direction": "lower", "log2fc": -5.0, "fdr": 0.0})
    results = gene_table(entities, relations, evidence, [], {})["genes"][0]["expression"]
    assert [r["source"] for r in results] == ["geo:GSE65127", "geo:GSE75819"]


def test_a_panel_gene_is_listed_even_without_a_measurement() -> None:
    genes = gene_table([VITILIGO], [], [], [], {"housekeeping": ["RPLP0"]})["genes"]
    assert genes == [{"symbol": "RPLP0", "agreeing": 0, "panel": "housekeeping"}]


def test_coexpression_pairs_point_at_the_genes_they_join() -> None:
    entities = [
        {"id": 2, "kind": "target", "name": "SRSF8"},
        {"id": 3, "kind": "target", "name": "DPM1"},
        {"id": 4, "kind": "target", "name": "ACTB"},
    ]
    relations = [
        {
            "id": 20,
            "subject_id": 2,
            "object_id": 3,
            "extraction_method": "geo_punch_biopsies_gse311770",
        }
    ]
    evidence = [
        {"relation_id": 20, "source_kind": "geo", "details": json.dumps({"pearson_r": 0.709})}
    ]
    table = gene_table(entities, relations, evidence, [], {"housekeeping": ["ACTB"]})
    symbols = [g["symbol"] for g in table["genes"]]
    ((a, b, r),) = table["pairs"]
    assert {symbols[a], symbols[b]} == {"SRSF8", "DPM1"} and r == 0.709
