"""Tests for recognising a vitiligo trial under the disease's other names."""

from __future__ import annotations

import pytest

from vitiligo.storage import Trial, TrialSourceKind
from vitiligo.trials.relevance import (
    DERM_DRUG_SCOPE,
    DRUG_CLASS_SCOPE,
    DRUG_CLASS_SCOPES,
    drug_class_relation,
    in_vitiligo_corpus,
    is_drug_class_trial,
    is_vitiligo_trial,
    names_vitiligo,
    treats_skin_disease,
)


def _trial(
    conditions: list[str] | None = None,
    title: str = "",
    criteria: str = "",
) -> Trial:
    return Trial(
        source=TrialSourceKind.ICTRP,
        source_id="X1",
        brief_title=title,
        conditions=conditions or [],
        eligibility_criteria=criteria,
    )


def test_a_free_text_white_patch_condition_is_enough_on_its_own() -> None:
    """CTRI writes most of these as prose, not as an ICD code.

    CTRI/2018/04/013496 registers "null- white patches over the body" and is
    saved only by the word Switra in its title. This is the sibling record
    that has no such word, and losing it would be invisible.
    """
    assert is_vitiligo_trial(
        _trial(["null- white patches over the body"], "Effect of a herbal ointment, 3 months")
    )


@pytest.mark.parametrize(
    ("conditions", "title"),
    [
        (["white patches & leucoderma"], "Development of Herbal Formulations for leucoderma"),
        (["Leukoderma, not elsewhere classified"], "Efficacy Of Ammi Visnaga In Leucoderma"),
        (["Diseases of the skin"], "A clinical study of SHWITRA w.s.r to leucoderma"),
        ([], "Effect of Avalgujadi Gutika in Switra"),
        (["Leukoderma, not elsewhere classified"], "virechana karma in switra"),
    ],
)
def test_the_trials_a_literal_word_match_was_missing_are_found(
    conditions: list[str], title: str
) -> None:
    """These five are real vitiligo trials that never write "vitiligo".

    Ayurveda registers the disease as *Switra* and Indian records as
    *leucoderma*, and the previous gate asked only whether the literal word
    appeared. One of the five measures VASI as its primary outcome, so the
    corpus was missing a trial that reports on the same scale as the JAK
    trials it is meant to be compared with.
    """
    assert is_vitiligo_trial(_trial(conditions, title))


@pytest.mark.parametrize(
    ("conditions", "title"),
    [
        (["post-burn leukoderma"], "Melanocyte suspension transplantation in postburn leukoderma"),
        (["Rhododenol-induced Leukoderma"], "Long-term treatment with bimatoprost"),
        (["Leukoderma"], "Occupational leukoderma among rubber workers"),
    ],
)
def test_depigmentation_with_a_known_external_cause_is_not_vitiligo(
    conditions: list[str], title: str
) -> None:
    """These are melanocyte loss from a burn or a chemical, not the disease.

    Both sweeps found them under "leukoderma" -- ICD L81.5, which does not
    distinguish cause. Admitting them would put their repigmentation rates in
    the same table as a JAK inhibitor's, which is the comparison this project
    exists to get right.
    """
    assert not is_vitiligo_trial(_trial(conditions, title))


@pytest.mark.parametrize(
    "subject",
    [
        "K132- Leukoplakia and other disturbances of oral epithelium, including tongue",
        "Disorder of pigmentation, unspecified | Unani formulations in the management of"
        " White patches | treatment of Bahaq (Pityriasis)",
        "Laser light therapy in patients with white patches in the mouth: oral lichen planus",
        "Retinoic acid cream in actinic keratosis with leukoderma",
        "Retinoic acid cream in cutis laxa senilis with leukoderma",
        "Melanocyte suspension transplantation in postburn leukoderma",
        "Rhododenol-induced Leukoderma: a long-term treatment study",
    ],
)
def test_a_suggestive_name_in_the_wrong_setting_is_refused(subject: str) -> None:
    """Twenty-three of the 640 records the sweeps found read like this.

    They are the only records the disqualifier list affects: each carries a
    name the disease shares -- leukoderma, white patch -- in a record about
    the mouth, a burn, a chemical or sun damage. Everything else in the sweep
    is refused for naming the disease nowhere at all, so these are the cases
    that decide whether the list is doing anything.
    """
    assert not names_vitiligo(subject)


