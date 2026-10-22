"""Tests for curated paper results: table parsing, cell location, verification, merging."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vitiligo.reports import paper_results as pr

JATS = b"""<article><body>
<table-wrap><label>Table 2</label><caption><p>Endpoints at week 24</p></caption>
<table><thead><tr><th/><th>PBO (n = 46)</th><th>UPA 11 mg (n = 47)</th></tr></thead>
<tbody>
<tr><td>F-VASI 75 at week 24</td><td/><td/></tr>
<tr><td>Responder, n (%) (95% CI)</td><td>1 (2.2%) (0.0&#8211;6.4)</td><td>9 (19.1%) (7.9&#8211;30.4)</td></tr>
<tr><td>T-VASI 50 at week 24</td><td/><td/></tr>
<tr><td>Responder, n (%) (95% CI)</td><td>1 (2.2%) (0&#8211;6.4)</td><td>3 (6.4%) (0&#8211;13.4)</td></tr>
</tbody></table>
<table-wrap-foot><p>Non-responder imputation.</p></table-wrap-foot></table-wrap>
<table-wrap><label>TABLE 1</label><caption><p>Through 3 years</p></caption><table>
<tr><td>Endpoint, n / N (%)</td><td>Week 24</td><td>Week 52</td></tr>
<tr><td colspan="3">All patients</td></tr>
<tr><td>F&#8208;VASI75 c</td><td>20/94 (21.3)</td><td>34/94 (36.2)</td></tr>
<tr><td colspan="3">Patients randomised to 1.5% BID</td></tr>
<tr><td>F&#8208;VASI75 c</td><td>10/33 (30.3)</td><td>17/33 (51.5)</td></tr>
</table></table-wrap>
</body></article>"""


def _result(**kwargs: object) -> pr.PaperResult:
    base: dict[str, object] = {
        "pmcid": "PMC1", "table": "Table 2", "section": "F-VASI 75 at week 24",
        "row": "Responder, n (%) (95% CI)", "column": "UPA 11 mg (n = 47)",
        "cell": "9 (19.1%) (7.9\u201330.4)", "population": "nri", "trial": "NCT04927975",
        "arm_label": "Upa 11 mg", "arm_role": "active", "agent": "upadacitinib",
        "dose_value": 11.0, "dose_unit": "mg", "frequency": "QD", "route": "oral",
        "loading_dose_value": None, "phototherapy": False, "instrument": "F-VASI",
        "threshold": 75, "week": 24,
    }  # fmt: skip
    base.update(kwargs)
    return pr.PaperResult(**base)  # type: ignore[arg-type]


def test_parse_tables_and_locate_cells_by_section() -> None:
    tables = pr.parse_tables(JATS)
    assert [t.label for t in tables] == ["Table 2", "TABLE 1"]
    assert tables[0].footnote == "Non-responder imputation."
    t2, t1 = tables
    assert pr.locate(
        t2, "T-VASI 50 at week 24", "Responder, n (%) (95% CI)", "UPA 11 mg (n = 47)"
    ) == ("3 (6.4%) (0-13.4)")
    # Spanning section rows tell the pooled group from the 1.5% BID arm.
    assert (
        pr.locate(t1, "Patients randomised to 1.5% BID", "F-VASI75 c", "Week 52") == "17/33 (51.5)"
    )
    assert pr.locate(t1, "All patients", "F-VASI75 c", "Week 52") == "34/94 (36.2)"
    assert pr.locate(t1, None, "F-VASI90 c", "Week 52") is None


@pytest.mark.parametrize(
    ("cell", "column", "expected"),
    [
        ("17/33 (51.5)", "Week 52", (17, 33, 51.5)),
        ("9/9 (100)", "Week 156", (9, 9, 100.0)),
        ("(n = 38) 24 (63.2%) (47.8\u201378.5)", "UPA 11 mg", (24, 38, 63.2)),
        ("4 (8.2%) (0.5\u201315.8)", "UPA 6 mg (n = 49)", (4, 49, 8.2)),
        ("4 (8.2%) (0.5\u201315.8)", "UPA 6 mg", None),  # no denominator anywhere
        ("\u221214.36 (\u221224.86 to \u22123.85)", "PBO", None),  # not a responder count
    ],
)
def test_parse_cell(cell: str, column: str, expected: tuple[int, int, float] | None) -> None:
    assert pr.parse_cell(cell, column) == expected


def test_verify_accepts_printed_cells_and_catches_errors() -> None:
    tables = {"PMC1": pr.parse_tables(JATS)}
    good = _result()
    assert pr.verify([good], tables) == []
    problems = pr.verify(
        [
            replace(good, cell="10 (19.1%) (7.9\u201330.4)"),  # mistyped count
            replace(good, section="T-VASI 50 at week 24"),  # wrong section
            replace(good, population="itt"),
            replace(good, table="Table 9"),
        ],
        tables,
    )
    assert len(problems) == 4
    assert "printed" in problems[0] and "printed" in problems[1]
    assert "population" in problems[2] and "table not found" in problems[3]


def test_rows_are_flagged_and_merged_by_daily_dose() -> None:
    [row] = pr.to_arm_rows([_result()])
    assert (row.responders, row.n_analyzed, row.percent) == (9, 47, 19.1)
    assert row.flags == ["from_publication", "population:nri", "source:PMC1"]
    assert row.body_region == "face" and row.week_source == "paper_table"
    # The registry leaves frequency blank for this arm; daily dose still matches.
    registry = replace(row, frequency=None, flags=[], outcome_title="registry")
    assert pr.cross_check([row], [registry])[0]["agree"] is True
    assert pr.new_rows([row], [registry]) == []
    later = pr.to_arm_rows([_result(week=52)])
    assert pr.new_rows(later, [registry]) == later
    disagreeing = replace(registry, responders=8)
    assert pr.cross_check([row], [disagreeing])[0]["agree"] is False


def test_curation_file_is_well_formed() -> None:
    """The shipped curation file loads, parses and uses known populations (offline)."""
    from pathlib import Path

    results = pr.load_curation(Path("curation/paper-results.json"))
    assert len(results) >= 40
    assert {r.population for r in results} <= set(pr.POPULATIONS)
    rows = pr.to_arm_rows(results)
    assert all(r.responders is not None and r.n_analyzed for r in rows)
    assert all(
        0 <= r.responders <= r.n_analyzed for r in rows if r.responders is not None and r.n_analyzed
    )


def test_overlapping_rows_catch_a_result_counted_twice() -> None:
    def entry(arm_role: str, dose: float | None, week: int) -> dict[str, object]:
        return {
            "trial": "NCT06072183", "arm_label": f"{arm_role} {dose}", "arm_role": arm_role,
            "agent": "ritlecitinib" if dose else None, "dose_value": dose,
            "dose_unit": "mg" if dose else None, "frequency": "QD" if dose else None,
            "route": "oral" if dose else None, "instrument": "F-VASI", "threshold": 75,
            "week": week, "n": 200, "percent": 10.0, "source_url": "u", "public_on": "d",
            "source": "s", "population": "nri",
        }  # fmt: skip

    existing = pr.toplines_from([entry("active", 100.0, 52), entry("placebo", None, 52)])
    new = pr.toplines_from(
        [entry("active", 50.0, 52), entry("placebo", None, 52), entry("placebo", None, 36)]
    )
    overlap = pr.overlapping_rows(existing, new)
    assert [(r.arm_role, r.week) for r in overlap] == [("placebo", 52)]


def test_topline_curation_is_frozen() -> None:
    """v0.4, v0.5 and the evidence ranking's base model are defined by this file.

    Their sealed data hashes, and the scripts that check them, rely on it staying
    as it is. New toplines go in a new file under a new pre-registration.
    """
    import hashlib
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "curation" / "topline-results.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "8abd1de39294cd82c2748ba1d1f6bc67e3745e854f057491aa03351753e5a85e"
    )
