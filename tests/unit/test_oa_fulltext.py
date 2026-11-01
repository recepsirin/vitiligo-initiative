"""Tests for reading a paper's open-access copy, and for what we decline to read."""

from __future__ import annotations

import httpx
import pytest

from vitiligo.sources.oa_fulltext import (
    OpenCopy,
    fetch_open_copy,
    find_open_copy,
    read_open_copy,
    read_payload,
)
from vitiligo.sources.tables import has_data, tables_from_html

HTML_TABLE = b"""<html><body>
<p>Repigmentation was better in group 1.</p>
<table>
  <caption>Table 2. Repigmentation at 18 months.</caption>
  <tr><th>Repigmentation</th><th>Group 1 (n = 30)</th><th>Group 2 (n = 30)</th></tr>
  <tr><td>Excellent</td><td>23 (76.7%)</td><td>22 (73.3%)</td></tr>
  <tr><td>None</td><td>3 (10%)</td><td>7 (23.4%)</td></tr>
</table>
</body></html>"""


def _copy(licence: str, url: str = "https://example.org/a") -> OpenCopy:
    return OpenCopy(
        doi="10.1/x", licence=licence, host_type="publisher", version="published", url=url
    )


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("licence", "may"),
    [
        ("cc-by", True),
        ("cc-by-nc", True),
        ("CC-BY-NC-ND", True),
        ("", False),
        ("other-oa", False),
        ("publisher-specific, author manuscript", False),
    ],
)
def test_only_a_creative_commons_licence_is_fetched(licence: str, may: bool) -> None:
    """Free to read is not free to copy.

    Of the 154 open-access copies Unpaywall found for this corpus, 83 are
    "bronze" or unlicensed: the publisher has put the page outside the
    paywall and granted nothing. Taking those would be a decision nobody
    recorded, so the licence is the gate and it is checked before the request
    is made, not after.
    """
    assert _copy(licence).may_fetch is may


def test_an_unlicensed_copy_is_never_requested() -> None:
    """The gate has to stop the request, not just discard the answer."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=HTML_TABLE)

    with _client(handler) as client:
        assert fetch_open_copy(_copy("other-oa"), client=client, cache=None) is None
    assert calls == [], "a request went out for a copy we have no licence to take"


def test_a_licensed_copy_is_fetched_and_its_tables_read() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=HTML_TABLE, headers={"content-type": "text/html"})

    with _client(handler) as client:
        got = fetch_open_copy(_copy("cc-by"), client=client, cache=None)
    assert got is not None
    payload, content_type = got
    text, tables = read_payload(payload, content_type)
    assert len(tables) == 1
    assert tables[0]["header"] == ["Repigmentation", "Group 1 (n = 30)", "Group 2 (n = 30)"]
    assert tables[0]["rows"][0] == ["Excellent", "23 (76.7%)", "22 (73.3%)"]
    assert "Group 1 (n = 30)" in text


def test_a_pdf_is_recognised_by_its_bytes_not_its_url() -> None:
    """Two of the six papers that answered serve a PDF from a URL ending /download.

    The NIHR's HI-Light report is one: 9.7 MB of PDF from a path with no
    extension, declared as text/html. Trusting the declaration would have run
    the report through an HTML parser and found nothing.
    """
    # The very same markup, told apart only by what it starts with.
    _, as_html = read_payload(HTML_TABLE, "text/html")
    _, as_pdf = read_payload(b"%PDF-1.4\n" + HTML_TABLE, "text/html")
    assert len(as_html) == 1, "a page of markup should give up its table"
    assert as_pdf == [], "bytes that begin %PDF- must not be parsed as markup"


def test_no_contact_address_means_the_source_is_simply_off() -> None:
    """Unpaywall requires an address on every call; without one we do not ask."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"is_oa": True})

    with _client(handler) as client:
        assert find_open_copy("10.1/x", client=client, email="") is None
    assert calls == []


def test_a_closed_paper_yields_no_copy() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"is_oa": False, "best_oa_location": None})

    with _client(handler) as client:
        assert find_open_copy("10.1/x", client=client, email="a@b.c") is None


def test_the_licence_travels_with_the_copy() -> None:
    """What we may do with a document has to survive alongside it."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "is_oa": True,
                "best_oa_location": {
                    "license": "cc-by",
                    "host_type": "publisher",
                    "version": "publishedVersion",
                    "url": "https://example.org/a",
                    "url_for_pdf": "https://example.org/a.pdf",
                },
            },
        )

    with _client(handler) as client:
        copy = find_open_copy("10.1/x", client=client, email="a@b.c")
    assert copy is not None
    assert (copy.licence, copy.host_type) == ("cc-by", "publisher")
    assert copy.may_fetch and copy.best_url == "https://example.org/a"


def test_an_html_page_with_no_table_reads_as_no_tables() -> None:
    assert tables_from_html(b"<html><body><p>No numbers here.</p></body></html>") == []


LANDING_PAGE = b"""<html><body>
<table><tr><td>Titre:</td><td>Time-kinetic study of repigmentation in vitiligo</td></tr>
       <tr><td>Auteur:</td><td>Lubaki, L.J.; Ghanem, G.E.</td></tr></table>
<table><tr><td>Export bibliographie</td></tr>
       <tr><td>Format de fichier :</td><td>PDF RTF bibtex CSV RIS</td></tr></table>
</body></html>"""


def test_a_repository_landing_page_is_not_mistaken_for_an_article() -> None:
    """A page lays out its furniture in tables too.

    The repository copy of PMID 19547993 answered with thirteen tables -- a
    title block, a pitch for the repository, an export-format menu -- and not
    one number among them. A check that asked only whether any table existed
    accepted it and stored 5,241 characters of French navigation as the
    paper's full text.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=LANDING_PAGE, headers={"content-type": "text/html"})

    with _client(handler) as client:
        assert read_open_copy(_copy("cc-by"), client=client, cache=None) is None


def test_the_article_behind_such_a_page_is_still_accepted() -> None:
    """The filter must not reject a real table for being short."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=HTML_TABLE, headers={"content-type": "text/html"})

    with _client(handler) as client:
        got = read_open_copy(_copy("cc-by"), client=client, cache=None)
    assert got is not None
    text, tables = got
    assert len(tables) == 1 and "23 (76.7%)" in text


@pytest.mark.parametrize(
    ("rows", "header", "expected"),
    [
        ([["Age"], ["<= 20", "5", "16.7%"], ["21-30", "9", "30.0%"]], ["Patients- 30"], True),
        ([["Titre:", "A study of vitiligo"], ["Auteur:", "Someone"]], [], False),
        ([["Export"], ["Format:", "PDF RTF bibtex"]], [], False),
        ([["a", "1"]], [], False),
    ],
)
def test_a_table_counts_as_data_when_it_has_numbers_in_rows(
    rows: list[list[str]], header: list[str], expected: bool
) -> None:
    table = {"label": "", "caption": "", "header": header, "rows": rows}
    assert has_data(table) is expected  # type: ignore[arg-type]
