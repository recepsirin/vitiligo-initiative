"""PubTator 3.0: what NCBI has already read out of PubMed.

PubTator annotates every PubMed abstract, and the open-access full text in PMC,
with normalised entities -- chemicals and diseases against MeSH, genes against
NCBI Gene -- and with typed relations between them. That is the extraction
this project would otherwise have to build, done once for all of PubMed and
refreshed weekly, by a group whose whole work it is.

Three things about the export shaped this module, each found by reading it
rather than its documentation:

- **A request takes at most 100 PMIDs.** 200 returns HTTP 400 and 1,000 a
  414, so the corpus is fetched in batches of 100 -- about two minutes for all
  of it.
- **Relations come from the abstract.** ``full=true`` adds the body's
  passages and their entity mentions, hundreds per paper, but no relations:
  one paper has a relation in its abstract-only export and none in its full
  one. Relations and full-text entities are therefore fetched separately.
- **The relation types are not the labels PubTator displays.** A drug that
  treats a disease is stored as ``Negative_Correlation`` -- it is displayed as
  "treat" -- and an adverse effect as ``Positive_Correlation``. The raw type
  is what is kept here; what it means is the graph loader's decision.

Every response is cached under ``data/raw/pubtator/`` before it is parsed, so
the mapping onto the graph can be revised and rerun without asking NCBI again.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from vitiligo.logging import get_logger
from vitiligo.sources.raw_cache import (
    DEFAULT_RAW_CACHE,
    load_manifest,
    load_payload,
    payload_path,
    save_payload,
)

logger = get_logger(__name__)

EXPORT_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"
SOURCE = "pubtator"
ABSTRACT_BATCH = 100
# A full-text export of a single paper runs to megabytes, so these go in
# smaller batches to keep a response well clear of the server's limits.
FULLTEXT_BATCH = 10
_NOT_HELD = b"Could not retrieve publications"
USER_AGENT = (
    "vitiligo-initiative/0.1 (non-profit vitiligo research; "
    "+https://github.com/recepsirin/vitiligo-initiative)"
)


@dataclass(frozen=True)
class Concept:
    """A normalised entity: what PubTator decided a mention refers to."""

    type: str  # Chemical, Disease, Gene, Species, Variant, CellLine
    identifier: str  # MESH:D014820, or an NCBI Gene id such as 3627
    name: str  # the preferred name: "Vitiligo", "CXCL10"
    # PubTator's key across species: mouse Nr3c1 (Gene 14815) and human NR3C1
    # (Gene 2908) are both @GENE_NR3C1.
    accession: str = ""


@dataclass(frozen=True)
class Mention:
    """One place in the text where a concept was found."""

    concept: Concept
    text: str  # as written: "depigmentation disorder", "HIF-1alpha"
    passage: str  # title, abstract, or a full-text section type
    offset: int
    # The words straight after it. "CO2" followed by "laser" is a laser, and
    # nothing else in the annotation says so.
    after: str = ""


@dataclass(frozen=True)
class Relation:
    """A typed relation between two concepts, asserted by one document."""

    type: str  # Association, Negative_Correlation, Positive_Correlation, ...
    score: float
    first: Concept
    second: Concept
    # Where in a full text it was read, and the words it was read from: PubTator's
    # abstract relations carry neither, a full-text model's carry both.
    section: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class Passage:
    """A stretch of the document as written: its title, abstract, or a paragraph."""

    section: str  # TITLE, ABSTRACT, INTRO, RESULTS, REF ... in a full text; title, abstract
    offset: int  # where it starts in the document, the frame every mention offset is in
    text: str


@dataclass(frozen=True)
class AnnotatedDocument:
    pmid: str
    pmcid: str | None
    mentions: tuple[Mention, ...]
    relations: tuple[Relation, ...]
    passages: tuple[Passage, ...] = ()
    target_type_pairs: frozenset[tuple[str, str]] | None = None


def _concept(infons: dict[str, object]) -> Concept | None:
    identifier = str(infons.get("identifier") or "").strip()
    kind = str(infons.get("type") or "").strip()
    # An unnormalised mention carries "-" or nothing; it names no concept.
    if not identifier or identifier == "-" or not kind:
        return None
    name = str(infons.get("name") or "").strip() or identifier
    accession = str(infons.get("accession") or "")
    return Concept(type=kind, identifier=identifier, name=name, accession=accession)


def parse_export(data: bytes) -> Iterator[AnnotatedDocument]:
    """Every document in one BioC JSON export."""
    for doc in json.loads(data).get("PubTator3", []):
        mentions: list[Mention] = []
        passages: list[Passage] = []
        for passage in doc.get("passages") or []:
            infons = passage.get("infons") or {}
            section = str(infons.get("type") or "")
            body = str(passage.get("text") or "")
            start = int(passage.get("offset") or 0)
            passages.append(Passage(str(infons.get("section_type") or section), start, body))
            for annotation in passage.get("annotations") or []:
                concept = _concept(annotation.get("infons") or {})
                if concept is None:
                    continue
                location = (annotation.get("locations") or [{}])[0]
                offset = int(location.get("offset") or 0)
                end = offset - start + int(location.get("length") or 0)
                mentions.append(
                    Mention(
                        concept=concept,
                        text=str(annotation.get("text") or ""),
                        passage=section,
                        offset=offset,
                        after=body[end : end + 24],
                    )
                )
        relations: list[Relation] = []
        for relation in doc.get("relations") or []:
            infons = relation.get("infons") or {}
            first = _concept(infons.get("role1") or {})
            second = _concept(infons.get("role2") or {})
            if first is None or second is None:
                continue
            relations.append(
                Relation(
                    type=str(infons.get("type") or ""),
                    score=float(infons.get("score") or 0.0),
                    first=first,
                    second=second,
                )
            )
        yield AnnotatedDocument(
            pmid=str(doc.get("pmid") or doc.get("id") or ""),
            pmcid=str(doc.get("pmcid")) if doc.get("pmcid") else None,
            mentions=tuple(mentions),
            relations=tuple(relations),
            passages=tuple(passages),
        )


class PubtatorClient:
    """Fetches PubTator exports and caches each response before parsing it."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        delay: float = 0.4,
        cache: Path = DEFAULT_RAW_CACHE,
    ) -> None:
        # NCBI asks for no more than three requests a second without a key.
        self._delay = delay
        self._cache = cache
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=300.0, follow_redirects=True
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PubtatorClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _export(self, pmids: list[str], *, full: bool) -> tuple[str, bytes]:
        params = {"pmids": ",".join(pmids)}
        if full:
            params["full"] = "true"
        response = self._client.get(EXPORT_URL, params=params)
        # A batch none of whose PMIDs PubTator holds is answered with HTTP 400
        # and this detail, not with an empty result. It is an answer, and it is
        # kept: without it the same 31 PMIDs were asked about on every run.
        if response.status_code == 400 and _NOT_HELD in response.content:
            return str(response.url), response.content
        response.raise_for_status()
        return str(response.url), response.content

    def harvest(self, pmids: Iterable[str], *, full: bool = False) -> Iterator[tuple[str, int]]:
        """Fetch and cache every PMID not already in the cache.

        Resumes rather than restarts: a PMID found in any cached batch of the
        same kind is skipped, so a run interrupted halfway, or a corpus that
        has grown since, fetches only what is missing. Yields each new
        batch's cache name and how many documents it held.
        """
        kind = "fulltext" if full else "abstracts"
        size = FULLTEXT_BATCH if full else ABSTRACT_BATCH
        held = set(cached_pmids(kind=kind, cache=self._cache))
        wanted = [p for p in dict.fromkeys(str(p) for p in pmids) if p and p not in held]
        logger.info("PubTator %s: %d held, %d to fetch", kind, len(held), len(wanted))
        sequence = len(_batch_names(kind, self._cache))
        for start in range(0, len(wanted), size):
            batch = wanted[start : start + size]
            url, data = self._export(batch, full=full)
            sequence += 1
            name = f"{kind}-{sequence:05d}.json"
            # The URL carries the PMIDs asked for, so a PMID PubTator does not
            # hold is recorded as asked about, and not asked about again.
            save_payload(SOURCE, name, data, url=url, cache=self._cache)
            yield name, len(json.loads(data).get("PubTator3", []))
            time.sleep(self._delay)