def test_depigmentation_and_white_spot_alone_never_qualify() -> None:
    """Both terms added hundreds of false records and not one true one.

    "Depigmentation" matched 129 records we did not hold and "white spot" 266,
    and every real trial among them was also found by another name. Were
    either an accepted term, the gate would depend entirely on the
    disqualifier list being exhaustive, which no list of other diseases is.
    """
    assert not names_vitiligo("depigmentation")
    assert not names_vitiligo("skin depigmentation study")
    assert not names_vitiligo("white spot")
    assert not names_vitiligo("prevention of white spot lesions")


def test_a_criterion_is_not_what_the_trial_is_about() -> None:
    """Twenty records name vitiligo only where they exclude it.

    CTRI/2019/04/018804 writes leukoderma once, in "any previous surgical
    treatments for post burn leukoderma"; several Kumkumadi trials for facial
    hyperpigmentation exclude vitiligo patients by name. Reading eligibility
    text would admit all of them as vitiligo trials.
    """
    excluded = _trial(
        conditions=["Chloasma"],
        title="Kumkumadi Taila in facial hyperpigmentation",
        criteria="Exclusion criteria: patients with vitiligo or leucoderma",
    )
    assert not is_vitiligo_trial(excluded)


def test_switra_is_the_disease_and_bahaq_is_not() -> None:
    """Both are traditional-medicine terms; only one means vitiligo.

    A gate that treated any Ayurvedic or Unani pigment formulation as vitiligo
    would take Bahaq, which is pityriasis, and Kalaf, which is melasma. The
    distinction has to be the disease name, not the tradition.
    """
    assert names_vitiligo("A clinical study of Shwitra")
    assert not names_vitiligo("Zimad e Bars in Kalaf (Melasma)")
    assert not names_vitiligo("Habb-e-Kalaf in Bahaq (Pityriasis)")


def test_a_misspelling_in_the_condition_still_counts() -> None:
    """Three ChiCTR records spell it wrong in the condition field.

    All three spell it correctly in their titles, so this changes no trial in
    the corpus today; it is what keeps a record that misspells it in both
    places from being dropped.
    """
    for spelling in ("vtiligo", "Vilitigo", "Vitligo"):
        assert is_vitiligo_trial(_trial([spelling], "A prospective open clinical study"))


# The records in the corpus that are not vitiligo trials. They arrived because
# ClinicalTrials.gov expands ``query.cond=vitiligo`` to neighbouring
# pigmentation terms and ICTRP matches free text: eight are gingival
# depigmentation, the rest hypopigmented scars, melanin hyperpigmentation, and
# trials of other diseases entirely. They are kept rather than deleted --
# each was really returned by a registry for this query, and that provenance
# is worth more than a round number -- but they are not vitiligo, and the
# corpus total should not be quoted as though they were.
NOT_VITILIGO: frozenset[str] = frozenset(
    {
        "NCT04089475",
        "NCT06491615",
        "NCT06945393",
        "NCT03646955",
        "NCT06122090",
        "NCT04680806",
        "NCT06075641",
        "NCT06886100",
        "NCT07067515",
        "NCT07521176",
        "NCT07595705",
        "NCT07677826",
        "NCT07708792",
        "NCT07748507",
        "ChiCTR2400080649",
        "ChiCTR2500102064",
        "ChiCTR2600132403",
        "ChiCTR-BOC-17011649",
        "CTRI/2023/10/058514",
        "NL-OMON58188",
    }
)


