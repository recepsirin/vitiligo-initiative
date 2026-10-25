"""Tests for resolving one WHO ICTRP record page into a trial.

Every test here names a failure that happened while the parser was written,
or a property that would silently corrupt the store if it broke.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vitiligo.sources.ictrp import _normalize_phase, _normalize_status
from vitiligo.sources.ictrp_web import (
    REDACTED_EMAIL,
    ictrp_trial_id,
    is_about_vitiligo,
    parse_record_page,
    record_to_xml,
    strip_personal,
)
from vitiligo.storage.models import Trial, TrialSourceKind

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ictrp_record_page.html"


@pytest.fixture
def page() -> str:
    return strip_personal(FIXTURE.read_text())


@pytest.fixture
def trial(page: str) -> Trial:
    parsed = parse_record_page(page)
    assert parsed is not None
    return parsed


def test_contacts_and_ethics_grids_never_reach_the_cache() -> None:
    """The page carries a name, a street address, a phone and an email.

    ``fetch_record`` caches what ``strip_personal`` returns, so anything left
    in it is written to disk and kept.
    """
    stripped = strip_personal(FIXTURE.read_text())
    for personal in ("Ada", "Example City", "12 Nowhere Road", "2345 6789"):
        assert personal not in stripped
    assert "ada.example@example.org" not in stripped
    assert "Institutional Ethics Committee" not in stripped


def test_redaction_leaves_the_trial_id_and_dates_intact() -> None:
    """A digit-run pattern eats registry ids and dates.

    The first version matched any run of nine or more digits, which turned
    ``ChiCTR2000036712`` into ``ChiCTR[phone removed]`` and ``29-05-2017``
    into ``[phone removed]`` — silently, on every record.
    """
    text = "ChiCTR2000036712 registered 29-05-2017 IRCT20210729052013N1 2020-08-24"
    assert strip_personal(text) == text


def test_redaction_still_removes_a_labelled_phone_and_an_email() -> None:
    assert "+91 11 2345 6789" not in strip_personal("Tel: +91 11 2345 6789")
    assert strip_personal("write to a@b.org") == f"write to {REDACTED_EMAIL}"


def test_every_recruitment_country_is_kept(trial: Trial) -> None:
    """``Country_Label`` names the field ``Country``.

    Normalising that span id to ``Country_`` instead matched no field, and
    every record came back with no countries at all.
    """
    assert trial.countries == ["India", "Nepal"]


def test_a_grid_summary_row_does_not_become_a_condition(trial: Trial) -> None:
    """Some grids end with a row restating all the rows above it.

    Keeping it invents a condition no registry recorded — here a single
    "Skin and Connective Tissue Diseases Vitiligo".
    """
    assert trial.conditions == ["Skin and Connective Tissue Diseases", "Vitiligo"]


def test_a_single_row_is_never_mistaken_for_a_summary() -> None:
    """One registry writes two conditions into one cell, newline-separated.

    That cell restates nothing, and dropping it would lose the only condition
    the record has.
    """
    page = (
        FIXTURE.read_text()
        .replace(
            '<span id="DataList8_ctl02_Condition_FreeTextLabel">Health Condition 2: Vitiligo</span>',
            "",
        )
        .replace(
            '<span id="DataList8_ctl03_Condition_FreeTextLabel">'
            "Skin and Connective Tissue Diseases <br>Vitiligo</span>",
            "",
        )
    )
    parsed = parse_record_page(strip_personal(page))
    assert parsed is not None
    assert parsed.conditions == ["Skin and Connective Tissue Diseases"]


def test_an_outcomes_timepoint_is_split_out_of_its_name(trial: Trial) -> None:
    """The web view folds the timepoint into the outcome name.

    Every figure in this project is indexed by week, so a week left inside
    "Extent of repigmentationTimepoint: 16 weeks" cannot be read.
    """
    [outcome] = trial.primary_outcomes
    assert outcome["measure"] == "Extent of repigmentation"
    assert outcome["description"] == "16 weeks"


def test_an_outcome_without_a_timepoint_keeps_its_whole_name(trial: Trial) -> None:
    [outcome] = trial.secondary_outcomes
    assert outcome["measure"] == "Pattern of repigmentation"


def test_a_page_with_no_record_parses_to_none() -> None:
    """The portal answers an unknown id with HTTP 200 and an empty page.

    Trusting the status code would store a trial with no id.
    """
    assert record_to_xml("<html><body>No trials found</body></html>") is None
    assert parse_record_page("<html><body>No trials found</body></html>") is None


def test_the_record_carries_a_link_back_to_its_home_registry(trial: Trial) -> None:
    """A clinician reading a CTRI trial needs CTRI's own record, not ours."""
    metadata = trial.raw_metadata or {}
    assert metadata["source_record_url"] == (
        "http://www.ctri.nic.in/Clinicaltrials/pmaindet2.php?trialid=18904"
    )
    assert trial.source_id in metadata["record_url"]


