"""Results from open-access papers: curated by hand, every number tied to a table cell.

Registries post results late and incompletely; papers report later weeks, other
doses and extensions. The curation file (``curation/paper-results.json``) lists
each number with its paper (PMCID), table, row and column as printed, and the
verbatim cell. ``verify`` re-reads the article's JATS XML and checks every cell
and every parsed number, so transcription errors are caught mechanically.

Every row carries its **analysis population**. Published tables mix
non-responder imputation over the randomized arm (``nri``, the convention of
registry results) with counts among patients still assessed (``as_observed``),
which run higher. The two must not be pooled blindly.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from lxml import etree

from vitiligo.reports.jak_arms import ArmEndpointRow

POPULATIONS = ("nri", "as_observed")


@dataclass(frozen=True)
class PaperTable:
    label: str
    caption: str
    footnote: str
    rows: list[list[str]]


def norm(text: str | None) -> str:
    """Comparable cell text: Unicode-normalized, ASCII dashes and spaces, collapsed."""
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub("[\u2010-\u2015\u2212]", "-", text)
    return " ".join(text.split())


def _text(el: Any) -> str:
    return norm(" ".join(el.itertext())) if el is not None else ""


def parse_tables(xml: bytes) -> list[PaperTable]:
    """Every ``<table-wrap>`` of a JATS article, cells as printed (row spans not expanded)."""
    root = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    tables = []
    for wrap in root.iter("table-wrap"):
        rows = [[_text(cell) for cell in tr if cell.tag in ("td", "th")] for tr in wrap.iter("tr")]
        tables.append(
            PaperTable(
                label=norm(wrap.findtext("label")),
                caption=_text(wrap.find("caption")),
                footnote=_text(wrap.find("table-wrap-foot")),
                rows=rows,
            )
        )
    return tables


@dataclass(frozen=True)
class PaperResult:
    """One curated number: where it is printed, and what it measures."""

    pmcid: str
    table: str
    section: str | None  # the nearest preceding section row, as printed
    row: str  # the row's first cell, as printed
    column: str  # the column header, as printed
    cell: str  # the cell, as printed
    population: str  # nri | as_observed
    trial: str
    arm_label: str
    arm_role: str  # active | placebo
    agent: str | None
    dose_value: float | None
    dose_unit: str | None
    frequency: str | None
    route: str | None
    loading_dose_value: float | None
    phototherapy: bool
    instrument: str  # F-VASI | T-VASI
    threshold: int
    week: int
    note: str = ""


def load_curation(path: Path) -> list[PaperResult]:
    names = {f.name for f in fields(PaperResult)}
    records = json.loads(path.read_text())["results"]
    return [PaperResult(**{k: v for k, v in r.items() if k in names}) for r in records]


_FRACTION = re.compile(r"^(?P<r>\d+)\s*/\s*(?P<n>\d+)\s*\((?P<pct>\d+(?:\.\d+)?)%?\)")
_N_THEN_COUNT = re.compile(r"^\(n\s*=\s*(?P<n>\d+)\)\s*(?P<r>\d+)\s*\((?P<pct>\d+(?:\.\d+)?)%\)")
_COUNT = re.compile(r"^(?P<r>\d+)\s*\((?P<pct>\d+(?:\.\d+)?)%\)")
_HEADER_N = re.compile(r"\(n\s*=\s*(\d+)\)")


def parse_cell(cell: str, column: str) -> tuple[int, int, float] | None:
    """(responders, n, percent) from a cell such as '17/33 (51.5)', '(n = 38) 14 (36.8%)',
    or '4 (8.2%)' with n taken from the column header '(n = 49)'."""
    text = norm(cell)
    for pattern in (_FRACTION, _N_THEN_COUNT):
        m = pattern.match(text)
        if m:
            return int(m["r"]), int(m["n"]), float(m["pct"])
    m = _COUNT.match(text)
    header_n = _HEADER_N.search(norm(column))
    if m and header_n:
        return int(m["r"]), int(header_n.group(1)), float(m["pct"])
    return None


def locate(table: PaperTable, section: str | None, row: str, column: str) -> str | None:
    """The printed cell at (section, row) x column, or None if the layout does not match."""
    header = next((r for r in table.rows if any(norm(c) == norm(column) for c in r)), None)
    if header is None:
        return None
    col = [norm(c) for c in header].index(norm(column))
    # Header rows often lack the row-label cell; align from the right.
    offset = len(header) - col
    current: str | None = None
    for cells in table.rows:
        if cells and cells is not header and not any(cells[1:]):
            current = cells[0]  # a section row: a spanning label, or empty value cells
            continue
        if cells and norm(cells[0]) == norm(row):
            if section is not None and norm(current) != norm(section):
                continue
            if len(cells) >= offset:
                return cells[len(cells) - offset]
    return None


def verify(results: list[PaperResult], tables: dict[str, list[PaperTable]]) -> list[str]:
    """Problems found (empty when every cell and number checks out)."""
    problems: list[str] = []
    for i, r in enumerate(results):
        where = f"#{i} {r.pmcid} {r.table} [{r.row} / {r.column}]"
        if r.population not in POPULATIONS:
            problems.append(f"{where}: unknown population {r.population!r}")
        table = next((t for t in tables.get(r.pmcid, []) if norm(t.label) == norm(r.table)), None)
        if table is None:
            problems.append(f"{where}: table not found")
            continue
        printed = locate(table, r.section, r.row, r.column)
        if printed is None:
            problems.append(f"{where}: cell not found")
            continue
        if norm(printed) != norm(r.cell):
            problems.append(f"{where}: printed {printed!r} != curated {r.cell!r}")
            continue
        parsed = parse_cell(r.cell, r.column)
        if parsed is None:
            problems.append(f"{where}: cannot parse {r.cell!r}")
            continue
        responders, n, pct = parsed
        if not 0 <= responders <= n or abs(100 * responders / n - pct) > 0.051:
            problems.append(f"{where}: {responders}/{n} does not round to {pct}%")
    return problems


def to_arm_rows(results: list[PaperResult]) -> list[ArmEndpointRow]:
    """Arm-table rows, flagged with their source and analysis population."""
    rows = []
    for r in results:
        parsed = parse_cell(r.cell, r.column)
        if parsed is None:
            raise ValueError(f"cannot parse {r.cell!r} ({r.pmcid} {r.table})")
        responders, n, pct = parsed
        section = f"{r.section} / " if r.section else ""
        rows.append(
            ArmEndpointRow(
                study_id=r.trial,
                source_id=r.trial,
                trial_agents=r.agent or "",
                arm_label=r.arm_label,
                period=None,
                arm_role=r.arm_role,
                arm_agent=r.agent,
                dose_value=r.dose_value,
                dose_unit=r.dose_unit,
                loading_dose_value=r.loading_dose_value,
                frequency=r.frequency,
                route=r.route,
                phototherapy=r.phototherapy,
                endpoint=f"{r.instrument}{r.threshold}",
                instrument=r.instrument,
                threshold=r.threshold,
                body_region="face" if r.instrument == "F-VASI" else "total body",
                assessor=None,
                week=r.week,
                week_source="paper_table",
                outcome_type=None,
                n_analyzed=n,
                percent=pct,
                responders=responders,
                responders_derived=False,
                value_raw=r.cell,
                outcome_title=f"{r.pmcid} {r.table}: {section}{r.row} - {r.column}",
                row_label=None,
                flags=["from_publication", f"population:{r.population}", f"source:{r.pmcid}"],
            )
        )
    return rows


_PER_DAY = {"QD": 1.0, "BID": 2.0}


def _key(row: ArmEndpointRow) -> tuple[Any, ...]:
    """Regimen identity by daily dose: registries often leave the frequency blank."""
    daily = None
    if row.dose_value is not None:
        daily = row.dose_value * _PER_DAY.get(row.frequency or "QD", 1.0)
    return (
        row.source_id,
        row.arm_role,
        row.arm_agent,
        daily,
        row.loading_dose_value,
        row.phototherapy,
        row.instrument,
        row.threshold,
        row.week,
    )


def cross_check(
    paper: list[ArmEndpointRow], registry: list[ArmEndpointRow]
) -> list[dict[str, Any]]:
    """Paper rows that the registry also reports, with both values (agreement check)."""
    index = {_key(r): r for r in registry if r.responders is not None and r.n_analyzed}
    out = []
    for p in paper:
        match = index.get(_key(p))
        if match is not None:
            out.append(
                {
                    "row": p.outcome_title,
                    "paper": f"{p.responders}/{p.n_analyzed}",
                    "registry": f"{match.responders}/{match.n_analyzed}",
                    "agree": (p.responders, p.n_analyzed) == (match.responders, match.n_analyzed),
                }
            )
    return out


def new_rows(paper: list[ArmEndpointRow], registry: list[ArmEndpointRow]) -> list[ArmEndpointRow]:
    """Paper rows the registry does not already report."""
    known = {_key(r) for r in registry}
    return [p for p in paper if _key(p) not in known]


def load_toplines(path: Path) -> list[ArmEndpointRow]:
    """Arm rows from public topline numbers (press releases, conference reports).

    Responders are derived from the reported percentage and arm size, so they
    carry rounding error of up to half a patient.
    """
    return toplines_from(json.loads(path.read_text())["results"])


def overlapping_rows(
    existing: Sequence[ArmEndpointRow], new: Sequence[ArmEndpointRow]
) -> list[ArmEndpointRow]:
    """Rows of ``new`` for an arm-week (same arm, endpoint and week) already in ``existing``.

    Adding such a row would count the same result twice.
    """

    def key(r: ArmEndpointRow) -> tuple[Any, ...]:
        return (r.source_id, r.arm_role, r.arm_agent, r.dose_value, r.frequency,
                r.instrument, r.threshold, r.week)  # fmt: skip

    seen = {key(r) for r in existing}
    return [r for r in new if key(r) in seen]


def toplines_from(entries: list[dict[str, Any]]) -> list[ArmEndpointRow]:
    """Arm rows from topline entries in the format of ``curation/topline-results.json``."""
    rows = []
    for t in entries:
        responders = round(t["percent"] / 100 * t["n"])
        rows.append(
            ArmEndpointRow(
                study_id=t["trial"],
                source_id=t["trial"],
                trial_agents=t["agent"] or "",
                arm_label=t["arm_label"],
                period=None,
                arm_role=t["arm_role"],
                arm_agent=t["agent"],
                dose_value=t["dose_value"],
                dose_unit=t["dose_unit"],
                loading_dose_value=None,
                frequency=t["frequency"],
                route=t["route"],
                phototherapy=bool(t.get("phototherapy", False)),
                endpoint=f"{t['instrument']}{t['threshold']}",
                instrument=t["instrument"],
                threshold=t["threshold"],
                body_region=t.get(
                    "body_region", "face" if t["instrument"] == "F-VASI" else "total body"
                ),
                assessor=None,
                week=t["week"],
                week_source="topline",
                outcome_type="PRIMARY",
                n_analyzed=t["n"],
                percent=t["percent"],
                responders=responders,
                responders_derived=True,
                value_raw=f"{t['percent']}% of {t['n']}",
                outcome_title=f"{t['source']} ({t['public_on']})",
                row_label=None,
                flags=[
                    "from_topline",
                    f"population:{t['population']}",
                    f"source:{t['source_url']}",
                ],
            )
        )
    return rows
