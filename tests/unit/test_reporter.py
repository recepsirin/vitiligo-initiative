"""Tests for NIH RePORTER projects and the funding summary."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from vitiligo.reports.funding import active_investigators, is_vitiligo_centred, topic_counts
from vitiligo.sources.reporter import MAX_OFFSET, ReporterClient, to_project
from vitiligo.storage import ResearchProject, ResearchSourceKind


def _record(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "project_num": "5R01AR123456-03",
        "core_project_num": "R01AR123456",
        "project_title": "Tissue resident memory T cells in vitiligo",
        "abstract_text": "Vitiligo relapses after treatment stops.",
        "principal_investigators": [
            {"profile_id": 123, "full_name": "Jane Doe", "is_contact_pi": True},
            {"profile_id": 456, "full_name": "Sam Roe", "is_contact_pi": False},
        ],
        "organization": {
            "org_name": "UNIV OF SOMEWHERE",
            "org_city": "BOSTON",
            "org_state": "MA",
            "org_country": "UNITED STATES",
        },
        "fiscal_year": 2026,
        "award_amount": 500000,
        "agency_ic_admin": {"abbreviation": "NIAMS"},
        "activity_code": "R01",
        "is_active": True,
        "project_start_date": "2024-09-01T00:00:00",
        "project_end_date": "2029-06-30T00:00:00",
        "pref_terms": "vitiligo; T cells",
        "project_detail_url": "https://reporter.nih.gov/project-details/123",
    }
    base.update(over)
    return base


def _project(**over: Any) -> ResearchProject:
    project = to_project(_record())
    assert project is not None
    for key, value in over.items():
        setattr(project, key, value)
    return project


def test_a_record_becomes_a_project_with_its_people_and_money() -> None:
    project = to_project(_record())
    assert project is not None
    assert project.source == ResearchSourceKind.NIH_REPORTER
    assert project.source_id == "5R01AR123456-03"
    assert project.core_project_num == "R01AR123456"
    assert project.contact_pi == "Jane Doe"
    assert project.investigators == ["Jane Doe", "Sam Roe"]
    assert project.organization == "UNIV OF SOMEWHERE"
    assert (project.org_state, project.fiscal_year, project.award_amount) == ("MA", 2026, 500000)
    assert project.agency == "NIAMS"
    assert project.project_start == "2024-09-01"


def test_the_contact_investigator_is_preferred_over_the_first_listed() -> None:
    record = _record(
        principal_investigators=[
            {"full_name": "Second Author", "is_contact_pi": False},
            {"full_name": "Lead Person", "is_contact_pi": True},
        ]
    )
    project = to_project(record)
    assert project is not None
    assert project.contact_pi == "Lead Person"


def test_a_project_without_a_number_is_skipped() -> None:
    assert to_project(_record(project_num="")) is None


def test_missing_money_and_people_do_not_crash() -> None:
    project = to_project(_record(award_amount=None, principal_investigators=[], fiscal_year=None))
    assert project is not None
    assert (project.award_amount, project.contact_pi, project.fiscal_year) == (None, None, None)


# ------------------------------------------------------------------ paging


def _transport(pages: list[dict[str, Any]]) -> httpx.MockTransport:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        calls.append(body["offset"])
        index = min(len(calls) - 1, len(pages) - 1)
        return httpx.Response(200, json=pages[index])

    return httpx.MockTransport(handler)


def test_paging_walks_until_the_total_is_reached() -> None:
    pages = [
        {"meta": {"total": 3}, "results": [_record(project_num="A"), _record(project_num="B")]},
        {"meta": {"total": 3}, "results": [_record(project_num="C")]},
        {"meta": {"total": 3}, "results": []},
    ]
    with httpx.Client(transport=_transport(pages)) as http:
        projects = list(ReporterClient(client=http).iter_projects("vitiligo", page_size=2))
    assert [p["project_num"] for p in projects] == ["A", "B", "C"]


def test_paging_stops_on_an_empty_page_even_if_the_total_disagrees() -> None:
    """A total that never reconciles must not spin forever."""
    pages = [{"meta": {"total": 999}, "results": []}]
    with httpx.Client(transport=_transport(pages)) as http:
        assert list(ReporterClient(client=http).iter_projects("vitiligo")) == []


def test_the_api_offset_ceiling_is_respected() -> None:
    assert MAX_OFFSET < 15_000


# ------------------------------------------------------------- the summary


def test_a_passing_mention_is_not_a_vitiligo_project() -> None:
    """RePORTER matches any mention, so melanoma work cites vitiligo as a side effect."""
    melanoma = _project(
        title="Checkpoint inhibitors in melanoma",
        abstract="Some patients develop vitiligo as an immune-related adverse event.",
    )
    assert not is_vitiligo_centred(melanoma)

    centred = _project(title="Melanocyte regeneration", abstract="In vitiligo, vitiligo lesions …")
    assert is_vitiligo_centred(centred)


def test_a_vitiligo_title_is_enough() -> None:
    assert is_vitiligo_centred(_project(title="Vitiligo repigmentation", abstract=""))


def test_investigators_are_grouped_and_ranked_by_funding() -> None:
    projects = [
        _project(contact_pi="Rich Lab", award_amount=400_000, fiscal_year=2025),
        _project(contact_pi="Rich Lab", award_amount=300_000, fiscal_year=2026),
        _project(contact_pi="Small Lab", award_amount=50_000, fiscal_year=2025),
    ]
    [first, second] = active_investigators(projects, since_fiscal_year=2024)
    assert (first.name, first.awards, first.total_award) == ("Rich Lab", 2, 700_000)
    assert first.latest_fiscal_year == 2026
    assert second.name == "Small Lab"


def test_old_awards_are_left_out() -> None:
    projects = [
        _project(contact_pi="Past Lab", fiscal_year=2015),
        _project(contact_pi="Now Lab", fiscal_year=2026),
    ]
    assert [p.name for p in active_investigators(projects, since_fiscal_year=2024)] == ["Now Lab"]


def test_projects_that_only_mention_the_topic_are_left_out() -> None:
    projects = [
        _project(
            contact_pi="Melanoma Lab",
            title="Checkpoint inhibitors",
            abstract="vitiligo occurred in some patients",
            fiscal_year=2026,
        )
    ]
    assert active_investigators(projects, since_fiscal_year=2024) == []


def test_an_investigator_without_a_name_is_skipped() -> None:
    assert active_investigators([_project(contact_pi=None)], since_fiscal_year=2024) == []


def test_topic_counts_report_what_recent_work_is_about() -> None:
    projects = [
        _project(title="Resident memory T cells in vitiligo", fiscal_year=2026),
        _project(title="Vitiligo and melanocyte stem cells", fiscal_year=2026),
        _project(title="Resident memory in vitiligo relapse", fiscal_year=2015),  # too old
    ]
    counts = topic_counts(projects, ["resident memory", "melanocyte stem"], since_fiscal_year=2024)
    assert counts == {"resident memory": 1, "melanocyte stem": 1}


@pytest.mark.parametrize("limit", [1, 2])
def test_the_summary_can_be_capped(limit: int) -> None:
    projects = [
        _project(contact_pi=f"Lab {i}", award_amount=i * 1000, fiscal_year=2026) for i in range(5)
    ]
    assert len(active_investigators(projects, since_fiscal_year=2024, limit=limit)) == limit