def test_the_scalar_fields_survive_the_round_trip(trial: Trial) -> None:
    assert trial.source == TrialSourceKind.ICTRP
    assert trial.source_id == "CTRI/2017/05/008692"
    assert trial.study_type == "INTERVENTIONAL"
    assert trial.enrollment_count == 84
    assert trial.first_posted_date == "29-05-2017"
    assert trial.sex == "Both"
    assert (trial.minimum_age, trial.maximum_age) == ("18 Year(s)", "65 Year(s)")
    assert trial.eligibility_criteria == "Stable vitiligo for >=12 months"
    assert (trial.raw_metadata or {})["primary_register"] == "CTRI"


def test_a_cross_registry_id_is_recovered_for_deduplication(trial: Trial) -> None:
    """The secondary id names a ClinicalTrials.gov record we may already hold."""
    assert "ctgov:NCT01234567" in (trial.raw_metadata or {})["cross_registry_keys"]


def test_a_bare_numeral_is_read_as_a_phase() -> None:
    """IRCT states the phase as "3", where the export writes "Phase 3".

    Left alone it became the literal phase label ``["3"]``, which no
    phase-aware query matches.
    """
    assert _normalize_phase("3") == ["PHASE3"]
    assert _normalize_phase("2/3") == ["PHASE2", "PHASE3"]
    assert _normalize_phase("Phase 3") == ["PHASE3"]
    assert _normalize_phase("Not Applicable") == []


def test_complete_and_completed_are_the_same_status() -> None:
    """PACTR writes "Complete"; splitting the two hides finished trials."""
    assert _normalize_status("Complete") == _normalize_status("Completed") == "COMPLETED"


@pytest.mark.parametrize(
    ("conditions", "title", "expected"),
    [
        (["Vitiligo"], "A trial", True),
        (["skin disease"], "The Psychosocial Burden of Skin Disease", False),
        ([], "Ruxolitinib cream in non-segmental vitiligo", True),
    ],
)
def test_only_records_registered_for_the_disease_are_kept(
    conditions: list[str], title: str, expected: bool
) -> None:
    """Papers cite registry ids for context as well as for evidence.

    DRKS00012745 is a sixteen-country study of stigmatization across
    dermatological disease, cited in a vitiligo paper and registered under
    "skin disease". Ingesting it would put 8,250 non-vitiligo participants in
    the trial table.
    """
    candidate = Trial(
        source=TrialSourceKind.ICTRP,
        source_id="X1",
        brief_title=title,
        conditions=conditions,
    )
    assert is_about_vitiligo(candidate) is expected


@pytest.mark.parametrize(
    ("cited", "asked"),
    [
        ("UMIN000000473", "JPRN-UMIN000000473"),
        ("JRCT2053190081", "JPRN-jRCT2053190081"),
        ("JRCTS052190079", "JPRN-jRCTs052190079"),
        ("JPRN-UMIN000000473", "JPRN-UMIN000000473"),
        ("CTRI/2017/05/008692", "CTRI/2017/05/008692"),
        ("ChiCTR2000036712", "ChiCTR2000036712"),
        ("ACTRN12620000227998", "ACTRN12620000227998"),
    ],
)
def test_japanese_ids_are_asked_for_in_the_form_ictrp_keys_them_by(cited: str, asked: str) -> None:
    """ICTRP prefixes UMIN and jRCT with ``JPRN-``, and spells jRCT lower-case.

    A paper cites neither, and ``cited_trials.normalize_id`` upper-cases what
    it finds. Asking for the cited form got "no record" for all 21 Japanese
    leads — indistinguishable from a trial ICTRP does not hold. With the
    prefix, 26 of 27 resolved; 25 proved to be burns, cardiomyopathy and
    limbal stem-cell trials from one cell-sheet review, which is why they are
    worth resolving rather than guessing about.
    """
    assert ictrp_trial_id(cited) == asked
