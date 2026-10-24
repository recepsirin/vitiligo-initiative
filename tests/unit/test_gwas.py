"""Tests for reading vitiligo associations out of a GWAS Catalog release."""

from __future__ import annotations

import io
import zipfile

import pytest

from vitiligo.sources.gwas import (
    associations_url,
    iter_records,
    parse_associations,
    to_association,
)
from vitiligo.storage import GeneticSourceKind

COLUMNS = [
    "DATE ADDED TO CATALOG",
    "PUBMEDID",
    "DISEASE/TRAIT",
    "REPORTED GENE(S)",
    "MAPPED_GENE",
    "STRONGEST SNP-RISK ALLELE",
    "SNPS",
    "P-VALUE",
    "OR or BETA",
    "95% CI (TEXT)",
    "INITIAL SAMPLE SIZE",
    "STUDY ACCESSION",
    "MAPPED_TRAIT",
]


def _row(**over: str) -> list[str]:
    base = {
        "DATE ADDED TO CATALOG": "2024-01-01",
        "PUBMEDID": "27723757",
        "DISEASE/TRAIT": "Vitiligo",
        "REPORTED GENE(S)": "HLA-DRB1",
        "MAPPED_GENE": "HLA-DRB1 - HLA-DQA1",
        "STRONGEST SNP-RISK ALLELE": "rs9271597-A",
        "SNPS": "rs9271597",
        "P-VALUE": "3E-89",
        "OR or BETA": "1.772",
        "95% CI (TEXT)": "[1.70-1.85]",
        "INITIAL SAMPLE SIZE": "2,853 European cases",
        "STUDY ACCESSION": "GCST003702",
        "MAPPED_TRAIT": "vitiligo",
    }
    base.update(over)
    return [base[c] for c in COLUMNS]


def _archive(rows: list[list[str]], columns: list[str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        lines = ["\t".join(columns or COLUMNS)] + ["\t".join(r) for r in rows]
        archive.writestr("gwas-catalog-associations.tsv", "\n".join(lines))
    return buffer.getvalue()


def test_release_url_points_at_the_latest_release() -> None:
    assert associations_url().startswith("https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest")
    assert associations_url().endswith(".zip")


def test_only_rows_matching_the_trait_are_kept() -> None:
    raw = _archive(
        [
            _row(),
            _row(**{"DISEASE/TRAIT": "Type 2 diabetes", "MAPPED_TRAIT": "type 2 diabetes"}),
            _row(**{"DISEASE/TRAIT": "Vitiligo (age of onset)", "STUDY ACCESSION": "GCST9"}),
        ]
    )
    kept = list(parse_associations(raw, "vitiligo"))
    assert [r["STUDY ACCESSION"] for r in kept] == ["GCST003702", "GCST9"]


def test_trait_match_ignores_case_and_reads_the_mapped_trait() -> None:
    raw = _archive([_row(**{"DISEASE/TRAIT": "Generalised VITILIGO", "MAPPED_TRAIT": ""})])
    assert len(list(parse_associations(raw, "vitiligo"))) == 1
    raw = _archive([_row(**{"DISEASE/TRAIT": "Autoimmune disease", "MAPPED_TRAIT": "vitiligo"})])
    assert len(list(parse_associations(raw, "vitiligo"))) == 1


def test_a_renamed_column_fails_loudly() -> None:
    """Silently importing blanks after a release changes its schema would be worse."""
    columns = [c for c in COLUMNS if c != "P-VALUE"] + ["PVALUE"]
    raw = _archive([[*_row()[:-1], "x"]], columns=columns)
    with pytest.raises(ValueError, match="missing columns"):
        list(parse_associations(raw, "vitiligo"))


def test_an_archive_without_a_tsv_is_rejected() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "nothing here")
    with pytest.raises(ValueError, match=r"no \.tsv"):
        list(parse_associations(buffer.getvalue(), "vitiligo"))


def test_a_row_becomes_a_record_with_its_statistics() -> None:
    [row] = list(parse_associations(_archive([_row()]), "vitiligo"))
    record = to_association(row)
    assert record is not None
    assert record.source == GeneticSourceKind.GWAS_CATALOG
    assert record.source_id == "GCST003702:rs9271597"
    assert record.variant == "rs9271597"
    assert record.mapped_gene == "HLA-DRB1 - HLA-DQA1"
    assert record.p_value == pytest.approx(3e-89)
    assert record.p_value_text == "3E-89"
    assert record.odds_ratio_or_beta == pytest.approx(1.772)
    assert record.pubmed_id == "27723757"


def test_blank_statistics_become_none_not_zero() -> None:
    """A missing odds ratio is unknown; storing 0.0 would read as a real effect."""
    [row] = list(
        parse_associations(_archive([_row(**{"OR or BETA": "", "P-VALUE": "NR"})]), "vitiligo")
    )
    record = to_association(row)
    assert record is not None
    assert record.odds_ratio_or_beta is None
    assert record.p_value is None
    assert record.p_value_text == "NR"


def test_a_row_without_a_study_or_variant_is_skipped() -> None:
    assert to_association({"STUDY ACCESSION": "", "SNPS": "rs1"}) is None
    assert to_association({"STUDY ACCESSION": "GCST1", "SNPS": ""}) is None


def test_records_are_deduplicated_by_study_and_variant() -> None:
    raw = _archive([_row(), _row(), _row(**{"SNPS": "rs111"})])
    records, _info = iter_records(raw, "vitiligo")
    assert [r.source_id for r in records] == ["GCST003702:rs9271597", "GCST003702:rs111"]


def test_the_whole_catalogue_row_is_kept_for_provenance() -> None:
    records, _info = iter_records(_archive([_row()]), "vitiligo")
    assert records[0].raw_metadata["INITIAL SAMPLE SIZE"] == "2,853 European cases"
