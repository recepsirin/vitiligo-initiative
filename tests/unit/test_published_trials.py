"""Tests for trials that exist only as papers."""

from __future__ import annotations

import pytest

from vitiligo.sources.published_trials import (
    PUBLISHED_ONLY_SCOPE,
    countries_of,
    observes_vitiligo_under_immunotherapy,
    outcome_trial_from_document,
    registry_ids,
    reports_a_trial,
    trial_from_document,
    unregistered_trials,
)
from vitiligo.storage.models import Document, SourceKind, TrialSourceKind
from vitiligo.trials.relevance import (
    VITILIGO_AS_OUTCOME_SCOPE,
    in_vitiligo_corpus,
    is_registered,
    studies_vitiligo,
)

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


@pytest.mark.parametrize(
    ("affiliation", "country"),
    [
        (
            "Department of Dermatology, University of Michigan, Ann Arbor, Michigan.",
            "United States",
        ),
        ("Department of Dermatology, Baylor, Houston, Texas", "United States"),
        ("Medical College of Georgia, Augusta, Georgia", "United States"),
        ("Department of Dermatology, Tbilisi State Medical University, Georgia.", "Georgia"),
    ],
)
def test_a_us_state_is_a_country_except_when_it_is_georgia(affiliation: str, country: str) -> None:
    """Sixty-three of these papers name a state and never the country.

    "Ann Arbor, Michigan" and "Houston, Texas" end there, and reading only
    country names lost every one. Georgia is the exception in both
    directions: it is a state far more often than a country, so it counts as
    the United States unless the affiliation says Tbilisi, which the one
    Georgian vitiligo trial in this corpus does.
    """
    doc = _doc(affiliations=[affiliation])
    assert countries_of(doc) == [country]


@pytest.mark.parametrize(
    ("affiliation", "country"),
    [
        # A country the list did not have. Thirty that this corpus already
        # knew from a registry had no affiliation pattern at all.
        ("Clinical Centre of Skin, Riga 1st Hospital, Riga, LV-1001, Latvia", "Latvia"),
        # A country written only as a postal code.
        (
            "Section of Medical Oncology, Rush-Presbyterian Medical Center, Chicago, IL.",
            "United States",
        ),
        # A letterhead that names the institution and assumes the country.
        # Eleven held papers say only "Lahore".
        ("KEMU/ Mayo Hospital Lahore", "Pakistan"),
        # An affiliation that is nothing but an email address.
        ("raffaele.cagiano@uniba.it.", "Italy"),
    ],
)
def test_a_country_is_read_from_a_code_a_city_or_a_domain(affiliation: str, country: str) -> None:
    """Sixty-six held papers named a place and were placed nowhere.

    A national journal's letterhead names the institution and assumes the
    country, because its readers share it. Each of these is a different way
    the country is stated without being spelled: a name the list lacked, a
    postal code, a city, a domain. A place is read only where the
    affiliation names no country at all, so it can never override one.
    """
    doc = _doc(affiliations=[affiliation])
    assert countries_of(doc) == [country]


def test_a_country_that_is_a_place_inside_another_country() -> None:
    """Three such names are in this corpus, found by auditing the rare ones.

    "University of Benin Teaching Hospital, Benin City, Edo State, Nigeria"
    is five papers of the five that name Benin, and reading the country out
    of it invented a Beninese literature. Armenia is a city in Colombia and
    Jamaica Plain is in Boston. The kept paper beside each proves the country
    is still read where it really is the country.
    """
    assert countries_of(
        _doc(
            affiliations=["University of Benin Teaching Hospital, Benin City, Edo State, Nigeria."]
        )
    ) == ["Nigeria"]
    assert countries_of(_doc(affiliations=["Service de Dermatologie, Cotonou, Benin."])) == [
        "Benin"
    ]
    assert countries_of(
        _doc(affiliations=["Universitaria Empresarial Alexander von Humboldt, Armenia, Colombia."])
    ) == ["Colombia"]
    assert countries_of(_doc(affiliations=["Institute of Dermatology, Yerevan, Armenia"])) == [
        "Armenia"
    ]
    assert countries_of(
        _doc(affiliations=["VA Boston Healthcare System, Jamaica Plain, MA, USA"])
    ) == ["United States"]
    assert countries_of(_doc(affiliations=["Department of Dermatology, Kingston, Jamaica"])) == [
        "Jamaica"
    ]


def test_a_place_never_overrides_a_country_the_affiliation_states() -> None:
    """Otherwise the gazetteer would decide against the evidence.

    "Moscow Institute ... Cairo, Egypt" names Egypt; Moscow is the name of an
    institute in it.
    """
    doc = _doc(affiliations=["Moscow Institute, Department of Dermatology, Cairo, Egypt"])
    assert countries_of(doc) == ["Egypt"]


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
    assert rows, "no trials reconstructed from papers are held"
    for source_id, metadata, has_results in rows:
        # Two kinds come from papers and they are different claims: a trial
        # of this disease that nobody registered, and a cancer trial in which
        # the disease appeared.
        scope = (json.loads(metadata or "{}") or {}).get("scope")
        assert scope in {PUBLISHED_ONLY_SCOPE, VITILIGO_AS_OUTCOME_SCOPE}, source_id
        assert not has_results, f"{source_id} claims a posted result it cannot have"


