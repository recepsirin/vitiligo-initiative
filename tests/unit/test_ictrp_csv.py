"""Tests for importing a WHO ICTRP search export.

The export is the only route to the whole registry network, and it is also
the one payload in this project that arrives full of personal data. Most of
what follows guards that.
"""

from __future__ import annotations

import csv
import io

import pytest

from vitiligo.sources.ictrp_csv import (
    _CACHEABLE,
    _FIELDS,
    count_csv_rows,
    iter_csv_trials,
    parse_row,
    redacted_csv,
    row_to_xml,
)

CONTACT_COLUMNS = (
    "Contact Firstname",
    "Contact Lastname",
    "Contact Address",
    "Contact Email",
    "Contact Tel",
    "Contact Affiliation",
    "Ethics Contact Name",
    "Ethics Contact Address",
    "Ethics Contact Phone",
    "Ethics Contact Email",
)

ROW = {
    "TrialID": "CTRI/2023/12/060431",
    "Source Register": "CTRI",
    "Public title": "Comparing tofacitinib and tacrolimus creams for unstable vitiligo",
    "Scientific title": "A randomised comparison in unstable non-segmental vitiligo",
    "Primary sponsor": "Institute of Dermatology",
    "Date registration": "20/12/2023",
    "Date enrollement": "01/02/2024",
    "Last Refreshed on": "5 October 2026",
    "Target size": "50",
    "Recruitment Status": "Open to Recruitment",
    "Study type": "Interventional",
    "Study design": "Randomised, parallel assignment",
    "Phase": "3",
    "Countries": "India;Nepal",
    "Condition": "Health Condition 1: L80- VitiligoHealth Condition 2: Unstable vitiligo",
    "Intervention": "Intervention1: Tofacitinib 2% cream<br>Intervention2: Tacrolimus 0.1% ointment",
    "Primary outcome": "Extent of repigmentationTimepoint: 24 weeks",
    "Secondary outcome": "Patient satisfaction",
    "Secondary ID": "NCT01234567",
    "Inclusion Criteria": "Inclusion criteria: Unstable vitiligo for >=6 months",
    "Exclusion Criteria": "Exclusion criteria: Pregnancy",
    "Inclusion agemin": "18 Year(s)",
    "Inclusion agemax": "65 Year(s)",
    "Inclusion gender": "Both",
    "web address": "http://www.ctri.nic.in/Clinicaltrials/pmaindet2.php?trialid=1",
    "results yes no": "",
    "Contact Firstname": "Ada",
    "Contact Lastname": "Example",
    "Contact Address": "12 Nowhere Road, Example City",
    "Contact Email": "ada.example@example.org",
    "Contact Tel": "+91 11 2345 6789",
    "Ethics Contact Name": "Bo Example",
    "Ethics Contact Email": "ethics@example.org",
    "Ethics Contact Phone": "+91 11 9999 0000",
    "Source Name": "Institute of Dermatology, 12 Road, Tel. No. 02912795321 Email Id: x@y.org",
}


