"""Tests for the ISRCTN trial source: relevance filtering and privacy."""

from __future__ import annotations

import httpx
import pytest
from lxml import etree

from vitiligo.sources.isrctn import (
    ISRCTNClient,
    is_about_vitiligo,
    parse_search,
    redact_emails,
    to_trial,
)
from vitiligo.storage import TrialSourceKind

NS = "http://www.67bricks.com/isrctn"


def _record(
    number: str = "26176655",
    title: str = "Laser treatment for vitiligo",
    condition: str = "Stable non-segmental vitiligo",
    summary: str = "Vitiligo is a long-term condition. Contact trials@example.ac.uk to join.",
) -> str:
    return f"""<fullTrial>
  <trial>
    <isrctn>{number}</isrctn>
    <trialDescription>
      <title>{title}</title>
      <scientificTitle>Clinical and immunological effects</scientificTitle>
      <plainEnglishSummary>{summary}</plainEnglishSummary>
    </trialDescription>
    <trialDesign>
      <primaryStudyDesign>Interventional</primaryStudyDesign>
      <overallEndDate>2026-08-05T00:00:00.000Z</overallEndDate>
    </trialDesign>
    <participants>
      <recruitmentCountries><country>Poland</country></recruitmentCountries>
      <trialCentres>
        <trialCentre><address>1 Hospital Road</address><city>Olsztyn</city></trialCentre>
      </trialCentres>
      <inclusion>Adults with stable disease</inclusion>
      <exclusion>Malignancies</exclusion>
      <gender>All</gender>
      <lowerAgeLimit>18 Years</lowerAgeLimit>
      <upperAgeLimit>75 Years</upperAgeLimit>
      <healthyVolunteersAllowed>false</healthyVolunteersAllowed>
      <targetEnrolment>20</targetEnrolment>
      <totalFinalEnrolment>19</totalFinalEnrolment>
      <recruitmentStart>2024-01-08T00:00:00.000Z</recruitmentStart>
      <recruitmentEnd>2025-11-03T00:00:00.000Z</recruitmentEnd>
    </participants>
    <conditions><condition><description>{condition}</description></condition></conditions>
    <interventions>
      <intervention>
        <description>Fractional laser</description>
        <interventionType>Procedure/Surgery</interventionType>
        <drugNames></drugNames>
      </intervention>
    </interventions>
  </trial>
  <contact>
    <forename>Alicja</forename><surname>Fraczek</surname>
    <contactDetails>
      <address>Municipal Hospital, Al. Wojska</address>
      <telephone>+48 89 678 66 70</telephone>
      <email>dermatologia@example.pl</email>
    </contactDetails>
  </contact>
  <sponsor><organisation>University of Warmia</organisation></sponsor>
</fullTrial>"""


def _doc(*records: str, total: int | None = None) -> bytes:
    body = "".join(records)
    count = total if total is not None else len(records)
    return f'<allTrials totalCount="{count}" xmlns="{NS}">{body}</allTrials>'.encode()


def _element(record: str) -> etree._Element:
    return parse_search(_doc(record)).trials[0]


def test_search_reports_its_total_and_trials() -> None:
    result = parse_search(_doc(_record(), _record(number="99"), total=65))
    assert result.total == 65
    assert len(result.trials) == 2


def test_a_malformed_total_does_not_crash() -> None:
    assert parse_search(f'<allTrials xmlns="{NS}"></allTrials>'.encode()).total == 0


def test_a_trial_about_vitiligo_is_kept() -> None:
    assert is_about_vitiligo(_element(_record()))


def test_a_trial_that_only_mentions_vitiligo_is_dropped() -> None:
    """ISRCTN matches the word anywhere, including in exclusion criteria."""
    mention = _record(
        title="A scalp serum to reduce hair loss",
        condition="Androgenetic alopecia",
        summary="People with vitiligo were excluded from this study.",
    )
    assert not is_about_vitiligo(_element(mention))


