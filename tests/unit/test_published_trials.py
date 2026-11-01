"""Tests for trials that exist only as papers."""

from __future__ import annotations

import pytest

from vitiligo.sources.published_trials import (
    PUBLISHED_ONLY_SCOPE,
    countries_of,
    registry_ids,
    trial_from_document,
    unregistered_trials,
)
from vitiligo.storage.models import Document, SourceKind, TrialSourceKind
from vitiligo.trials.relevance import in_vitiligo_corpus, is_registered

DATABANK = (
    "<PubmedArticle><MedlineCitation><PMID>25902042</PMID></MedlineCitation>"
    '<DataBankList CompleteYN="Y"><DataBank>'
    "<DataBankName>ClinicalTrials.gov</DataBankName>"
    "<AccessionNumberList><AccessionNumber>NCT01701648</AccessionNumber>"
    "</AccessionNumberList></DataBank></DataBankList></PubmedArticle>"
)


def _doc(
    pmid: str = "20394489",
    title: str = "Mometasone cream versus pimecrolimus cream in vitiligo",
    abstract: str = "Sixty patients with vitiligo were randomised.",
    xml: str = "",
    affiliations: list[str] | None = None,
    year: int | None = 2010,
) -> Document:
    return Document(
        source=SourceKind.PUBMED,
        source_id=pmid,
        title=title,
        abstract=abstract,
        year=year,
        authors=[{"last": "Kose", "affiliations": affiliations or []}],
        raw_metadata={"pmid": pmid, "pubmed_xml_excerpt": xml},
    )


def test_pubmeds_own_record_of_registration_is_read() -> None:
    """A journal that required registration records the accession in PubMed.

    That is the reliable half of the check: 28 of the 522 published vitiligo
    trials carry one, and reading only the abstract would find fewer.
    """
    assert registry_ids(_doc(xml=DATABANK)) == {"NCT01701648"}


def test_an_identifier_named_only_in_the_text_is_read_too() -> None:
    """The other half, for a paper that gives its number in a sentence."""
    doc = _doc(abstract="Registered as ChiCTR-TRC-10000930. Sixty patients with vitiligo.")
    assert "ChiCTR-TRC-10000930" in registry_ids(doc)


def test_a_paper_whose_trial_we_hold_becomes_no_trial() -> None:
    """The registry record is the better source and is already in the table.

    Building a second record from the paper would hold one trial twice, which
    is the mistake this corpus has already made 34 times with European
    re-registrations.
    """
    assert list(unregistered_trials([_doc(xml=DATABANK)], ["NCT01701648"])) == []
    assert len(list(unregistered_trials([_doc(xml=DATABANK)], ["NCT99999999"]))) == 1


def test_the_identifier_is_matched_across_styles() -> None:
    """A paper writes the number its way and a registry files it another."""
    doc = _doc(abstract="Vitiligo trial registered ChiCTRTRC10000930.")
    assert list(unregistered_trials([doc], ["ChiCTR-TRC-10000930"])) == []


def test_the_country_comes_from_the_affiliation() -> None:
    """An affiliation ends with its country more reliably than it names a city."""
    doc = _doc(
        affiliations=["Department of Dermatology, Gulhane School of Medicine, Ankara, Turkey."]
    )
    assert countries_of(doc) == ["Turkey"]


def test_the_country_reaches_the_trial_record() -> None:
    """Reading the affiliation is pointless if the trial does not carry it.

    The whole reason for these records is that a reader asking what has been
    tried in Turkey gets 23 trials rather than 7, and that answer comes from
    the country filter matching the stored string.
    """
    doc = _doc(affiliations=["Department of Dermatology, Ankara, Turkey."])
    trial = trial_from_document(doc)
    assert trial is not None
    assert trial.countries == ["Turkey"]


def test_a_letterhead_spelling_becomes_the_project_s_name() -> None:
    """ "USA" is not how a registry writes it, and the filter matches one string."""
    doc = _doc(affiliations=["Department of Dermatology, Boston, MA, USA"])
    assert countries_of(doc) == ["United States"]


def test_a_paper_that_is_not_about_vitiligo_becomes_no_trial() -> None:
    """The publication type does not settle the disease.

    PubMed indexes trials of other things that measured vitiligo as an
    outcome, and a melanoma immunotherapy trial is not a vitiligo trial
    because depigmentation was an adverse event.
    """
    melanoma = _doc(
        title="Nivolumab in advanced melanoma",
        abstract="Depigmentation occurred in 12 patients.",
    )
    assert trial_from_document(melanoma) is None


def test_the_record_claims_no_posted_result() -> None:
    """``has_results`` means a registry posted them, and there is no registry.

    What the paper reports is in its abstract, which the corpus already
    holds. Setting this true would put 467 papers into a count of trials with
    posted results, which is 65.
    """
    trial = trial_from_document(_doc())
    assert trial is not None
    assert trial.has_results is False
    assert trial.source == TrialSourceKind.PUBLICATION


def test_it_is_a_vitiligo_trial_and_not_a_registered_one() -> None:
    """Both halves matter and they are different questions.

    The eighteen published Turkish vitiligo trials name no registry id
    between them. They belong in a count of vitiligo trials and they must
    not appear in a count of registrations.
    """
    trial = trial_from_document(_doc())
    assert trial is not None
    assert (trial.raw_metadata or {})["scope"] == PUBLISHED_ONLY_SCOPE
    assert in_vitiligo_corpus(trial)
    assert not is_registered(trial)


@pytest.mark.corpus
def test_the_store_keeps_the_two_kinds_apart(require_local_corpus) -> None:
    """Every published-only record is a vitiligo trial and none is registered."""
    import json
    import sqlite3

    from vitiligo.config import get_settings

    con = sqlite3.connect(f"file:{get_settings().resolved_db_path}?mode=ro", uri=True)
    rows = list(
        con.execute(
            "SELECT source_id, raw_metadata, has_results FROM trials WHERE source='PUBLICATION'"
        )
    )
    con.close()
    assert rows, "no published-only trials held"
    for source_id, metadata, has_results in rows:
        assert (json.loads(metadata or "{}") or {}).get("scope") == PUBLISHED_ONLY_SCOPE
        assert not has_results, f"{source_id} claims a posted result it cannot have"
