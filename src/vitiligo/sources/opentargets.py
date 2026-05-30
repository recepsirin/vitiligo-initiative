"""Open Targets Platform source client — GraphQL API v4.

API docs: https://platform.opentargets.org/api

Open Targets aggregates disease-target-drug associations from genetics,
literature, known drugs, and clinical pipelines. For vitiligo we pull:

- `drugAndClinicalCandidates` — drugs with clinical activity for the disease
- `associatedTargets` — ranked gene targets with association scores

No authentication is required. We paginate GraphQL responses and enrich
drug records with mechanism-of-action data via follow-up queries when the
initial payload is sparse.
"""

from __future__ import annotations

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
from vitiligo.storage.models import Prior, PriorKind, PriorSourceKind

logger = get_logger(__name__)

GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

DEFAULT_DISEASE_QUERY = "vitiligo"
DEFAULT_VITILIGO_EFO_ID = "EFO_0004208"
DEFAULT_TARGET_LIMIT = 200
DEFAULT_TARGET_PAGE_SIZE = 100
DEFAULT_DRUG_PAGE_SIZE = 50


@dataclass(frozen=True)
class DiseaseHandle:
    efo_id: str
    name: str
    query: str


class OpenTargetsClient:
    """Thin client over the Open Targets Platform GraphQL API."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        request_delay_s: float = 0.15,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "User-Agent": "vitiligo-initiative/0.1 (+https://github.com/recepsirin/vitiligo-initiative)",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        self._delay = request_delay_s
        self._last_request_ts = 0.0

    def __enter__(self) -> OpenTargetsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

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
        retry=retry_if_exception_type((httpx.HTTPError,)),
    )
    def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        self._throttle()
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        response = self._client.post(GRAPHQL_URL, json=payload)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        if errors := data.get("errors"):
            raise RuntimeError(f"Open Targets GraphQL error: {errors[0].get('message', errors)}")
        return data

    def resolve_disease(self, query: str = DEFAULT_DISEASE_QUERY) -> DiseaseHandle:
        """Resolve a free-text disease query to the best EFO match."""
        result = self._graphql(
            """
            query ResolveDisease($query: String!) {
              search(queryString: $query, entityNames: ["disease"]) {
                hits { id name entity }
              }
            }
            """,
            {"query": query},
        )
        hits = (result.get("data") or {}).get("search", {}).get("hits") or []
        for hit in hits:
            if hit.get("entity") == "disease" and hit.get("id"):
                return DiseaseHandle(
                    efo_id=str(hit["id"]),
                    name=str(hit.get("name") or query),
                    query=query,
                )
        raise RuntimeError(f"No Open Targets disease match for query '{query}'")

    def iter_drug_priors(
        self,
        efo_id: str,
        disease_name: str,
    ) -> Iterator[Prior]:
        """Yield drug priors for a disease."""
        result = self._graphql(
            """
            query DrugCandidates($efoId: String!) {
              disease(efoId: $efoId) {
                id
                name
                drugAndClinicalCandidates {
                  count
                  rows {
                    id
                    maxClinicalStage
                    drug {
                      id
                      name
                      maximumClinicalStage
                      synonyms
                      description
                    }
                    clinicalReports { id }
                  }
                }
              }
            }
            """,
            {"efoId": efo_id},
        )
        disease = (result.get("data") or {}).get("disease") or {}
        rows = (disease.get("drugAndClinicalCandidates") or {}).get("rows") or []
        logger.info("Open Targets: %d drug candidates for %s", len(rows), efo_id)

        for row in rows:
            drug = row.get("drug") or {}
            chembl_id = (drug.get("id") or "").strip()
            if not chembl_id:
                continue

            mechanisms = self._fetch_drug_mechanisms(chembl_id)
            trial_ids = [
                str(r.get("id")).lower() for r in (row.get("clinicalReports") or []) if r.get("id")
            ]

            yield Prior(
                source=PriorSourceKind.OPENTARGETS,
                kind=PriorKind.DRUG,
                source_id=chembl_id,
                disease_id=efo_id,
                disease_name=disease_name or disease.get("name"),
                name=str(drug.get("name") or chembl_id),
                description=_coerce_str(drug.get("description")),
                score=None,
                clinical_stage=_coerce_str(row.get("maxClinicalStage"))
                or _coerce_str(drug.get("maximumClinicalStage")),
                synonyms=[str(s) for s in (drug.get("synonyms") or []) if s][:20],
                mechanisms=mechanisms,
                linked_trial_ids=trial_ids,
                linked_target_ids=_mechanism_target_ids(mechanisms),
                raw_metadata={"row": row, "drug": drug},
            )

    def iter_target_priors(
        self,
        efo_id: str,
        disease_name: str,
        limit: int = DEFAULT_TARGET_LIMIT,
        page_size: int = DEFAULT_TARGET_PAGE_SIZE,
    ) -> Iterator[Prior]:
        """Yield top associated gene targets for a disease, paginated by score."""
        emitted = 0
        page_index = 0

        while emitted < limit:
            size = min(page_size, limit - emitted)
            result = self._graphql(
                """
                query AssociatedTargets($efoId: String!, $index: Int!, $size: Int!) {
                  disease(efoId: $efoId) {
                    id
                    name
                    associatedTargets(page: { index: $index, size: $size }) {
                      count
                      rows {
                        score
                        target {
                          id
                          approvedSymbol
                          approvedName
                          biotype
                        }
                      }
                    }
                  }
                }
                """,
                {"efoId": efo_id, "index": page_index, "size": size},
            )
            disease = (result.get("data") or {}).get("disease") or {}
            rows = (disease.get("associatedTargets") or {}).get("rows") or []
            if not rows:
                break

            if page_index == 0:
                total = (disease.get("associatedTargets") or {}).get("count")
                logger.info(
                    "Open Targets: fetching up to %d of %s associated targets for %s",
                    limit,
                    total,
                    efo_id,
                )

            for row in rows:
                target = row.get("target") or {}
                ensembl_id = (target.get("id") or "").strip()
                if not ensembl_id:
                    continue
                symbol = _coerce_str(target.get("approvedSymbol")) or ensembl_id
                yield Prior(
                    source=PriorSourceKind.OPENTARGETS,
                    kind=PriorKind.TARGET,
                    source_id=ensembl_id,
                    disease_id=efo_id,
                    disease_name=disease_name or disease.get("name"),
                    name=symbol,
                    description=_coerce_str(target.get("approvedName")),
                    score=float(row.get("score") or 0.0),
                    clinical_stage=None,
                    synonyms=[],
                    mechanisms=[],
                    linked_trial_ids=[],
                    linked_target_ids=[ensembl_id],
                    raw_metadata={"row": row, "target": target},
                )
                emitted += 1
                if emitted >= limit:
                    return

            page_index += 1

    def _fetch_drug_mechanisms(self, chembl_id: str) -> list[dict[str, Any]]:
        result = self._graphql(
            """
            query DrugMechanisms($chemblId: String!) {
              drug(chemblId: $chemblId) {
                mechanismsOfAction {
                  rows {
                    mechanismOfAction
                    actionType
                    targetName
                    targets { id approvedSymbol approvedName }
                  }
                }
              }
            }
            """,
            {"chemblId": chembl_id},
        )
        drug = (result.get("data") or {}).get("drug") or {}
        rows = (drug.get("mechanismsOfAction") or {}).get("rows") or []
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = str(row.get("mechanismOfAction") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "mechanism": row.get("mechanismOfAction"),
                    "action_type": row.get("actionType"),
                    "target_name": row.get("targetName"),
                    "targets": [
                        {
                            "id": t.get("id"),
                            "symbol": t.get("approvedSymbol"),
                            "name": t.get("approvedName"),
                        }
                        for t in (row.get("targets") or [])
                    ],
                }
            )
        return out


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _mechanism_target_ids(mechanisms: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for mech in mechanisms:
        for target in mech.get("targets") or []:
            tid = (target.get("id") or "").strip()
            if tid and tid not in seen:
                seen.add(tid)
                ids.append(tid)
    return ids