def test_the_condition_alone_is_enough_to_keep_a_trial() -> None:
    record = _record(title="A study of a topical product", condition="Non-segmental vitiligo")
    assert is_about_vitiligo(_element(record))


def test_a_record_becomes_a_trial_with_its_design_and_counts() -> None:
    trial = to_trial(_element(_record()))
    assert trial is not None
    assert trial.source == TrialSourceKind.ISRCTN
    assert trial.source_id == "ISRCTN26176655"
    assert trial.study_type == "INTERVENTIONAL"
    assert trial.conditions == ["Stable non-segmental vitiligo"]
    assert trial.countries == ["Poland"]
    assert trial.enrollment_count == 19  # the final count is preferred
    assert trial.enrollment_type == "ACTUAL"
    assert trial.start_date == "2024-01-08"
    assert trial.completion_date == "2026-08-05"
    assert trial.minimum_age == "18 Years"
    assert trial.healthy_volunteers is False


def test_the_target_count_is_used_when_no_final_count_exists() -> None:
    record = _record().replace("<totalFinalEnrolment>19</totalFinalEnrolment>", "")
    trial = to_trial(_element(record))
    assert trial is not None
    assert (trial.enrollment_count, trial.enrollment_type) == (20, "ESTIMATED")


def test_eligibility_keeps_both_halves() -> None:
    trial = to_trial(_element(_record()))
    assert trial is not None
    assert "Inclusion:" in (trial.eligibility_criteria or "")
    assert "Exclusion:" in (trial.eligibility_criteria or "")


def test_a_record_without_a_number_is_skipped() -> None:
    assert to_trial(_element(_record().replace("<isrctn>26176655</isrctn>", ""))) is None


# ------------------------------------------------------------------ privacy


def test_names_telephones_and_contact_details_are_not_stored() -> None:
    trial = to_trial(_element(_record()))
    assert trial is not None
    stored = (trial.raw_metadata or {}).get("xml", "")
    for leaked in ("Alicja", "Fraczek", "+48 89", "dermatologia@example.pl"):
        assert leaked not in stored


def test_site_street_addresses_are_not_stored_but_countries_are() -> None:
    trial = to_trial(_element(_record()))
    assert trial is not None
    stored = (trial.raw_metadata or {}).get("xml", "")
    assert "Hospital Road" not in stored
    assert "<address" not in stored
    assert trial.countries == ["Poland"]


def test_emails_written_into_the_summary_are_redacted() -> None:
    """Sponsors put recruitment addresses in the prose, which is kept otherwise."""
    trial = to_trial(_element(_record()))
    assert trial is not None
    assert "trials@example.ac.uk" not in (trial.summary or "")
    assert "[email removed]" in (trial.summary or "")
    assert "Vitiligo is a long-term condition." in (trial.summary or "")
    assert "@" not in (trial.raw_metadata or {}).get("xml", "")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("write to a.b+c@x.co.uk now", "write to [email removed] now"),
        ("no address here", "no address here"),
        (None, None),
        ("", ""),
    ],
)
def test_redact_emails(text: str | None, expected: str | None) -> None:
    assert redact_emails(text) == expected


# ------------------------------------------------------------------- client


def test_the_client_yields_only_relevant_trials() -> None:
    mention = _record(
        number="111", title="Hair loss serum", condition="Alopecia", summary="vitiligo excluded"
    )
    payload = _doc(_record(), mention)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "vitiligo"
        return httpx.Response(200, content=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        trials = list(ISRCTNClient(client=http).iter_trials("vitiligo"))
    assert [t.source_id for t in trials] == ["ISRCTN26176655"]


def test_a_failed_search_raises() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(500))
    with httpx.Client(transport=transport) as http, pytest.raises(httpx.HTTPStatusError):
        list(ISRCTNClient(client=http).iter_trials("vitiligo"))
