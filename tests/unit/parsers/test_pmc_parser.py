"""Smoke tests for the PMC JATS parser. No network calls."""

from __future__ import annotations

from vitiligo.sources.pmc import parse_pmc_xml
from vitiligo.storage.models import SourceKind

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset>
  <article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article" xml:lang="en">
    <front>
      <journal-meta>
        <journal-title-group>
          <journal-title>Journal of Investigative Dermatology</journal-title>
        </journal-title-group>
      </journal-meta>
      <article-meta>
        <article-id pub-id-type="pmcid">PMC9999999</article-id>
        <article-id pub-id-type="pmid">11111111</article-id>
        <article-id pub-id-type="doi">10.1234/jid.2024.001</article-id>
        <title-group>
          <article-title>JAK inhibition halts vitiligo spread</article-title>
        </title-group>
        <contrib-group>
          <contrib contrib-type="author">
            <name>
              <surname>Harris</surname>
              <given-names>John</given-names>
            </name>
          </contrib>
        </contrib-group>
        <pub-date pub-type="epub">
          <year>2024</year>
        </pub-date>
        <abstract>
          <p>We show that JAK inhibition halts disease activity in vitiligo.</p>
        </abstract>
        <kwd-group>
          <kwd>JAK</kwd>
          <kwd>vitiligo</kwd>
        </kwd-group>
      </article-meta>
    </front>
    <body>
      <sec>
        <title>Introduction</title>
        <p>Vitiligo is autoimmune.</p>
      </sec>
      <sec>
        <title>Methods</title>
        <p>We treated mice.</p>
      </sec>
      <sec>
        <title>Results</title>
        <p>Repigmentation occurred.</p>
      </sec>
    </body>
  </article>
</pmc-articleset>
"""


def test_parses_minimal_pmc_article() -> None:
    docs = list(parse_pmc_xml(SAMPLE_XML))
    assert len(docs) == 1
    doc = docs[0]

    assert doc.source == SourceKind.PMC
    assert doc.source_id == "PMC9999999"
    assert doc.title is not None and "vitiligo" in doc.title.lower()
    assert doc.year == 2024
    assert doc.doi == "10.1234/jid.2024.001"
    assert doc.journal == "Journal of Investigative Dermatology"
    assert doc.language == "en"
    assert (
        doc.abstract is not None and "autoimmune" not in doc.abstract
    )  # abstract is the front one only
    assert doc.authors == [{"last": "Harris", "fore": "John"}]
    assert doc.keywords == ["JAK", "vitiligo"]
    assert doc.publication_types == ["research-article"]

    raw = doc.raw_metadata
    sections = raw["sections"]
    assert "introduction" in sections
    assert "methods" in sections
    assert "results" in sections
    assert "Repigmentation occurred" in raw["full_text"]


def test_handles_empty_pmc_payload() -> None:
    empty = b"<?xml version='1.0'?><pmc-articleset></pmc-articleset>"
    assert list(parse_pmc_xml(empty)) == []


def _abstract_of(abstract_xml: str) -> str | None:
    from lxml import etree

    from vitiligo.sources.pmc import _collect_abstract

    return _collect_abstract(etree.fromstring(f"<article><front>{abstract_xml}</front></article>"))


def test_abstract_inline_markup_is_not_repeated() -> None:
    """Italic/sup text used to be appended again (e.g. 'P' in '<italic>P</italic> < 0.05')."""
    text = _abstract_of(
        "<abstract><p>Repigmentation improved (<italic>P</italic> &lt; 0.05) with "
        "<italic>Vernonia anthelmintica</italic> extract.</p></abstract>"
    )
    assert text == "Repigmentation improved (P < 0.05) with Vernonia anthelmintica extract."


def test_structured_abstract_keeps_section_labels_once() -> None:
    text = _abstract_of(
        "<abstract><title>Abstract</title>"
        "<sec><title>Background</title><p>Alpha <sup>2</sup> beta.</p></sec>"
        "<sec><title>Results</title><p>Gamma.</p></sec></abstract>"
    )
    assert text == "Background: Alpha 2 beta.\n\nResults: Gamma."


# A results table as a dermatology journal prints one: the group size is in
# the column header and the cell is a count with its percentage. Modelled on
# Table 2 of PMID 39679850, "Repigmentation at 18 months".
TABLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset>
  <article article-type="research-article">
    <front><article-meta>
      <article-id pub-id-type="pmcid">PMC8888888</article-id>
      <title-group><article-title>Grafting in stable vitiligo</article-title></title-group>
    </article-meta></front>
    <body>
      <sec><title>Results</title><p>Repigmentation was better in group 1.</p>
        <table-wrap id="t2">
          <label>TABLE 2</label>
          <caption><p>Repigmentation at 18 months.</p></caption>
          <table>
            <thead><tr>
              <th>Repigmentation</th><th>Group 1 (n = 30)</th><th>Group 2 (n = 30)</th><th>p</th>
            </tr></thead>
            <tbody>
              <tr><td>Excellent</td><td>23 (76.7%)</td><td>22 (73.3%)</td><td>0.02</td></tr>
              <tr><td>None</td><td>3 (10%)</td><td>7 (23.4%)</td><td>0.14</td></tr>
            </tbody>
          </table>
        </table-wrap>
      </sec>
    </body>
  </article>
</pmc-articleset>
"""


