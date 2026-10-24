"""Keep the bytes a source actually returned, not only what we parsed out of them.

Ingestion turns a payload into rows and throws the payload away. That is fine
until one of three things happens, and all three have happened here:

- **the source goes down** (Europe PMC returned 503 for every query on
  2026-10-24, including ones that had worked an hour earlier);
- **the source changes shape** — the GWAS Catalog's REST API is retired, and
  release files are reissued without notice;
- **a number needs checking** against what was downloaded, months later.

So each raw payload is written to ``data/raw/<source>/`` and recorded in a
manifest with its URL, size, SHA-256 and retrieval time — the same discipline
as the GEO file cache and the sealed forecasts. A re-run can then work from
the saved copy, and a disputed row can be traced to the bytes it came from.

The cache is local only: ``data/`` is not committed, and these payloads are
redistributable only under each source's own terms.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RAW_CACHE = Path("data/raw")
MANIFEST_NAME = "manifest.json"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class RawPayload:
    """One saved payload, and where it came from."""

    source: str
    name: str
    url: str | None
    bytes: int
    sha256: str
    retrieved_at: str

    @property
    def key(self) -> str:
        return f"{self.source}/{self.name}"

    @property
    def megabytes(self) -> float:
        return self.bytes / 1e6


def safe_name(name: str) -> str:
    """A file name that cannot escape the cache directory."""
    cleaned = _SAFE_NAME.sub("-", name).strip("-.")
    return cleaned or "payload"


def payload_path(source: str, name: str, cache: Path = DEFAULT_RAW_CACHE) -> Path:
    return cache / safe_name(source) / safe_name(name)


def manifest_path(cache: Path = DEFAULT_RAW_CACHE) -> Path:
    return cache / MANIFEST_NAME


def load_manifest(cache: Path = DEFAULT_RAW_CACHE) -> dict[str, RawPayload]:
    path = manifest_path(cache)
    if not path.is_file():
        return {}
    names = set(RawPayload.__dataclass_fields__)
    out: dict[str, RawPayload] = {}
    for record in json.loads(path.read_text()).get("payloads", []):
        payload = RawPayload(**{k: v for k, v in record.items() if k in names})
        out[payload.key] = payload
    return out


def save_manifest(payloads: dict[str, RawPayload], cache: Path = DEFAULT_RAW_CACHE) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    path = manifest_path(cache)
    path.write_text(
        json.dumps(
            {
                "description": (
                    "Raw payloads as sources returned them, kept so an ingest can be "
                    "reproduced or re-run offline."
                ),
                "updated_at": datetime.now(UTC).isoformat(),
                "payloads": [
                    asdict(p) for p in sorted(payloads.values(), key=lambda p: (p.source, p.name))
                ],
            },
            indent=2,
        )
        + "\n"
    )
    return path


def save_payload(
    source: str,
    name: str,
    data: bytes,
    *,
    url: str | None = None,
    cache: Path = DEFAULT_RAW_CACHE,
) -> RawPayload:
    """Write a payload to the cache and record what it was."""
    target = payload_path(source, name, cache)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    partial.write_bytes(data)
    partial.replace(target)

    payload = RawPayload(
        source=source,
        name=safe_name(name),
        url=url,
        bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        retrieved_at=datetime.now(UTC).isoformat(),
    )
    manifest = load_manifest(cache)
    manifest[payload.key] = payload
    save_manifest(manifest, cache)
    logger.info("Cached %s (%.1f MB) from %s", payload.key, payload.megabytes, url or "memory")
    return payload


def load_payload(source: str, name: str, cache: Path = DEFAULT_RAW_CACHE) -> bytes | None:
    """The saved bytes, if they are present and still match what was recorded."""
    path = payload_path(source, name, cache)
    if not path.is_file():
        return None
    data = path.read_bytes()
    known = load_manifest(cache).get(f"{source}/{safe_name(name)}")
    if known is not None and hashlib.sha256(data).hexdigest() != known.sha256:
        logger.warning("Cached %s/%s does not match its recorded hash; ignoring it", source, name)
        return None
    return data


def cache_summary(cache: Path = DEFAULT_RAW_CACHE) -> dict[str, object]:
    """What is held locally, by source."""
    manifest = load_manifest(cache)
    by_source: dict[str, dict[str, object]] = {}
    for payload in manifest.values():
        entry = by_source.setdefault(payload.source, {"payloads": 0, "bytes": 0})
        entry["payloads"] = int(entry["payloads"]) + 1  # type: ignore[call-overload]
        entry["bytes"] = int(entry["bytes"]) + payload.bytes  # type: ignore[call-overload]
    return {
        "sources": len(by_source),
        "payloads": len(manifest),
        "bytes": sum(p.bytes for p in manifest.values()),
        "by_source": dict(sorted(by_source.items())),
    }
