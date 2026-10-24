"""Tests for the GEO supplementary-file cache. No network: listings are fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from vitiligo.sources.geo_files import (
    CachedFile,
    RemoteFile,
    cache_summary,
    download,
    fetch_series,
    is_cached,
    list_files,
    listed_size_to_bytes,
    load_manifest,
    parse_listing,
    save_manifest,
    series_suppl_url,
    sha256_of,
)

# Apache's listing, as NCBI serves it.
LISTING = """<html><head><title>Index of /geo/series/GSE203nnn/GSE203262/suppl</title></head>
<body><h1>Index of /geo/series/GSE203nnn/GSE203262/suppl</h1><pre>
<a href="?C=N;O=D">Name</a> <a href="?C=M;O=A">Last modified</a> <a href="?C=S;O=A">Size</a>
<hr><a href="/geo/series/GSE203nnn/GSE203262/">Parent Directory</a>                       -
<a href="GSE203262_PtA_processed.tar.gz">GSE203262_PtA_processed.tar.gz</a>   2022-05-18 10:06  9.0M
<a href="GSE203262_PtD_processed.tar.gz">GSE203262_PtD_processed.tar.gz</a>   2022-05-18 10:07   40M
<a href="GSE203262_notes.txt">GSE203262_notes.txt</a>                             2022-05-18 10:07  812
<hr></pre>
<a href="https://www.hhs.gov/vulnerability-disclosure-policy/index.html">HHS Vulnerability Disclosure</a>
</body></html>"""


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_series_url_is_built_from_the_accession() -> None:
    assert series_suppl_url("GSE203262").endswith("/GSE203nnn/GSE203262/suppl/")
    assert series_suppl_url("GSE1").endswith("/GSEnnn/GSE1/suppl/")


@pytest.mark.parametrize("bad", ["GSM6165458", "203262", "GSE12a", ""])
def test_series_url_rejects_anything_that_is_not_a_series(bad: str) -> None:
    with pytest.raises(ValueError, match="not a GEO series accession"):
        series_suppl_url(bad)


@pytest.mark.parametrize(
    ("listed", "expected"),
    [("9.0M", 9_000_000), ("40M", 40_000_000), ("3.1G", 3_100_000_000), ("812", 812)],
)
def test_listed_sizes_become_bytes(listed: str, expected: int) -> None:
    assert listed_size_to_bytes(listed) == expected


def test_parse_listing_finds_the_files_and_skips_the_furniture() -> None:
    """Parent Directory, sort links and the HHS footer are not data files."""
    files = parse_listing("GSE203262", LISTING)
    assert [f.name for f in files] == [
        "GSE203262_PtA_processed.tar.gz",
        "GSE203262_PtD_processed.tar.gz",
        "GSE203262_notes.txt",
    ]
    assert files[1].listed_bytes == 40_000_000
    assert files[0].url.endswith("/GSE203262/suppl/GSE203262_PtA_processed.tar.gz")


def test_list_files_returns_nothing_when_a_series_has_no_supplementary_directory() -> None:
    """Some series keep their data on the individual samples; that is not an error."""
    client = _client(lambda request: httpx.Response(404, text="Object not found!"))
    assert list_files("GSE169238", client) == []


def test_list_files_raises_on_a_server_error() -> None:
    client = _client(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(httpx.HTTPStatusError):
        list_files("GSE203262", client)


def _remote(name: str = "counts.tsv") -> RemoteFile:
    return RemoteFile(
        accession="GSE311770",
        name=name,
        url=f"https://ftp.ncbi.nlm.nih.gov/geo/series/GSE311nnn/GSE311770/suppl/{name}",
        listed_bytes=11,
    )


def test_download_writes_the_file_and_records_its_hash(tmp_path: Path) -> None:
    client = _client(lambda request: httpx.Response(200, content=b"gene\tcount"))
    cached = download(_remote(), tmp_path, client)
    path = tmp_path / "GSE311770" / "counts.tsv"
    assert path.read_bytes() == b"gene\tcount"
    assert cached.sha256 == sha256_of(path)
    assert cached.bytes == 10
    assert cached.url.endswith("counts.tsv")


def test_download_leaves_no_partial_file_behind(tmp_path: Path) -> None:
    client = _client(lambda request: httpx.Response(200, content=b"x" * 100))
    download(_remote(), tmp_path, client)
    assert list((tmp_path / "GSE311770").glob("*.part")) == []


def test_a_failed_download_does_not_create_the_target(tmp_path: Path) -> None:
    """A truncated file that looks complete would poison every later analysis."""
    client = _client(lambda request: httpx.Response(503, text="unavailable"))
    with pytest.raises(httpx.HTTPStatusError):
        download(_remote(), tmp_path, client)
    assert not (tmp_path / "GSE311770" / "counts.tsv").exists()


def test_manifest_round_trips(tmp_path: Path) -> None:
    entry = CachedFile(
        accession="GSE311770",
        name="counts.tsv",
        url="https://example.invalid/counts.tsv",
        bytes=10,
        sha256="abc",
        retrieved_at="2026-10-23T00:00:00+00:00",
    )
    save_manifest({"GSE311770/counts.tsv": entry}, tmp_path)
    assert load_manifest(tmp_path) == {"GSE311770/counts.tsv": entry}


def test_manifest_is_readable_json_with_provenance(tmp_path: Path) -> None:
    save_manifest(
        {
            "GSE1/a": CachedFile("GSE1", "a", "u", 1, "h", "2026-10-23T00:00:00+00:00"),
        },
        tmp_path,
    )
    raw = json.loads((tmp_path / "manifest.json").read_text())
    assert raw["description"] and raw["updated_at"]
    assert raw["files"][0]["sha256"] == "h"


def test_missing_manifest_is_empty_not_an_error(tmp_path: Path) -> None:
    assert load_manifest(tmp_path) == {}


def test_is_cached_needs_both_the_manifest_entry_and_the_file(tmp_path: Path) -> None:
    remote = _remote()
    entry = CachedFile("GSE311770", "counts.tsv", remote.url, 10, "h", "2026-10-23T00:00:00+00:00")
    manifest = {"GSE311770/counts.tsv": entry}
    assert not is_cached(remote, tmp_path, manifest)  # recorded but not on disk

    path = tmp_path / "GSE311770" / "counts.tsv"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"gene\tcount")
    assert is_cached(remote, tmp_path, manifest)

    path.write_bytes(b"truncated")  # size no longer matches what was recorded
    assert not is_cached(remote, tmp_path, manifest)


def test_fetch_downloads_once_then_reports_the_file_as_cached(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if str(request.url).endswith("/suppl/"):
            return httpx.Response(200, text=LISTING)
        return httpx.Response(200, content=b"data")

    with _client(handler) as client:
        first = list(fetch_series(["GSE203262"], tmp_path, client=client))
        downloads = len([c for c in calls if not c.endswith("/suppl/")])
        second = list(fetch_series(["GSE203262"], tmp_path, client=client))

    assert [note for _r, _c, note in first] == ["downloaded"] * 3
    assert downloads == 3
    assert [note for _r, _c, note in second] == ["cached"] * 3
    assert len([c for c in calls if not c.endswith("/suppl/")]) == 3  # nothing re-fetched


def test_fetch_can_skip_files_over_a_size_limit(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/suppl/"):
            return httpx.Response(200, text=LISTING)
        return httpx.Response(200, content=b"data")

    with _client(handler) as client:
        results = list(fetch_series(["GSE203262"], tmp_path, client=client, max_bytes=10_000_000))
    notes = {r.name: note for r, _c, note in results}
    assert notes["GSE203262_PtA_processed.tar.gz"] == "downloaded"  # 9 MB
    assert notes["GSE203262_PtD_processed.tar.gz"].startswith("skipped")  # 40 MB


def test_fetch_survives_a_series_whose_listing_fails(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "GSE999999" in str(request.url):
            raise httpx.ConnectError("no route")
        if str(request.url).endswith("/suppl/"):
            return httpx.Response(200, text=LISTING)
        return httpx.Response(200, content=b"data")

    with _client(handler) as client:
        results = list(fetch_series(["GSE999999", "GSE203262"], tmp_path, client=client))
    assert [note for _r, _c, note in results] == ["downloaded"] * 3


def test_fetch_records_a_download_failure_without_stopping(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/suppl/"):
            return httpx.Response(200, text=LISTING)
        if "PtA" in str(request.url):
            return httpx.Response(500, text="boom")
        return httpx.Response(200, content=b"data")

    with _client(handler) as client:
        results = list(fetch_series(["GSE203262"], tmp_path, client=client))
    notes = [note for _r, _c, note in results]
    assert notes[0].startswith("failed")
    assert notes[1:] == ["downloaded", "downloaded"]


def test_cache_summary_counts_what_is_recorded(tmp_path: Path) -> None:
    save_manifest(
        {
            "GSE1/a": CachedFile("GSE1", "a", "u", 1_000_000, "h", "2026-10-23T00:00:00+00:00"),
            "GSE1/b": CachedFile("GSE1", "b", "u", 2_000_000, "h", "2026-10-23T00:00:00+00:00"),
            "GSE2/c": CachedFile("GSE2", "c", "u", 3_000_000, "h", "2026-10-23T00:00:00+00:00"),
        },
        tmp_path,
    )
    summary = cache_summary(tmp_path)
    assert (summary["series"], summary["files"], summary["bytes"]) == (2, 3, 6_000_000)
    assert summary["by_series"]["GSE1"]["files"] == 2