def _batch_names(kind: str, cache: Path) -> list[str]:
    prefix = f"{SOURCE}/{kind}-"
    return sorted(key.split("/", 1)[1] for key in load_manifest(cache) if key.startswith(prefix))


def cached_documents(
    *, kind: str = "abstracts", cache: Path = DEFAULT_RAW_CACHE
) -> Iterator[AnnotatedDocument]:
    """Every document in the cache, parsed from the bytes NCBI returned."""
    for name in _batch_names(kind, cache):
        data = load_payload(SOURCE, name, cache)
        if data is None:
            logger.warning("Skipping %s: missing or altered since it was cached", name)
            continue
        yield from parse_export(data)


def cached_pmids(*, kind: str = "abstracts", cache: Path = DEFAULT_RAW_CACHE) -> Iterator[str]:
    """Every PMID already asked about: the ones returned, and the ones requested.

    A PMID PubTator does not hold appears in no payload, only in the request
    that asked for it, so both are read.
    """
    manifest = load_manifest(cache)
    for name in _batch_names(kind, cache):
        requested = parse_qs(urlparse(manifest[f"{SOURCE}/{name}"].url or "").query)
        for joined in requested.get("pmids", []):
            yield from joined.split(",")
        path = payload_path(SOURCE, name, cache)
        if not path.is_file():
            continue
        for doc in json.loads(path.read_bytes()).get("PubTator3", []):
            yield str(doc.get("pmid") or doc.get("id") or "")
