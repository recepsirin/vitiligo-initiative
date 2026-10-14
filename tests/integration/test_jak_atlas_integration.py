"""Integration tests for the JAK atlas on a seeded temp DB."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from sqlmodel import Session

from vitiligo.reports.jak import (
    atlas_to_dict,
    build_jak_atlas,
    render_jak_atlas_markdown,
    write_jak_atlas_csv,
)
from vitiligo.storage import (
    Document,
    Prior,
    PriorKind,
    PriorSourceKind,
    SourceKind,
    Trial,
    TrialSourceKind,
    get_engine,
)

pytestmark = pytest.mark.integration


def _ctgov_study(
    nct: str, org_id: str, secondary: list[str], pmids: list[str], *, with_results: bool
) -> dict:
    study: dict = {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct,
                "orgStudyIdInfo": {"id": org_id},
                "secondaryIdInfos": [{"id": s} for s in secondary],
            },
            "referencesModule": {
                "references": [{"pmid": p, "type": "RESULT"} for p in pmids]
                + [{"pmid": "99999999", "type": "BACKGROUND"}]
            },
        },
    }
    if not with_results:
        return study
    study["resultsSection"] = {
        "outcomeMeasuresModule": {
            "outcomeMeasures": [
                {
                    "type": "PRIMARY",
                    "title": "F-VASI75 at Week 24",
                    "paramType": "NUMBER",
                    "unitOfMeasure": "percentage of participants",
                    "groups": [{"id": "OG000", "title": "Ruxolitinib"}],
                    "classes": [
                        {"categories": [{"measurements": [{"groupId": "OG000", "value": "30"}]}]}
                    ],
                }
            ]
        }
    }
    return study


@pytest.fixture
def seeded_jak_db(test_db_path: Path) -> Path:
    rows = [
        # CT.gov ruxolitinib trial with posted results, linked to a CTIS record by secondary ID.
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT10000001",
            brief_title="Ruxolitinib cream in vitiligo",
            phases=["PHASE3"],
            status="COMPLETED",
            has_results=True,
            interventions=[{"name": "Ruxolitinib cream", "type": "DRUG"}],
            arm_groups=[
                {
                    "label": "Ruxolitinib",
                    "type": "EXPERIMENTAL",
                    "intervention_names": ["Drug: Ruxolitinib cream"],
                }
            ],
            sponsors=[{"role": "lead", "name": "Sponsor A", "class": "INDUSTRY"}],
            raw_metadata={
                "study": _ctgov_study(
                    "NCT10000001", "PROT-0001", ["2023-500001-11-00"], ["111"], with_results=True
                )
            },
        ),
        Trial(
            source=TrialSourceKind.EUCTR,
            source_id="2023-500001-11-00",
            brief_title="PROT-0001",
            phases=["PHASE3"],
            status="AUTHORISED",
            interventions=[{"name": "Ruxolitinib cream", "other_names": ["ruxolitinib"]}],
            raw_metadata={"search": {"shortTitle": "PROT-0001"}},
        ),
        # CT.gov TYK2 trial whose CTIS twin has no intervention data: linked by protocol code.
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT10000002",
            brief_title="Deucravacitinib in vitiligo",
            phases=["PHASE2"],
            status="RECRUITING",
            interventions=[{"name": "Deucravacitinib", "type": "DRUG"}],
            raw_metadata={
                "study": _ctgov_study("NCT10000002", "23-PP-99", [], [], with_results=False)
            },
        ),
        Trial(
            source=TrialSourceKind.EUCTR,
            source_id="2023-500002-22-00",
            brief_title="23-PP-99",
            interventions=[],
            raw_metadata={"search": {"shortTitle": "23-PP-99"}},
        ),
        # Extension study naming its parent NCT as a secondary ID: a distinct study.
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT10000004",
            brief_title="Ruxolitinib cream long-term extension",
            interventions=[{"name": "Ruxolitinib cream", "type": "DRUG"}],
            raw_metadata={
                "study": _ctgov_study(
                    "NCT10000004", "PROT-0002", ["NCT10000001"], [], with_results=False
                )
            },
        ),
        # Non-JAK trial must not appear.
        Trial(
            source=TrialSourceKind.CTGOV,
            source_id="NCT10000003",
            brief_title="Tacrolimus ointment",
            interventions=[{"name": "Tacrolimus", "type": "DRUG"}],
        ),
        Document(
            source=SourceKind.PUBMED,
            source_id="111",
            title="Ruxolitinib phase 3 results",
            abstract="Registered as NCT10000001.",
        ),
        # Same paper as PMID 111, held as a PMC full-text record: must not count twice.
        Document(
            source=SourceKind.PMC,
            source_id="PMC111",
            title="Ruxolitinib phase 3 results",
            abstract="Registered as NCT10000001.",
            raw_metadata={"pmid": "111", "pmcid": "PMC111"},
        ),
        Document(
            source=SourceKind.PUBMED,
            source_id="222",
            title="Deucravacitinib case series",
            abstract="TYK2 inhibition in vitiligo.",
        ),
        Prior(
            source=PriorSourceKind.OPENTARGETS,
            kind=PriorKind.DRUG,
            source_id="CHEMBL1789941",
            disease_id="EFO_0004208",
            name="RUXOLITINIB",
            clinical_stage="APPROVAL",
            mechanisms=[{"mechanism": "Tyrosine-protein kinase JAK1 inhibitor"}],
        ),
    ]
    with Session(get_engine(), expire_on_commit=False) as session:
        session.add_all(rows)
        session.commit()
    return test_db_path


def test_atlas_groups_registry_records_into_studies(seeded_jak_db) -> None:
    atlas = build_jak_atlas()
    by_id = {t.source_id: t for t in atlas.trials}

    assert set(by_id) == {
        "NCT10000001",
        "2023-500001-11-00",
        "NCT10000002",
        "2023-500002-22-00",
        "NCT10000004",
    }
    assert by_id["NCT10000004"].study_id == "NCT10000004"
    assert by_id["2023-500001-11-00"].study_id == "NCT10000001"
    assert by_id["NCT10000001"].linked_records == ["2023-500001-11-00"]

    twin = by_id["2023-500002-22-00"]
    assert twin.study_id == "NCT10000002"
    assert twin.agents == ["deucravacitinib"]
    assert twin.match_basis == "linked_registry_record"


def test_atlas_agent_summaries_count_studies(seeded_jak_db) -> None:
    atlas = build_jak_atlas()
    agents = {a.name: a for a in atlas.agents}

    rux = agents["ruxolitinib"]
    assert (rux.studies, rux.registry_records, rux.studies_with_posted_results) == (2, 3, 1)
    assert rux.prior_stage == "APPROVAL"
    assert rux.mechanisms == ["Tyrosine-protein kinase JAK1 inhibitor"]
    assert rux.statuses == {"COMPLETED": 1, "UNKNOWN": 1}
    assert rux.papers_mentioning == 1

    assert agents["deucravacitinib"].studies == 1
    assert agents["deucravacitinib"].papers_mentioning == 1
    # Agents ordered by Open Targets stage first.
    assert atlas.agents[0].name == "ruxolitinib"


def test_atlas_publications_and_outcomes(seeded_jak_db) -> None:
    atlas = build_jak_atlas()
    rux = next(t for t in atlas.trials if t.source_id == "NCT10000001")
    # RESULT reference kept, BACKGROUND dropped, citing paper not duplicated.
    assert [(p.pmid, p.relation, p.in_corpus) for p in rux.publications] == [
        ("111", "registry:RESULT", True)
    ]
    assert rux.outcomes[0].measurements[0].value == "30"
    assert rux.jak_arm_types == ["EXPERIMENTAL"]


def test_atlas_renderers(seeded_jak_db, tmp_path: Path) -> None:
    atlas = build_jak_atlas()

    payload = json.loads(json.dumps(atlas_to_dict(atlas)))
    assert payload["agents"][0]["name"] == "ruxolitinib"

    markdown = render_jak_atlas_markdown(atlas)
    assert "| ruxolitinib |" in markdown
    # One study row for the linked pair, naming the CTIS twin.
    assert markdown.count("[NCT10000001](https://clinicaltrials.gov/study/NCT10000001) |") == 1
    assert "2023-500001-11-00" in markdown

    paths = write_jak_atlas_csv(atlas, tmp_path / "csv")
    with paths[0].open(encoding="utf-8") as fh:
        trials = list(csv.DictReader(fh))
    assert {r["study_id"] for r in trials} == {"NCT10000001", "NCT10000002", "NCT10000004"}
    with paths[1].open(encoding="utf-8") as fh:
        outcomes = list(csv.DictReader(fh))
    assert [(r["source_id"], r["value"]) for r in outcomes] == [("NCT10000001", "30")]


def test_report_jak_cli_writes_all_outputs(seeded_jak_db, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from vitiligo.cli import app

    json_path = tmp_path / "atlas.json"
    md_path = tmp_path / "atlas.md"
    csv_dir = tmp_path / "csv"
    result = CliRunner().invoke(
        app,
        [
            "report",
            "jak",
            "--json",
            str(json_path),
            "--markdown",
            str(md_path),
            "--csv-dir",
            str(csv_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "3 studies" in result.output
    payload = json.loads(json_path.read_text())
    assert {a["name"] for a in payload["agents"] if a["studies"]} == {
        "ruxolitinib",
        "deucravacitinib",
    }
    assert md_path.read_text().startswith("# JAK Inhibitors in Vitiligo")
    assert sorted(p.name for p in csv_dir.iterdir()) == [
        "adverse_events.csv",
        "outcomes.csv",
        "trials.csv",
    ]


def test_report_jak_arms_cli_writes_table(seeded_jak_db, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from vitiligo.cli import app

    csv_path = tmp_path / "arms.csv"
    json_path = tmp_path / "arms.json"
    result = CliRunner().invoke(
        app, ["report", "jak-arms", "--csv", str(csv_path), "--json", str(json_path)]
    )
    assert result.exit_code == 0, result.output
    with csv_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["source_id"], r["endpoint"], r["week"], r["value_raw"]) for r in rows] == [
        ("NCT10000001", "F-VASI75", "24", "30")
    ]
    assert "n_missing" in rows[0]["flags"]  # seeded result has no denominator
    assert json.loads(json_path.read_text())["summary"]["model_ready_rows"] == 0
