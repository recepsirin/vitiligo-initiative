"""Smoke tests for the PubMed XML parser. No network calls."""

from __future__ import annotations

from vitiligo.sources.pubmed import parse_pubmed_xml
from vitiligo.storage.models import SourceKind

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">12345678</PMID>
      <Article>
        <Journal>
          <Title>Journal of Investigative Dermatology</Title>
          <JournalIssue>
            <PubDate><Year>2023</Year></PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Targeting the IFN-gamma/CXCL10 axis in vitiligo</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Vitiligo is an autoimmune disease.</AbstractText>
          <AbstractText Label="METHODS">We treated mice with a JAK inhibitor.</AbstractText>
          <AbstractText Label="RESULTS">Repigmentation was observed.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <LastName>Harris</LastName>
            <ForeName>John</ForeName>
            <Initials>J</Initials>
            <AffiliationInfo>
              <Affiliation>UMass Chan Medical School</Affiliation>
            </AffiliationInfo>
          </Author>
        </AuthorList>
        <Language>eng</Language>
        <PublicationTypeList>
          <PublicationType UI="D016428">Journal Article</PublicationType>
        </PublicationTypeList>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName UI="D014820">Vitiligo</DescriptorName></MeshHeading>
        <MeshHeading><DescriptorName UI="D015496">Interferon-gamma</DescriptorName></MeshHeading>
      </MeshHeadingList>
      <KeywordList Owner="NOTNLM">
        <Keyword>JAK inhibitors</Keyword>
        <Keyword>repigmentation</Keyword>
      </KeywordList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">12345678</ArticleId>
        <ArticleId IdType="doi">10.1234/jid.2023.001</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_parses_minimal_article() -> None:
    docs = list(parse_pubmed_xml(SAMPLE_XML))
    assert len(docs) == 1
    doc = docs[0]

    assert doc.source == SourceKind.PUBMED
    assert doc.source_id == "12345678"
    assert doc.title is not None
    assert "IFN-gamma" in doc.title
    assert doc.year == 2023
    assert doc.doi == "10.1234/jid.2023.001"
    assert doc.journal == "Journal of Investigative Dermatology"
    assert doc.language == "eng"

    assert doc.abstract is not None
    assert "BACKGROUND:" in doc.abstract
    assert "Repigmentation was observed" in doc.abstract

    assert doc.authors == [
        {
            "last": "Harris",
            "fore": "John",
            "initials": "J",
            "affiliations": ["UMass Chan Medical School"],
        }
    ]
    assert doc.mesh_terms == ["Vitiligo", "Interferon-gamma"]
    assert doc.keywords == ["JAK inhibitors", "repigmentation"]
    assert doc.publication_types == ["Journal Article"]


def test_handles_empty_article_list() -> None:
    empty = b"<?xml version='1.0'?><PubmedArticleSet></PubmedArticleSet>"
    assert list(parse_pubmed_xml(empty)) == []