@pytest.mark.corpus
def test_the_corpus_holds_exactly_these_twenty_non_vitiligo_records(
    require_local_corpus,
) -> None:
    """Every other held trial names the disease; these twenty do not.

    This is the number behind any claim about how many vitiligo trials exist.
    If an ingest admits a record naming no form of the disease, this fails and
    the record has to be looked at rather than counted.
    """
    import json
    import sqlite3

    from vitiligo.config import get_settings

    con = sqlite3.connect(f"file:{get_settings().resolved_db_path}?mode=ro", uri=True)
    rejected = set()
    total = 0
    for sid, cond, kw, brief, official, metadata in con.execute(
        "SELECT source_id, conditions, keywords, brief_title, official_title, raw_metadata"
        " FROM trials"
    ):
        # A trial held for its drug rather than its disease is a different
        # population and is counted separately. Without this partition,
        # importing the JAK class's 1,358 trials in rheumatoid arthritis and
        # myelofibrosis would make this test fail 1,358 times over and the
        # corpus total mean something else entirely.
        if str((json.loads(metadata or "{}") or {}).get("scope") or "") in DRUG_CLASS_SCOPES:
            continue
        total += 1
        subject = " | ".join(
            [*json.loads(cond or "[]"), *json.loads(kw or "[]"), brief or "", official or ""]
        )
        if not names_vitiligo(subject):
            rejected.add(sid)
    con.close()

    assert rejected - NOT_VITILIGO == set(), "a record naming no form of the disease was admitted"
    assert NOT_VITILIGO - rejected == set(), "a listed record is gone, or now names the disease"
    # 1,081 records from registries and 467 reconstructed from the papers of
    # trials that were never registered, less the twenty above.
    assert total - len(NOT_VITILIGO) == 1528


def test_a_drug_class_trial_is_not_a_vitiligo_trial() -> None:
    """Ruxolitinib in myelofibrosis is held for the drug, not the disease.

    1,358 trials of this drug class are in the corpus because the class is
    the one the scenario model is built on, and 428 of them have posted
    results against 65 in the whole vitiligo corpus. None of them is a
    vitiligo trial, and a count that said otherwise would be a number about
    rheumatoid arthritis wearing this project's name.
    """
    myelofibrosis = Trial(
        source=TrialSourceKind.CTGOV,
        source_id="NCT00000001",
        brief_title="Ruxolitinib in primary myelofibrosis",
        conditions=["Primary Myelofibrosis"],
        raw_metadata={"scope": DRUG_CLASS_SCOPE, "scope_drug": "ruxolitinib"},
    )
    assert is_drug_class_trial(myelofibrosis)
    assert not in_vitiligo_corpus(myelofibrosis)
    assert not is_vitiligo_trial(myelofibrosis)


def test_a_vitiligo_trial_of_the_same_drug_stays_in_the_corpus() -> None:
    """Ruxolitinib cream in vitiligo arrives from both searches.

    The condition search is the one that says what it is, so the drug search
    must not relabel it. A trial with no scope mark is a vitiligo trial, which
    is every trial ingested before the mark existed.
    """
    in_vitiligo = Trial(
        source=TrialSourceKind.CTGOV,
        source_id="NCT04052425",
        brief_title="Ruxolitinib cream in non-segmental vitiligo",
        conditions=["Vitiligo"],
        raw_metadata={"study": {}},
    )
    assert not is_drug_class_trial(in_vitiligo)
    assert in_vitiligo_corpus(in_vitiligo)
    assert is_vitiligo_trial(in_vitiligo)


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        (["Psoriasis"], True),
        (["Atopic Dermatitis"], True),
        (["Dermatitis, Atopic"], True),
        (["Alopecia Areata"], True),
        (["Oral Lichen Planus"], True),
        (["Hidradenitis Suppurativa"], True),
        (["Vitiligo"], True),
        (["Breast Cancer"], False),
        (["Metastatic Breast Cancer", "Psoriasis"], False),
        (["Mycosis Fungoides"], False),
        (["Sezary Syndrome"], False),
        (["Type 2 Diabetes"], False),
        (["Septic Shock"], False),
    ],
)
def test_a_drug_trial_counts_only_where_the_disease_is_skin(
    conditions: list[str], expected: bool
) -> None:
    """The search cannot be trusted to answer the question it was asked.

    Asking ClinicalTrials.gov for these drugs "in a list of skin diseases"
    returned 2,974 trials we did not hold and 1,579 were oncology, 420 of them
    breast cancer, because methotrexate and fluorouracil are chemotherapy and
    the condition expression expands much further than it reads. Filtering on
    the conditions each record carries leaves 1,362.

    A disease that is both is refused. Mycosis fungoides is a lymphoma of the
    skin and its population is an oncology population whatever organ it
    presents in.
    """
    trial = Trial(
        source=TrialSourceKind.CTGOV,
        source_id="NCT00000002",
        brief_title="A study of a drug",
        conditions=conditions,
    )
    assert treats_skin_disease(trial) is expected