def _table_doc():
    return next(iter(parse_pmc_xml(TABLE_XML)))


def test_a_results_table_is_not_thrown_away() -> None:
    """The parser read only <p> elements, so every table was discarded.

    Of 33 published vitiligo trials held in full, the collected body carried
    an extractable responder count for exactly one. The tables of the other
    32 were in the XML the whole time: 94 of them, none of them read. That is
    not a licence problem or an access problem.
    """
    tables = (_table_doc().raw_metadata or {})["tables"]
    assert len(tables) == 1
    assert tables[0]["label"] == "TABLE 2"
    assert "Repigmentation at 18 months" in tables[0]["caption"]


def test_the_group_size_survives_in_the_column_header() -> None:
    """A cell reading "23 (76.7%)" is meaningless without its denominator.

    The denominator is not in the cell; it is in the column header, as
    "Group 1 (n = 30)". Flattening the table into a sentence would lose the
    association between the two, which is the same mistake as dropping the
    table, one level down.
    """
    table = (_table_doc().raw_metadata or {})["tables"][0]
    assert table["header"] == ["Repigmentation", "Group 1 (n = 30)", "Group 2 (n = 30)", "p"]
    assert table["rows"][0] == ["Excellent", "23 (76.7%)", "22 (73.3%)", "0.02"]
    assert table["rows"][1][1] == "3 (10%)"


def test_the_rendered_tables_reach_the_searchable_text() -> None:
    """Whatever is not in ``full_text`` is not embedded and cannot be found."""
    doc = _table_doc()
    body = (doc.raw_metadata or {})["full_text"]
    assert "## Tables" in body
    assert "Group 1 (n = 30)" in body
    assert "23 (76.7%)" in body
    assert (doc.raw_metadata or {})["sections"]["tables"].startswith("### TABLE 2")

    # One row per line, so a reader of the text can still tell which cell sits
    # under which column. Collapsing the rows together would put "23 (76.7%)"
    # and "7 (23.4%)" on one line and lose which row each belongs to.
    lines = (doc.raw_metadata or {})["sections"]["tables"].splitlines()
    assert lines[1] == "Repigmentation | Group 1 (n = 30) | Group 2 (n = 30) | p"
    assert lines[2] == "Excellent | 23 (76.7%) | 22 (73.3%) | 0.02"
    assert lines[3] == "None | 3 (10%) | 7 (23.4%) | 0.14"


def test_an_article_with_no_table_gains_no_table_section() -> None:
    """The common case must not grow an empty heading."""
    doc = next(iter(parse_pmc_xml(SAMPLE_XML)))
    assert (doc.raw_metadata or {})["tables"] == []
    assert "## Tables" not in (doc.raw_metadata or {})["full_text"]
    assert "tables" not in (doc.raw_metadata or {})["sections"]
