"""MeSH: what NLM says a concept is called, and whether it is a drug.

PubTator names every chemical and disease it finds by a MeSH identifier, and
two of its mistakes can only be told from its correct calls by asking MeSH:

- **A normalisation the text does not support.** "Cancer" normalised to
  *Neoplasms* is right, and "hair loss" to *Alopecia*; "depigmentation
  disorder" normalised to *Congenital, Hereditary, and Neonatal Diseases and
  Abnormalities* is wrong, and so is "dermatological disorders" to
  *Acrocephalosyndactylia*. No word is shared in any of the four. What
  separates them is that MeSH lists "Cancer" and "Hair Loss" among those
  descriptors' own entry terms, and lists neither wrong one.
- **A molecule that is not a drug.** PubTator stores every chemical that is
  lower in a disease as negatively correlated with it, and displays that as
  "treat" -- so melanin "treats" vitiligo and malondialdehyde "causes" it.
  MeSH records a pharmacological action for tacrolimus and none for melanin.

Only those three things are kept from each record: the name, the entry terms
and the pharmacological actions. Both files are cached under ``data/raw/mesh``
the first time and read from there afterwards.
"""

from __future__ import annotations

import gzip
import io
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from lxml import etree

from vitiligo.logging import get_logger
from vitiligo.sources.raw_cache import DEFAULT_RAW_CACHE, load_payload, save_payload

logger = get_logger(__name__)

BASE_URL = "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh"
SOURCE = "mesh"
YEAR = 2026


@dataclass(frozen=True)
class MeshRecord:
    ui: str  # D016559, or a supplementary C540383
    name: str
    terms: frozenset[str] = field(default_factory=frozenset)  # normalised, name included
    pharmacological_actions: tuple[str, ...] = ()


def normalise(text: str) -> str:
    """Lower case, punctuation to spaces, one space between words."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _download(name: str, cache: Path) -> bytes:
    cached = load_payload(SOURCE, name, cache)
    if cached is not None:
        return cached
    url = f"{BASE_URL}/{name}"
    logger.info("Downloading %s", url)
    # The server labels the file ``Content-Encoding: x-gzip``, so a plain read
    # would be decompressed on arrival and cached as 1.1 GB of XML. The bytes
    # are read as sent instead: the 64 MB gzip file the name says.
    with (
        httpx.Client(timeout=600.0, follow_redirects=True) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        data = b"".join(response.iter_raw())
    # NLM answers a missing file with a 16 KB HTML error page and status 200.
    if not data.startswith(b"\x1f\x8b"):
        raise ValueError(f"{url} did not return a gzip file; the file has moved")
    save_payload(SOURCE, name, data, url=url, cache=cache)
    return data


def _records(data: bytes, tag: str, ui_tag: str, name_tag: str) -> Iterator[MeshRecord]:
    stream = gzip.GzipFile(fileobj=io.BytesIO(data))
    for _, element in etree.iterparse(stream, events=("end",), tag=tag):
        ui = element.findtext(ui_tag) or ""
        name = element.findtext(f"{name_tag}/String") or ""
        terms = {normalise(t.text) for t in element.iterfind(".//Term/String") if t.text}
        terms.add(normalise(name))
        actions = tuple(
            a.text
            for a in element.iterfind(
                "PharmacologicalActionList/PharmacologicalAction/DescriptorReferredTo"
                "/DescriptorName/String"
            )
            if a.text
        )
        yield MeshRecord(
            ui=ui,
            name=name,
            terms=frozenset(t for t in terms if t),
            pharmacological_actions=actions,
        )
        element.clear()
        parent = element.getparent()
        while parent is not None and element.getprevious() is not None:
            del parent[0]


def load_index(
    wanted: Iterable[str] | None = None, *, cache: Path = DEFAULT_RAW_CACHE
) -> dict[str, MeshRecord]:
    """MeSH descriptors and supplementary concepts by identifier.

    ``wanted`` limits the 330,000 supplementary records to the ones asked
    about; descriptors are few enough to keep in full.
    """
    keep = {w.removeprefix("MESH:") for w in wanted} if wanted is not None else None
    index: dict[str, MeshRecord] = {}
    desc = _download(f"desc{YEAR}.gz", cache)
    for record in _records(desc, "DescriptorRecord", "DescriptorUI", "DescriptorName"):
        index[record.ui] = record
    supp = _download(f"supp{YEAR}.gz", cache)
    for record in _records(
        supp, "SupplementalRecord", "SupplementalRecordUI", "SupplementalRecordName"
    ):
        if keep is None or record.ui in keep:
            index[record.ui] = record
    logger.info("MeSH index: %d records", len(index))
    return index
