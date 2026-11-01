"""A paper's tables, kept as rows.

A clinical paper puts its numbers in tables and its reasoning in prose. The
PMC parser read only ``<p>`` elements, so of 33 published vitiligo trials held
in full, the collected body carried an extractable responder count for exactly
one; the 94 tables of the other 32 were in the XML the whole time. That was
never a licence problem or an access problem.

Two things shape this module.

**A cell means nothing without its column.** Table 2 of PMID 39679850 reads
"Repigmentation at 18 months", and its cell says ``23 (76.7%)``. The
denominator is not in the cell: it is in the column header, ``Group 1
(n = 30)``. Flattening a table into a sentence loses which cell sat under
which column, which is the same mistake as dropping the table, one level
down. So rows stay rows and the header is kept separately.

**JATS and HTML are the same shape.** A JATS ``<table-wrap>`` and an HTML
``<table>`` both hold ``<tr>`` of ``<th>`` and ``<td>``, so one reader serves
PMC's XML and a publisher's open-access page alike.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from lxml import etree, html


class Table(TypedDict):
    """One table: what it is called, what it is about, and its cells."""

    label: str
    caption: str
    header: list[str]
    rows: list[list[str]]


def cell_text(cell: etree._Element) -> str:
    """One cell's text, whitespace collapsed."""
    return " ".join("".join(cell.itertext()).split()).strip()


def read_table(element: etree._Element, *, label: str = "", caption: str = "") -> Table | None:
    """The rows of one table element, or ``None`` when it holds nothing.

    ``label`` and ``caption`` are passed in because JATS keeps them in
    siblings of the table while HTML keeps the caption inside it.
    """
    header_rows = [[cell_text(c) for c in tr.iter("th")] for tr in element.iter("tr")]
    rows = [
        cells
        for tr in element.iter("tr")
        if (cells := [cell_text(c) for c in tr.iter("td")]) and any(cells)
    ]
    header = next((h for h in header_rows if any(h)), [])
    if not rows and not header:
        return None
    return {"label": label, "caption": caption, "header": header, "rows": rows}


def tables_from_jats(article: etree._Element) -> list[Table]:
    """Every table in a JATS article, in document order."""
    out: list[Table] = []
    for wrap in article.iter("table-wrap"):
        label_el = wrap.find("./label")
        caption_el = wrap.find("./caption")
        table = read_table(
            wrap,
            label=cell_text(label_el) if label_el is not None else "",
            caption=cell_text(caption_el) if caption_el is not None else "",
        )
        if table is not None:
            out.append(table)
    return out


def tables_from_html(payload: bytes | str) -> list[Table]:
    """Every table in an HTML page, in document order.

    A publisher's open-access page carries the same tables as the PDF and
    carries them as markup, which is why it is preferred over the PDF: a PDF
    gives back lines of text with the columns already lost.
    """
    try:
        root = html.fromstring(payload)
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        return []
    out: list[Table] = []
    for element in root.iter("table"):
        caption_el = element.find("./caption")
        table = read_table(element, caption=cell_text(caption_el) if caption_el is not None else "")
        if table is not None:
            out.append(table)
    return out


_NUMBER = re.compile(r"\d")


def has_data(table: Table) -> bool:
    """True when a table holds numbers in rows, not layout or a menu.

    An HTML page lays out its furniture in tables too. The repository copy of
    PMID 19547993 answered with thirteen of them -- a title block, a
    four-column pitch for the repository, an export-format menu -- and not one
    number among them, which was enough to pass a check that asked only
    whether any table existed. A results table has at least two rows, at least
    two columns, and digits in more than one cell.
    """
    rows = [r for r in table["rows"] if len(r) >= 2]
    if len(rows) < 2 and not (table["header"] and len(rows) >= 1):
        return False
    numeric = sum(1 for r in rows for c in r if _NUMBER.search(c))
    return numeric >= 2


def render_tables(tables: list[Table] | list[dict[str, Any]]) -> str:
    """The tables as text, one row to a line, so a search can reach them."""
    out: list[str] = []
    for table in tables:
        title = " ".join(p for p in (table.get("label"), table.get("caption")) if p)
        lines = [f"### {title}" if title else "### Table"]
        if table.get("header"):
            lines.append(" | ".join(table["header"]))
        lines += [" | ".join(r) for r in table.get("rows", [])]
        out.append("\n".join(lines))
    return "\n\n".join(out)
