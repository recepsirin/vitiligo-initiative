"""Tests for keeping the bytes a source returned."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from vitiligo.sources.raw_cache import (
    cache_summary,
    load_manifest,
    load_payload,
    payload_path,
    safe_name,
    save_payload,
)


def test_a_payload_is_written_and_recorded(tmp_path: Path) -> None:
    saved = save_payload("gwas_catalog", "release.zip", b"bytes", url="https://x/y", cache=tmp_path)
    assert (tmp_path / "gwas_catalog" / "release.zip").read_bytes() == b"bytes"
    assert saved.sha256 == hashlib.sha256(b"bytes").hexdigest()
    assert saved.bytes == 5
    assert saved.url == "https://x/y"
    assert load_manifest(tmp_path)[saved.key] == saved


def test_a_saved_payload_reads_back(tmp_path: Path) -> None:
    save_payload("nih_reporter", "projects.json", b'{"a": 1}', cache=tmp_path)
    assert load_payload("nih_reporter", "projects.json", cache=tmp_path) == b'{"a": 1}'


def test_a_missing_payload_is_none_not_an_error(tmp_path: Path) -> None:
    assert load_payload("nowhere", "nothing.bin", cache=tmp_path) is None


def test_a_payload_that_no_longer_matches_its_hash_is_refused(tmp_path: Path) -> None:
    """A corrupted cache must not silently feed an ingest."""
    save_payload("gwas_catalog", "release.zip", b"original", cache=tmp_path)
    (tmp_path / "gwas_catalog" / "release.zip").write_bytes(b"tampered")
    assert load_payload("gwas_catalog", "release.zip", cache=tmp_path) is None


def test_saving_again_replaces_the_payload_and_its_record(tmp_path: Path) -> None:
    save_payload("s", "p.bin", b"old", cache=tmp_path)
    saved = save_payload("s", "p.bin", b"new bytes", cache=tmp_path)
    assert load_payload("s", "p.bin", cache=tmp_path) == b"new bytes"
    manifest = load_manifest(tmp_path)
    assert len(manifest) == 1
    assert manifest[saved.key].bytes == 9


def test_a_name_cannot_escape_the_cache_directory(tmp_path: Path) -> None:
    saved = save_payload("src", "../../etc/passwd", b"x", cache=tmp_path)
    written = payload_path("src", "../../etc/passwd", tmp_path)
    assert tmp_path in written.parents
    assert ".." not in saved.name


def test_safe_name_keeps_something_usable() -> None:
    assert safe_name("vitiligo-projects.json") == "vitiligo-projects.json"
    assert safe_name("///") == "payload"
    assert "/" not in safe_name("a/b/c")


def test_no_partial_file_is_left_behind(tmp_path: Path) -> None:
    save_payload("s", "p.bin", b"data", cache=tmp_path)
    assert list(tmp_path.rglob("*.part")) == []


def test_the_manifest_is_readable_json_with_provenance(tmp_path: Path) -> None:
    save_payload("s", "p.bin", b"data", url="https://example.invalid/p.bin", cache=tmp_path)
    raw = json.loads((tmp_path / "manifest.json").read_text())
    assert raw["description"] and raw["updated_at"]
    assert raw["payloads"][0]["url"] == "https://example.invalid/p.bin"


def test_summary_counts_by_source(tmp_path: Path) -> None:
    save_payload("a", "one.bin", b"x" * 10, cache=tmp_path)
    save_payload("a", "two.bin", b"x" * 20, cache=tmp_path)
    save_payload("b", "three.bin", b"x" * 30, cache=tmp_path)
    summary = cache_summary(tmp_path)
    assert (summary["sources"], summary["payloads"], summary["bytes"]) == (2, 3, 60)
    assert summary["by_source"]["a"] == {"payloads": 2, "bytes": 30}  # type: ignore[index]
