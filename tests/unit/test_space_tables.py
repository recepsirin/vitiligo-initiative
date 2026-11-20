"""The Space's outcome, genetics and funding rows: stored values passed on, nothing filled in."""

from __future__ import annotations

from vitiligo.reports.space_tables import association_row, award_row, award_rows, outcome_row
from vitiligo.storage import GeneticAssociation, ResearchProject
from vitiligo.storage.models import GeneticSourceKind, ResearchSourceKind


def _topline(**fields: object) -> dict[str, object]:
    row: dict[str, object] = {
        "trial": "NCT05583526",
        "instrument": "F-VASI",
        "threshold": 75,
        "week": 52,
        "source": "EADV 2026 late-breaker LB-161, as reported by HCPLive",
    }
    row.update(fields)
    return row


def _project(source_id: str, **fields: object) -> ResearchProject:
    return ResearchProject(source=ResearchSourceKind.NIH_REPORTER, source_id=source_id, **fields)


def test_an_active_arm_reads_as_the_source_wrote_it() -> None:
    row = outcome_row(
        _topline(
            arm_role="active",
            agent="ritlecitinib",
            dose_value=50.0,
            dose_unit="mg",
            frequency="QD",
            route="oral",
            n=401,
            percent=12.5,
        )
    )
    assert row["regimen"] == "50 mg QD"
    assert (row["threshold"], row["week"], row["percent"]) == ("75%", "Wk 52", "12.5%")


def test_a_placebo_arm_gets_no_dose_or_route_its_source_does_not_give() -> None:
    row = outcome_row(
        _topline(arm_role="placebo", arm_label="Placebo", agent=None, n=202, percent=2.5)
    )
    assert row["agent"] == "Placebo"  # the page pairs arms with their control by this name
    assert "regimen" not in row and "route" not in row


def test_an_award_without_dates_is_given_none() -> None:
    row = award_row(_project("ZIAAR041159-08", fiscal_year=2014, award_amount=3_195_398))
    assert "start" not in row and "end" not in row
    dated = award_row(
        _project("1R33AR084210-01", project_start="2024-07-03", project_end="2029-04-30")
    )
    assert (dated["start"], dated["end"]) == ("2024-07-03", "2029-04-30")


def test_awards_are_kept_only_for_projects_about_vitiligo() -> None:
    rows = award_rows(
        [
            _project("A-01", title="Melanocyte stem cells in vitiligo"),
            _project(
                "B-01", title="Skin immunity", abstract="Vitiligo relapses. We study vitiligo."
            ),
            _project(
                "C-01", title="Melanoma immunotherapy", abstract="Vitiligo can follow treatment."
            ),
        ]
    )
    assert [r["award"] for r in rows] == ["A-01", "B-01"]


def test_a_beta_keeps_the_catalogs_wording_that_says_it_is_one() -> None:
    row = association_row(
        GeneticAssociation(
            source=GeneticSourceKind.GWAS_CATALOG,
            source_id="GCST90476173:rs12203592",
            trait="Vitiligo",
            variant="rs12203592",
            study_accession="GCST90476173",
            odds_ratio_or_beta=0.2538,
            confidence_interval="[0.22-0.29] unit decrease",
        )
    )
    assert row["or_or_beta"] == 0.2538
    assert row["ci"] == "[0.22-0.29] unit decrease"
