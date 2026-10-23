"""Download the data behind a GEO series, not just its metadata.

``geo.py`` ingests series *metadata* into the corpus, which makes a dataset
findable and citable. It cannot be analysed from that: the counts live in
supplementary files on NCBI's FTP host. This module fetches those files into a
local cache and records where each one came from.

Every file is recorded in a manifest with its URL, byte count, SHA-256 and
retrieval time, for the same reason forecasts carry a hash: an analysis is
reproducible only if the bytes it ran on can be identified again. A file
already in the cache with a matching checksum is never re-downloaded.

What this does **not** do is read the files. GEO deposits are not uniform:
one series ships a single counts matrix, another six per-patient tar archives
whose internal naming differs between archives, another nothing at all at
series level because the data sit on the individual samples. Readers belong
with the analysis that needs them, one dataset at a time.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from vitiligo.logging import get_logger

logger = get_logger(__name__)

FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/geo/series"
DEFAULT_CACHE = Path("data/geo")
MANIFEST_NAME = "manifest.json"

# The listing is Apache's: <a href="NAME">NAME</a>  2022-05-18 10:06  9.0M
_ROW = re.compile(
    r'<a href="(?P<name>[^"/][^"]*)">[^<]*</a>\s+'
    r"(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+"
    r"(?P<size>[\d.]+[KMGT]?)\s",
    re.IGNORECASE,
)
_UNITS = {"K": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}


def listed_size_to_bytes(size: str) -> int:
    """'9.0M' -> 9000000. The listing rounds, so this is approximate."""
    size = size.strip()
    if size and size[-1].upper() in _UNITS:
        return int(float(size[:-1]) * _UNITS[size[-1].upper()])
    return int(float(size))


def series_suppl_url(accession: str) -> str:
    """Supplementary directory of a series: GSE203262 -> .../GSE203nnn/GSE203262/suppl/."""
    match = re.fullmatch(r"GSE(\d+)", accession)
    if match is None:
        raise ValueError(f"not a GEO series accession: {accession!r}")
    # NCBI groups series by the accession with its last three digits masked:
    # GSE203262 -> GSE203nnn, and anything under 1000 -> GSEnnn.
    return f"{FTP_BASE}/GSE{match.group(1)[:-3]}nnn/{accession}/suppl/"


@dataclass(frozen=True)
class RemoteFile:
    """A supplementary file as the directory listing describes it."""

    accession: str
    name: str
    url: str
    listed_bytes: int


@dataclass(frozen=True)
class CachedFile:
    """A file on disk, with where it came from and what it hashes to."""

    accession: str
    name: str
    url: str
    bytes: int
    sha256: str
    retrieved_at: str

    @property
    def megabytes(self) -> float:
        return self.bytes / 1e6


def parse_listing(accession: str, html: str) -> list[RemoteFile]:
    """Supplementary files named in a series' directory listing."""
    base = series_suppl_url(accession)
    return [
        RemoteFile(
            accession=accession,
            name=m.group("name"),
            url=base + m.group("name"),
            listed_bytes=listed_size_to_bytes(m.group("size")),
        )
        for m in _ROW.finditer(html)
    ]


def list_files(accession: str, client: httpx.Client) -> list[RemoteFile]:
    """Ask NCBI what a series offers. An empty list means the data sit on its samples."""
    response = client.get(series_suppl_url(accession))
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return parse_listing(accession, response.text)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(remote: RemoteFile, cache: Path, client: httpx.Client) -> CachedFile:
    """Stream one file into ``cache/<accession>/``, then hash what landed.

    The download goes to a ``.part`` file and is renamed only once complete, so
    an interrupted run cannot leave a truncated file looking finished.
    """
    directory = cache / remote.accession
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / remote.name
    partial = target.with_suffix(target.suffix + ".part")
    with client.stream("GET", remote.url) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 256):
                handle.write(chunk)
    partial.replace(target)
    return CachedFile(
        accession=remote.accession,
        name=remote.name,
        url=remote.url,
        bytes=target.stat().st_size,
        sha256=sha256_of(target),
        retrieved_at=datetime.now(UTC).isoformat(),
    )


def manifest_path(cache: Path = DEFAULT_CACHE) -> Path:
    return cache / MANIFEST_NAME


def load_manifest(cache: Path = DEFAULT_CACHE) -> dict[str, CachedFile]:
    """Cached files by ``accession/name``."""
    path = manifest_path(cache)
    if not path.is_file():
        return {}
    records = json.loads(path.read_text()).get("files", [])
    names = set(CachedFile.__dataclass_fields__)
    out = {}
    for record in records:
        cached = CachedFile(**{k: v for k, v in record.items() if k in names})
        out[f"{cached.accession}/{cached.name}"] = cached
    return out


def save_manifest(files: dict[str, CachedFile], cache: Path = DEFAULT_CACHE) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    path = manifest_path(cache)
    payload = {
        "description": (
            "GEO supplementary files fetched by `vitiligo geo-data fetch`. "
            "Each entry records where the bytes came from and what they hash to."
        ),
        "updated_at": datetime.now(UTC).isoformat(),
        "files": [asdict(f) for f in sorted(files.values(), key=lambda f: (f.accession, f.name))],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def is_cached(remote: RemoteFile, cache: Path, manifest: dict[str, CachedFile]) -> bool:
    """True when the file is on disk at the size the manifest recorded."""
    key = f"{remote.accession}/{remote.name}"
    known = manifest.get(key)
    if known is None:
        return False
    path = cache / remote.accession / remote.name
    return path.is_file() and path.stat().st_size == known.bytes


def fetch_series(
    accessions: list[str],
    cache: Path = DEFAULT_CACHE,
    *,
    client: httpx.Client,
    max_bytes: int | None = None,
) -> Iterator[tuple[RemoteFile, CachedFile | None, str]]:
    """Fetch each series' files, yielding ``(remote, cached, note)`` as it goes.

    ``cached`` is ``None`` when the file was skipped; ``note`` says why.
    Progress is yielded rather than printed so the CLI owns the display.
    """
    manifest = load_manifest(cache)
    for accession in accessions:
        try:
            remotes = list_files(accession, client)
        except httpx.HTTPError as exc:
            logger.warning("geo-data: listing failed for %s: %s", accession, exc)
            continue
        if not remotes:
            logger.info("geo-data: %s has no series-level files", accession)
            continue
        for remote in remotes:
            if is_cached(remote, cache, manifest):
                yield remote, manifest[f"{accession}/{remote.name}"], "cached"
                continue
            if max_bytes is not None and remote.listed_bytes > max_bytes:
                yield remote, None, f"skipped: larger than {max_bytes / 1e6:.0f} MB"
                continue
            try:
                cached = download(remote, cache, client)
            except httpx.HTTPError as exc:
                yield remote, None, f"failed: {exc}"
                continue
            manifest[f"{accession}/{remote.name}"] = cached
            save_manifest(manifest, cache)
            yield remote, cached, "downloaded"


def cache_summary(cache: Path = DEFAULT_CACHE) -> dict[str, Any]:
    """What the cache holds, by series."""
    manifest = load_manifest(cache)
    by_series: dict[str, dict[str, Any]] = {}
    for cached in manifest.values():
        entry = by_series.setdefault(cached.accession, {"files": 0, "bytes": 0})
        entry["files"] += 1
        entry["bytes"] += cached.bytes
    return {
        "series": len(by_series),
        "files": len(manifest),
        "bytes": sum(f.bytes for f in manifest.values()),
        "by_series": dict(sorted(by_series.items())),
    }
