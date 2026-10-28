"""Tests for reading per-sample labels out of a GEO series matrix."""

from __future__ import annotations

import pytest

from vitiligo.sources.geo_matrix import (
    TABLE_MARKER,
    GeoSample,
    is_about_vitiligo,
    parse_header,
    series_matrix_url,
)

HEADER = f"""!Series_title\t"Targeting the WNT pathway for repigmenting vitiligo"
!Sample_title\t"Healthy Volunteer [9001]"\t"Lesional [9011]"\t"Non Lesional [9021]"
!Sample_geo_accession\t"GSM1587709"\t"GSM1587719"\t"GSM1587729"
!Sample_source_name_ch1\t"Healthy Volunteer"\t"Lesional"\t"Non Lesional"
!Sample_organism_ch1\t"Homo sapiens"\t"Homo sapiens"\t"Homo sapiens"
!Sample_characteristics_ch1\t"tissue: Whole skin"\t"tissue: Whole skin"\t"tissue: Whole skin"
!Sample_characteristics_ch1\t"disease state: healthy"\t"disease state: vitiligo"\t"disease state: vitiligo"
{TABLE_MARKER}
ID_REF\tGSM1587709\tGSM1587719\tGSM1587729
1007_s_at\t9.1\t8.7\t9.0
"""


@pytest.fixture
def samples() -> list[GeoSample]:
    return parse_header(HEADER.split(TABLE_MARKER)[0])


def test_each_sample_gets_its_own_column_of_characteristics(samples) -> None:
    """A characteristics line is one key across every sample, not one sample.

    Read row-wise instead of column-wise, every sample would carry every
    other sample's phenotype, and the healthy controls would read as vitiligo.
    """
    assert [s.accession for s in samples] == ["GSM1587709", "GSM1587719", "GSM1587729"]
    assert samples[0].characteristics == {"tissue": "Whole skin", "disease state": "healthy"}
    assert samples[1].characteristics == {"tissue": "Whole skin", "disease state": "vitiligo"}


def test_source_name_and_organism_are_kept_as_written(samples) -> None:
    assert [s.source_name for s in samples] == ["Healthy Volunteer", "Lesional", "Non Lesional"]
    assert {s.organism for s in samples} == {"Homo sapiens"}


def test_a_header_without_samples_parses_to_nothing() -> None:
    assert parse_header('!Series_title\t"Something"\n') == []


def test_a_series_is_relevant_when_its_title_names_the_disease(samples) -> None:
    assert is_about_vitiligo(samples, title="Targeting the WNT pathway for repigmenting vitiligo")


def test_a_sample_phenotype_is_enough_when_the_title_is_silent(samples) -> None:
    assert is_about_vitiligo(samples, title="Microarray of skin biopsies")


def test_a_donors_other_illnesses_do_not_make_a_series_relevant() -> None:
    """This is why the check reads phenotype fields and not free text.

    GSE160310 is a diabetic retinopathy study of 158 retinas. One donor has
    vitiligo in their comorbidity list, and matching any characteristic
    counted all 158 samples as vitiligo data — 316 across the three sibling
    series, a third of every human sample we hold.
    """
    retina = [
        GeoSample(
            accession="GSM4871112",
            title="sample_01",
            source_name="Retina Macula",
            organism="Homo sapiens",
            characteristics={
                "tissue": "Retina Macula",
                "disease group": "Control",
                "comorbidities": "hypertension, asthma, hypothyroidism, vitiligo",
                "other_medication": "ASA, levoxyl, verapamil",
            },
        )
    ]
    assert not is_about_vitiligo(
        retina,
        title="In-depth transcriptomic analyses underlying diabetic retinopathy",
    )


def test_the_accession_decides_the_ftp_directory() -> None:
    """GEO buckets series by accession with the last three digits masked."""
    assert series_matrix_url("GSE65127").endswith(
        "/GSE65nnn/GSE65127/matrix/GSE65127_series_matrix.txt.gz"
    )
    assert "/GSE160nnn/GSE160310/" in series_matrix_url("GSE160310")
    assert "/GSEnnn/GSE1/" in series_matrix_url("GSE1")


@pytest.mark.parametrize("bad", ["GSM1587709", "65127", "GSE65127.txt", ""])
def test_a_non_series_accession_is_refused(bad: str) -> None:
    """A sample accession would resolve to a URL that quietly 404s."""
    with pytest.raises(ValueError):
        series_matrix_url(bad)