def test_both_drug_scopes_are_kept_out_of_the_vitiligo_count() -> None:
    """Two scopes exist and a count of vitiligo trials must exclude both.

    ``jak_class`` is the drug class the scenario model is built on, in any
    disease. ``derm_drug`` is a vitiligo prior drug in skin disease. Neither
    is a vitiligo trial, and 2,661 of them join 1,027 that are.
    """
    for scope in (DRUG_CLASS_SCOPE, DERM_DRUG_SCOPE):
        trial = Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT00000003",
            brief_title="Tacrolimus in atopic dermatitis",
            conditions=["Atopic Dermatitis"],
            raw_metadata={"scope": scope},
        )
        assert is_drug_class_trial(trial), scope
        assert not in_vitiligo_corpus(trial), scope


@pytest.mark.parametrize(
    ("conditions", "relation"),
    [
        (["Alopecia Areata"], "skin"),
        (["Atopic Dermatitis"], "skin"),
        (["Acne Vulgaris"], "skin"),
        (["Rosacea"], "skin"),
        (["Rheumatoid Arthritis"], "class_safety"),
        (["Systemic Lupus Erythematosus"], "class_safety"),
        (["Primary Myelofibrosis"], "distant"),
        (["COVID-19"], "distant"),
        (["Healthy"], "distant"),
    ],
)
def test_a_drug_class_trial_says_how_near_it_sits(conditions: list[str], relation: str) -> None:
    """ "Held for the drug" is true of all of them and says too little.

    Ritlecitinib in alopecia areata and ruxolitinib in myelofibrosis are not
    equally informative about vitiligo: the first is approved in both diseases
    and shares the mechanism, the second is JAK2 inhibition of a driver
    mutation in a cancer at far higher exposure. Of 1,358 JAK trials, 323 are
    skin, 332 are another autoimmune disease on the same molecule -- which is
    where the class's boxed warning came from -- and 703 are neither.
    """
    trial = Trial(
        source=TrialSourceKind.CTGOV,
        source_id="NCT00000004",
        brief_title="A drug study",
        conditions=conditions,
    )
    assert drug_class_relation(trial) == relation


def test_the_skin_list_is_one_list() -> None:
    """Written twice, it drifted, and the two copies disagreed on 88 trials.

    ``treats_skin_disease`` decides whether a prior drug's trial is worth
    holding; ``drug_class_relation`` decides how near it sits. They are the
    same question about the same word and must not answer differently, which
    they did for acne, rosacea, seborrhoeic dermatitis and contact dermatitis
    until the second copy was deleted.
    """
    for condition in (
        "Acne Vulgaris",
        "Rosacea",
        "Seborrheic Dermatitis",
        "Allergic Contact Dermatitis",
        "Pityriasis Alba",
        "Psoriasis",
    ):
        trial = Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT00000005",
            brief_title="A drug study",
            conditions=[condition],
        )
        assert treats_skin_disease(trial), condition
        assert drug_class_relation(trial) == "skin", condition
