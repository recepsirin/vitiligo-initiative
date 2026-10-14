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