def _csv_bytes(*rows: dict[str, str]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return out.getvalue().encode("utf-8")


@pytest.fixture
def trial():
    parsed = parse_row(ROW)
    assert parsed is not None
    return parsed


def test_no_contact_column_is_ever_read() -> None:
    """The columns are a whitelist, so a contact column cannot leak by oversight.

    The real export populates an email in 833 rows, a telephone number in 813
    and a street address in 683. A filter that had to name each one would fail
    the day WHO adds a column.
    """
    for column in CONTACT_COLUMNS:
        assert column not in _FIELDS
        assert column not in _CACHEABLE


def test_a_cached_export_carries_no_contact_details() -> None:
    """What reaches the raw cache is what we keep, not what WHO served."""
    cached = redacted_csv(_csv_bytes(ROW)).decode()
    for personal in ("Ada", "Example City", "12 Nowhere Road", "Bo Example"):
        assert personal not in cached
    assert "ada.example@example.org" not in cached
    assert "ethics@example.org" not in cached
    assert "+91 11 2345 6789" not in cached


def test_contact_details_inside_a_kept_column_are_redacted() -> None:
    """One CTRI record puts an address, a phone and an email in a funder's name.

    Dropping the contact columns does not catch that, which is why the kept
    columns are redacted too.
    """
    row = dict(ROW)
    row["Study design"] = "Open label. Tel. No. 02912795321 Email Id: someone@example.org"
    cached = redacted_csv(_csv_bytes(row)).decode()
    assert "someone@example.org" not in cached
    assert "02912795321" not in cached
    assert "Open label." in cached


def test_a_redacted_export_still_parses(trial, tmp_path) -> None:
    """Redaction must not cost a trial: it runs before anything is stored."""
    path = tmp_path / "export.csv"
    path.write_bytes(redacted_csv(_csv_bytes(ROW)))
    assert count_csv_rows(path) == 1
    [reparsed] = list(iter_csv_trials(path))
    assert reparsed.source_id == trial.source_id
    assert reparsed.conditions == trial.conditions


def test_numbered_values_in_one_cell_are_split_apart(trial) -> None:
    """The export runs repeated fields together behind their own numbering.

    "Health Condition 1: ...Health Condition 2: ..." is two conditions in one
    cell. Left joined, every CTRI trial would have a single nonsense condition.
    """
    assert trial.conditions == ["L80- Vitiligo", "Unstable vitiligo"]
    assert [i["name"] for i in trial.interventions] == [
        "Tofacitinib 2% cream",
        "Tacrolimus 0.1% ointment",
    ]


def test_a_cell_with_no_numbering_is_one_value() -> None:
    row = dict(ROW, Condition="Vitiligo")
    parsed = parse_row(row)
    assert parsed is not None
    assert parsed.conditions == ["Vitiligo"]


def test_countries_split_on_semicolons(trial) -> None:
    assert trial.countries == ["India", "Nepal"]


def test_a_timepoint_is_split_out_of_an_outcome(trial) -> None:
    [outcome] = trial.primary_outcomes
    assert outcome["measure"] == "Extent of repigmentation"
    assert outcome["description"] == "24 weeks"


def test_placeholder_values_are_not_stored() -> None:
    """Registries write NIL where there is no secondary id."""
    parsed = parse_row(dict(ROW, **{"Secondary ID": "NIL"}))
    assert parsed is not None
    assert parsed.raw_metadata["secondary_ids"] == []


def test_the_scalar_fields_survive(trial) -> None:
    assert trial.source_id == "CTRI/2023/12/060431"
    assert trial.enrollment_count == 50
    assert trial.phases == ["PHASE3"]
    assert trial.study_type == "INTERVENTIONAL"
    assert trial.sex == "Both"
    assert trial.eligibility_criteria == "Unstable vitiligo for >=6 months"
    assert trial.raw_metadata["primary_register"] == "CTRI"
    assert trial.raw_metadata["source_record_url"].startswith("http://www.ctri.nic.in/")


def test_a_cross_registry_id_is_recovered_for_deduplication(trial) -> None:
    """340 of the exported trials are CTRI records; some restate an NCT id."""
    assert "ctgov:NCT01234567" in trial.raw_metadata["cross_registry_keys"]


def test_a_row_without_a_trial_id_is_skipped() -> None:
    assert row_to_xml({"TrialID": "  ", "Public title": "x"}) is None
    assert parse_row({"TrialID": "", "Public title": "x"}) is None


def test_a_doubled_label_is_stripped_all_the_way() -> None:
    """ICTRP prepends a field's label even when the registry already wrote it.

    29 IRCT records and one ChiCTR record arrive as "Inclusion criteria:
    Inclusion Criteria: 1. ...". Stripping once leaves the second copy, and
    the criteria text then begins with a label instead of a criterion.
    """
    row = dict(
        ROW,
        **{"Inclusion Criteria": "Inclusion criteria: Inclusion Criteria: Stable vitiligo"},
    )
    parsed = parse_row(row)
    assert parsed is not None
    assert parsed.eligibility_criteria == "Stable vitiligo"
