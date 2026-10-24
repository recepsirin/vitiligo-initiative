"""Tests for recovering trial registrations from the papers that report them."""

from __future__ import annotations

import pytest

from vitiligo.reports.cited_trials import (
    REGISTRY_PATTERNS,
    by_registry,
    document_text,
    find_in_text,
    scan,
)
from vitiligo.storage import Document, SourceKind


def _doc(title: str = "A vitiligo trial", body: str = "", abstract: str = "") -> Document:
    return Document(
        source=SourceKind.PMC,
        source_id=f"PMC{abs(hash(title + body)) % 100000}",
        title=title,
        abstract=abstract,
        raw_metadata={"full_text": body},
    )


@pytest.mark.parametrize(
    ("identifier", "registry"),
    [
        ("CTRI/2017/05/008692", "CTRI (India)"),
        ("ChiCTR1900024173", "ChiCTR (China)"),
        ("IRCT20210729052013N1", "IRCT (Iran)"),
        ("IRCT138802251906N1", "IRCT (Iran)"),
        ("UMIN000000473", "UMIN (Japan)"),
        ("jRCTs052190079", "jRCT (Japan)"),
        ("DRKS00012745", "DRKS (Germany)"),
        ("ACTRN12620000227998", "ANZCTR (Australia, NZ)"),
        ("TCTR20170526002", "TCTR (Thailand)"),
        ("PACTR201705002279419", "PACTR (Africa)"),
        ("KCT0001234", "CRIS (Korea)"),
    ],
)
def test_each_registry_format_is_recognised(identifier: str, registry: str) -> None:
    assert REGISTRY_PATTERNS[registry].search(identifier)


def test_an_identifier_in_a_vitiligo_paper_is_found() -> None:
    doc = _doc(body="The study was registered as CTRI/2017/05/008692 before enrolment.")
    [lead] = scan([doc])
    assert lead.identifier == "CTRI/2017/05/008692"
    assert lead.registry == "CTRI (India)"
    assert "registered as" in lead.context
    assert lead.cited_by.startswith("pmc:")


def test_a_paper_that_never_mentions_the_disease_is_skipped() -> None:
    doc = _doc(title="A cardiology trial", body="Registered as CTRI/2017/05/008692.")
    assert scan([doc]) == []


def test_a_number_far_from_any_mention_of_the_disease_is_dropped() -> None:
    """A review of other diseases cited sixteen trial numbers while mentioning vitiligo twice."""
    body = (
        "Vitiligo is mentioned here at the start. "
        + ("Filler sentence about oesophageal strictures. " * 40)
        + "The sheet trial was UMIN000000473 in gastroenterology."
    )
    assert scan([_doc(title="Cell sheet therapies", body=body)]) == []


def test_a_vitiligo_title_keeps_a_number_that_sits_far_away() -> None:
    body = ("Filler. " * 200) + "Registered as CTRI/2018/01/011120."
    [lead] = scan([_doc(title="Trial of grafting in vitiligo", body=body)])
    assert lead.identifier == "CTRI/2018/01/011120"


def test_identifiers_already_held_as_trials_are_left_out() -> None:
    doc = _doc(body="Vitiligo study, registered ISRCTN26176655.")
    assert scan([doc], known_identifiers=["ISRCTN26176655"]) == []
    assert len(scan([doc], known_identifiers=["ISRCTN99999999"])) == 1


def test_known_identifiers_match_whatever_their_case() -> None:
    doc = _doc(body="Vitiligo study, registered ChiCTR1900024173.")
    assert scan([doc], known_identifiers=["chictr1900024173"]) == []


def test_one_identifier_is_reported_once_however_often_it_is_cited() -> None:
    first = _doc(title="Vitiligo trial report", body="Registered CTRI/2017/05/008692.")
    second = _doc(title="A later vitiligo review", body="See CTRI/2017/05/008692 for details.")
    [lead] = scan([first, second])
    assert lead.cited_by == f"pmc:{first.source_id}"


def test_identifiers_are_normalised_to_upper_case() -> None:
    [lead] = scan([_doc(body="Vitiligo trial, chictr1900024173, completed.")])
    assert lead.identifier == "CHICTR1900024173"


def test_several_registries_in_one_paper_all_come_back() -> None:
    body = "Vitiligo trials: CTRI/2017/05/008692, ChiCTR1900024173 and TCTR20170526002."
    assert {lead.registry for lead in scan([_doc(body=body)])} == {
        "CTRI (India)",
        "ChiCTR (China)",
        "TCTR (Thailand)",
    }


def test_document_text_includes_the_body_not_just_the_abstract() -> None:
    doc = _doc(title="T", abstract="A", body="B")
    assert document_text(doc).split() == ["T", "A", "B"]


def test_a_document_with_no_body_still_scans() -> None:
    doc = Document(
        source=SourceKind.PUBMED, source_id="1", title="Vitiligo", abstract="CTRI/2017/05/008692"
    )
    assert len(scan([doc])) == 1


def test_find_in_text_reports_the_sentence_around_the_number() -> None:
    text = "Before. Vitiligo patients were enrolled and the trial was CTRI/2017/05/008692. After."
    [(registry, identifier, context)] = list(find_in_text(text, title_is_about_vitiligo=False))
    assert (registry, identifier) == ("CTRI (India)", "CTRI/2017/05/008692")
    assert "enrolled" in context and "After" in context


def test_grouping_orders_registries_by_how_many_leads_they_hold() -> None:
    docs = [
        _doc(body="Vitiligo CTRI/2017/05/008692."),
        _doc(body="Vitiligo CTRI/2018/01/011120."),
        _doc(body="Vitiligo TCTR20170526002."),
    ]
    grouped = by_registry(scan(docs))
    assert list(grouped) == ["CTRI (India)", "TCTR (Thailand)"]
    assert len(grouped["CTRI (India)"]) == 2


def test_a_lead_records_whether_its_paper_is_about_the_disease() -> None:
    """One lead came from a survey of several skin diseases, not a vitiligo trial."""
    named = _doc(title="A vitiligo grafting trial", body="Registered CTRI/2017/05/008692.")
    broad = _doc(
        title="Body dysmorphia in common skin diseases",
        body="Patients with psoriasis, acne and vitiligo were enrolled. Registered DRKS00012745.",
    )
    leads = {lead.identifier: lead for lead in scan([named, broad])}
    assert leads["CTRI/2017/05/008692"].paper_title_names_disease is True
    assert leads["DRKS00012745"].paper_title_names_disease is False


def test_leads_split_into_solid_and_needing_checking() -> None:
    from vitiligo.reports.cited_trials import split_by_confidence

    named = _doc(title="A vitiligo trial", body="Registered CTRI/2017/05/008692.")
    broad = _doc(
        title="Several skin diseases",
        body="Vitiligo patients among others. Registered DRKS00012745.",
    )
    solid, check = split_by_confidence(scan([named, broad]))
    assert [t.identifier for t in solid] == ["CTRI/2017/05/008692"]
    assert [t.identifier for t in check] == ["DRKS00012745"]