@pytest.mark.parametrize(
    ("title", "abstract", "studied"),
    [
        ("Efficacy of tacrolimus versus clobetasol in vitiligo", "", True),
        (
            "Syringes versus Chinese cups in blister grafting",
            "Thirty patients with stable vitiligo were enrolled.",
            True,
        ),
        ("Polypodium leucotomos extract", "In the treatment of vitiligo, patients received", True),
        (
            "Complete response to nivolumab in melanoma",
            "Vitiligo developed in three patients during treatment.",
            False,
        ),
        (
            "Autoimmune toxicities of antitumor vaccines",
            "Autoimmune toxicities including vitiligo were observed.",
            False,
        ),
    ],
)
def test_whose_disease_it_was_decides(title: str, abstract: str, studied: bool) -> None:
    """Reading a title and abstract together for the word was not enough.

    A melanoma immunotherapy paper names vitiligo because depigmentation was
    an adverse event, and six of them reached a corpus of vitiligo trials
    that way. The title settles it when it names the disease; otherwise the
    abstract has to say the disease is who was studied.
    """
    assert studies_vitiligo(title, abstract) is studied


@pytest.mark.parametrize(
    ("types", "abstract", "reports"),
    [
        (["Randomized Controlled Trial"], "", True),
        (["Letter", "Randomized Controlled Trial"], "", True),
        (["Review"], "Forty patients were randomised in the trials reviewed.", False),
        (["Meta-Analysis"], "Nine randomised trials of 400 patients were pooled.", False),
        (["Case Reports", "Clinical Trial"], "", False),
        # A dermatology abstract writes its sample size either way, and
        # reading only digits lost 28 trials.
        (["Journal Article"], "Fifty-five patients applied ruxolitinib cream twice daily.", True),
        (["Journal Article"], "55 patients with vitiligo applied cream twice daily.", True),
        (["Journal Article"], "Patients were randomly assigned to two groups.", True),
        (["Journal Article"], "This review covers recent advances.", False),
    ],
)
def test_a_report_of_a_trial_is_not_a_paper_about_trials(
    types: list[str], abstract: str, reports: bool
) -> None:
    """Searching the text for "randomised" finds 545 more papers and 71 are reviews.

    Where PubMed has typed it there is nothing to decide, in both directions.
    Where it has not, the abstract must count the people enrolled or say how
    they were assigned -- either, not both, because requiring both rejected
    the single-arm ruxolitinib and narrow-band UVB study along with 333 other
    records already held.
    """
    document = Document(
        source=SourceKind.PUBMED,
        source_id="1",
        title="Tacrolimus ointment in vitiligo",
        abstract=abstract,
        publication_types=types,
    )
    assert reports_a_trial(document) is reports


def test_an_abstract_cannot_tell_a_trial_from_a_case_control_study() -> None:
    """Both count their participants in the same sentence, so the title decides.

    "148 patients were classified" and "148 patients were randomised" are one
    pattern to a reader of abstracts, and the corpus was holding 132
    case-control and epidemiology papers as trials because of it. A trial
    gives somebody something; this paper gives nobody anything.

    The title is one that nothing else in the gate refuses -- it names no
    design, carries no publication type and matches no disqualifier -- so
    this passes for one reason only. "TLR2 and TLR4 gene polymorphisms in
    Turkish vitiligo patients" was tried first and was refused for saying
    "polymorphism", which left the rule itself untested.
    """
    document = Document(
        source=SourceKind.PUBMED,
        source_id="1",
        title="Audiological abnormalities in patients with vitiligo",
        abstract="Ninety patients with vitiligo and 90 controls were examined.",
        publication_types=["Journal Article"],
    )
    assert reports_a_trial(document) is False


