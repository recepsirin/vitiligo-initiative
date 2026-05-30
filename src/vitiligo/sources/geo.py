"""NCBI GEO (Gene Expression Omnibus) metadata client.

We ingest **series-level metadata** (GSE accessions) from the GEO DataSets
(`db=gds`) index via E-utilities `esearch` + `esummary`. Full expression
matrices are out of scope for v1 — this module lands searchable dataset
records in the shared `documents` table for omics-aware retrieval.

API docs: https://www.ncbi.nlm.nih.gov/books/NBK25500/
GEO overview: https://www.ncbi.nlm.nih.gov/geo/
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from vitiligo.config import Settings, get_settings
from vitiligo.logging import get_logger
from vitiligo.storage.models import Document, SourceKind

logger = get_logger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

DEFAULT_VITILIGO_QUERY = '"vitiligo"[MeSH Terms] OR vitiligo[All Fields]'
DEFAULT_BATCH_SIZE = 100
ESUMMARY_BATCH_SIZE = 200


@dataclass(frozen=True)
class SearchHandle:
    total: int
    query: str


class GEOClient:
    """Thin client over NCBI E-utilities for GEO DataSets metadata."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        request_delay_s: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "User-Agent": f"{self.settings.ncbi_tool}/0.1 (+https://github.com/recepsirin/vitiligo-initiative)",
                "Accept": "application/json",
            },
        )
        if request_delay_s is None:
            request_delay_s = 0.12 if self.settings.ncbi_api_key else 0.35
        self._delay = request_delay_s
        self._last_request_ts = 0.0

    def __enter__(self) -> GEOClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _identity_params(self) -> dict[str, str]:
        params: dict[str, str] = {"tool": self.settings.ncbi_tool}
        if self.settings.ncbi_email:
            params["email"] = self.settings.ncbi_email
        if self.settings.ncbi_api_key:
            params["api_key"] = self.settings.ncbi_api_key
        return params

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = self._delay - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, json.JSONDecodeError)),
    )
    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        self._throttle()
        response = self._client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise json.JSONDecodeError("Expected JSON object", response.text, 0)
        return payload

    def search(self, query: str = DEFAULT_VITILIGO_QUERY) -> SearchHandle:
        params: dict[str, Any] = {
            "db": "gds",
            "term": query,
            "retmax": 0,
            "retmode": "json",
            **self._identity_params(),
        }
        logger.info("GEO esearch: %s", query)
        payload = self._get_json(ESEARCH_URL, params)
        result = payload.get("esearchresult") or {}
        total = int(result.get("count") or 0)
        logger.info("GEO esearch matched %d datasets", total)
        return SearchHandle(total=total, query=query)

    def list_uids(
        self,
        query: str = DEFAULT_VITILIGO_QUERY,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        limit: int | None = None,
    ) -> list[str]:
        """Return GEO DataSets UIDs for a query."""
        handle = self.search(query)
        if handle.total == 0:
            return []

        cap = min(handle.total, limit) if limit is not None else handle.total
        uids: list[str] = []
        retstart = 0
        while retstart < cap:
            retmax = min(batch_size, cap - retstart)
            params: dict[str, Any] = {
                "db": "gds",
                "term": query,
                "retstart": retstart,
                "retmax": retmax,
                "retmode": "json",
                **self._identity_params(),
            }
            payload = self._get_json(ESEARCH_URL, params)
            idlist = (payload.get("esearchresult") or {}).get("idlist") or []
            if not idlist:
                break
            uids.extend(str(uid) for uid in idlist)
            retstart += len(idlist)
        return uids[:cap]

    def fetch_summaries(self, uids: list[str]) -> list[Document]:
        if not uids:
            return []
        params: dict[str, Any] = {
            "db": "gds",
            "id": ",".join(uids),
            "retmode": "json",
            **self._identity_params(),
        }
        payload = self._get_json(ESUMMARY_URL, params)
        result = payload.get("result") or {}
        docs: list[Document] = []
        for uid in result.get("uids") or []:
            if uid == "uids":
                continue
            record = result.get(uid)
            if isinstance(record, dict):
                doc = parse_geo_summary(record)
                if doc is not None:
                    docs.append(doc)
        return docs

    def iter_documents(
        self,
        query: str = DEFAULT_VITILIGO_QUERY,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        limit: int | None = None,
    ) -> Iterator[Document]:
        uids = self.list_uids(query, batch_size=batch_size, limit=limit)
        for start in range(0, len(uids), ESUMMARY_BATCH_SIZE):
            chunk = uids[start : start + ESUMMARY_BATCH_SIZE]
            yield from self.fetch_summaries(chunk)


def parse_geo_summary(record: dict[str, Any]) -> Document | None:
    """Map a GEO DataSets esummary record to a Document."""
    accession = str(record.get("accession") or "").strip()
    uid = str(record.get("uid") or "").strip()
    source_id = accession or (f"GDS{uid}" if uid else "")
    if not source_id:
        return None

    title = str(record.get("title") or "").strip() or None
    summary = str(record.get("summary") or "").strip() or None
    taxon = str(record.get("taxon") or "").strip()
    entrytype = str(record.get("entrytype") or "GSE").strip()
    gdstype = str(record.get("gdstype") or "").strip()
    pdat = str(record.get("pdat") or "").strip()
    year = _parse_year(pdat)

    keywords: list[str] = []
    if taxon:
        keywords.append(taxon)
    if gdstype:
        keywords.append(gdstype)
    bioproject = str(record.get("bioproject") or "").strip()
    if bioproject:
        keywords.append(bioproject)

    n_samples = record.get("n_samples")
    pubtypes = [f"GEO {entrytype}"]
    if gdstype:
        pubtypes.append(gdstype)

    return Document(
        source=SourceKind.GEO,
        source_id=source_id,
        title=title,
        abstract=summary,
        journal="NCBI GEO",
        year=year,
        language="eng",
        keywords=keywords,
        publication_types=pubtypes,
        raw_metadata={
            **record,
            "geo_uid": uid,
            "sample_count": n_samples,
            "platform_id": record.get("gpl"),
            "ftp_link": record.get("ftplink"),
        },
    )


def _parse_year(pdat: str) -> int | None:
    if not pdat:
        return None
    head = pdat.split("/", 1)[0]
    if head.isdigit() and len(head) == 4:
        return int(head)
    return None
