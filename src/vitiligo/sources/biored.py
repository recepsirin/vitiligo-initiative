"""BioRED: NCBI's gold standard for the relations PubTator reads.

600 PubMed abstracts in which annotators marked every gene, disease, chemical
and variant, normalised each, and recorded every relation between them in the
eight types PubTator's own relation model produces -- 4,178 relations in the
400 training abstracts, 1,162 in the 100 for development and 1,163 in the 100
held out for test. A model of ours is trained against it and judged on the
test split, which nothing else touches. A United States Government work, in
the public domain.

The documents are read into the same structures as a PubTator export, with
BioRED's entity type names translated to PubTator's, so one model reads both.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx

from vitiligo.logging import get_logger
from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Mention, Passage, Relation
from vitiligo.sources.raw_cache import DEFAULT_RAW_CACHE, load_payload, save_payload

logger = get_logger(__name__)

URL = "https://ftp.ncbi.nlm.nih.gov/pub/lu/BioRED/BIORED.zip"
SOURCE = "biored"
SPLITS = ("Train", "Dev", "Test")

_TYPES = {
    "GeneOrGeneProduct": "Gene",
    "DiseaseOrPhenotypicFeature": "Disease",
    "ChemicalEntity": "Chemical",
    "SequenceVariant": "Variant",
    "OrganismTaxon": "Species",
    "CellLine": "CellLine",
}


def _archive(cache: Path) -> bytes:
    cached = load_payload(SOURCE, "BIORED.zip", cache)
    if cached is not None:
        return cached
    logger.info("Downloading %s", URL)
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        response = client.get(URL)
        response.raise_for_status()
    save_payload(SOURCE, "BIORED.zip", response.content, url=URL, cache=cache)
    return response.content


def load_split(split: str, *, cache: Path = DEFAULT_RAW_CACHE) -> list[AnnotatedDocument]:
    """One of Train, Dev or Test, as annotated documents."""
    with zipfile.ZipFile(io.BytesIO(_archive(cache))) as archive:
        data = json.loads(archive.read(f"BioRED/{split}.BioC.JSON"))
    return [_document(doc) for doc in data["documents"]]


def _document(doc: dict[str, Any]) -> AnnotatedDocument:
    passages: list[Passage] = []
    mentions: list[Mention] = []
    kinds: dict[str, str] = {}
    for index, passage in enumerate(doc["passages"]):
        section = "title" if index == 0 else "abstract"
        start = int(passage.get("offset") or 0)
        passages.append(Passage(section, start, str(passage.get("text") or "")))
        for annotation in passage.get("annotations") or []:
            infons = annotation.get("infons") or {}
            identifier = str(infons.get("identifier") or "")
            kind = _TYPES.get(str(infons.get("type")), str(infons.get("type")))
            # An unnormalised mention names no concept.
            if not identifier or identifier == "-":
                continue
            # A mention may name several concepts at once ("3172,3651,6927");
            # a relation always names one, so each is known by itself too.
            for one in identifier.split(","):
                kinds.setdefault(one, kind)
            location = (annotation.get("locations") or [{}])[0]
            text = str(annotation.get("text") or "")
            mentions.append(
                Mention(
                    concept=Concept(type=kind, identifier=identifier, name=text),
                    text=text,
                    passage=section,
                    offset=int(location.get("offset") or 0),
                )
            )
    relations = [
        Relation(
            type=str(infons["type"]),
            score=1.0,
            first=Concept(kinds[infons["entity1"]], infons["entity1"], infons["entity1"]),
            second=Concept(kinds[infons["entity2"]], infons["entity2"], infons["entity2"]),
        )
        for infons in (r["infons"] for r in doc.get("relations") or [])
    ]
    return AnnotatedDocument(
        pmid=str(doc["id"]),
        pmcid=None,
        mentions=tuple(mentions),
        relations=tuple(relations),
        passages=tuple(passages),
    )