@pytest.mark.parametrize(
    ("title", "abstract", "types", "held"),
    [
        # Every case below turns on exactly one of the four conditions, so a
        # test that passes says which guard held.
        (
            "Poliosis predicts durable response to immune-checkpoint blockade",
            "Of 120 patients with melanoma treated with pembrolizumab, 14 developed "
            "depigmentation.",
            ["Journal Article"],
            True,
        ),
        # No cancer: interferon depigments outside oncology too, without the
        # melanocyte antigens that make these trials informative.
        (
            "Interferon alfa for chronic hepatitis C",
            "90 patients were randomised; vitiligo developed in two.",
            ["Journal Article"],
            False,
        ),
        # Cancer, but no immunotherapy: a cytotoxic drug depigments skin
        # without provoking a response to melanocytes.
        (
            "Docetaxel in metastatic breast cancer",
            "80 patients were randomised; hypopigmentation occurred in four.",
            ["Journal Article"],
            False,
        ),
        # Cancer and immunotherapy, but a review of trials rather than one.
        (
            "Checkpoint inhibitors in melanoma: a review",
            "Across 40 trials of nivolumab, 300 patients were randomised and "
            "vitiligo was reported.",
            ["Review"],
            False,
        ),
        # Cancer and immunotherapy named, but the treated disease is vitiligo:
        # interferon has been trialled in it, and that belongs in the corpus.
        (
            "Interferon alfa in the treatment of vitiligo",
            "In melanoma, interferon causes depigmentation. Here 40 patients with "
            "vitiligo were randomised.",
            ["Journal Article"],
            False,
        ),
        # Cancer, immunotherapy and a trial, but nothing depigmented.
        (
            "Nivolumab in advanced melanoma",
            "200 patients were randomised; fatigue was the commonest event.",
            ["Journal Article"],
            False,
        ),
    ],
)
def test_a_cancer_trial_that_caused_vitiligo_is_held_apart(
    title: str, abstract: str, types: list[str], held: bool
) -> None:
    """Checkpoint blockade causes vitiligo by the mechanism that causes it.

    The same CD8 response to melanocyte antigens, and its appearance predicts
    durable response, so these trials are mechanism evidence the disease's own
    literature cannot supply: nobody randomises people to develop vitiligo.
    The disease being treated is a cancer, so they are not vitiligo trials.
    """
    document = Document(
        source=SourceKind.PUBMED,
        source_id="1",
        title=title,
        abstract=abstract,
        publication_types=types,
    )
    assert observes_vitiligo_under_immunotherapy(document) is held
    trial = outcome_trial_from_document(document)
    assert (trial is not None) is held
    if trial is not None:
        assert (trial.raw_metadata or {})["scope"] == VITILIGO_AS_OUTCOME_SCOPE
        assert not in_vitiligo_corpus(trial)
        # It came from a paper, so no registry holds it either. Reading one
        # scope name here called all 62 of these registered trials.
        assert not is_registered(trial)
        # The paper names the cancer in prose; guessing it would put a wrong
        # disease in a field readers filter on.
        assert trial.conditions == []


@pytest.mark.parametrize(
    "title",
    [
        # "Observation of therapeutic effect" declares a study of a treatment
        # in patients, the way "a clinical trial" does in English.
        "复方甘草酸苷联合窄谱中波紫外线治疗白癜风的疗效观察",
        # Romance languages drop the h from phototherapy and name the
        # treatment with a word of their own, so "corticoterapia sistêmica no
        # tratamento de vitiligo" says what it gave and matched nothing.
        "Estudo comparativo do uso da minociclina sistêmica versus"
        " corticoterapia sistêmica no tratamento de vitiligo em atividade",
    ],
)
def test_a_design_is_read_where_the_paper_is_not_in_english(title: str) -> None:
    """Each of these is a trial refused for the language it was written in.

    The disease gate was taught to read such a title and this one was not.
    Both cases are here because each turns on wording nothing else supplies:
    drop 疗效观察 and the first is refused, drop the Romance treatment words
    and so is the second.
    """
    document = Document(
        source=SourceKind.PUBMED,
        source_id="1",
        title=title,
        abstract="",
        publication_types=["Journal Article"],
    )
    assert reports_a_trial(document) is True


@pytest.mark.parametrize(
    ("title", "reports"),
    [
        ("[4-5-8 trimethylpsoralen in vitiligo. Controlled study of its effect]", True),
        # Names a treatment but no design: it could be a trial, a case series
        # or an opinion, and the record says nothing more.
        ("The treatment of vitiligo with psoralen derivatives", False),
        # Plural: a paper about trials rather than a report of one.
        ("Randomized controlled trials in vitiligo: a systematic review", False),
        # A head-to-head comparison is a design statement.
        ("Mini punch graft versus suction blister grafting in stable vitiligo", True),
        # ...which a synthesis can also make, so the synthesis words decide
        # here: this one says "compared to" and never says "trials".
        (
            "Meta-analysis reveals a lower UV signature in vitiligo skin compared to normal skin",
            False,
        ),
        # Except where the comparison is part of a disease's name.
        ("Vitiligo-like manifestations of graft-versus-host disease in a child", False),
    ],
)
def test_with_no_abstract_the_title_must_name_a_design(title: str, reports: bool) -> None:
    """For 399 of the 401 vitiligo papers before 1970 the title is the record.

    They carry no abstract, and Europe PMC has none either because it mirrors
    MEDLINE. So the title decides: it must name a design, and it must name one
    trial rather than discuss several. Two survive from the 1970s; guessing at
    the rest would be inventing trials out of treatment papers.
    """
    document = Document(
        source=SourceKind.PUBMED,
        source_id="1",
        title=title,
        abstract="",
        publication_types=["Journal Article"],
    )
    assert reports_a_trial(document) is reports
