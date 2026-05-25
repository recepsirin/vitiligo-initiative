"""Offline tests for the Open Targets GraphQL client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from vitiligo.sources.opentargets import OpenTargetsClient
from vitiligo.storage.models import PriorKind, PriorSourceKind

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


class _FixtureTransport(httpx.BaseTransport):
    """Return canned GraphQL payloads keyed by operation name fragments."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._idx = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        query = body.get("query", "")
        if "ResolveDisease" in query:
            payload = _load("opentargets_resolve.json")
        elif "DrugCandidates" in query:
            payload = _load("opentargets_drugs.json")
        elif "AssociatedTargets" in query:
            payload = _load("opentargets_targets.json")
        elif "DrugMechanisms" in query:
            payload = _load("opentargets_mechanisms.json")
        else:
            payload = self._responses[self._idx]
            self._idx += 1
        return httpx.Response(200, json=payload)


def test_resolve_disease_returns_vitiligo_efo() -> None:
    transport = _FixtureTransport([])
    client = httpx.Client(transport=transport)
    with OpenTargetsClient(client=client, request_delay_s=0) as ot:
        handle = ot.resolve_disease("vitiligo")
    assert handle.efo_id == "EFO_0004208"
    assert "vitiligo" in handle.name.lower()


def test_iter_drug_priors_parses_ruxolitinib() -> None:
    transport = _FixtureTransport([])
    client = httpx.Client(transport=transport)
    with OpenTargetsClient(client=client, request_delay_s=0) as ot:
        drugs = list(ot.iter_drug_priors("EFO_0004208", "Vitiligo"))

    assert len(drugs) == 37
    rux = next(d for d in drugs if d.name == "RUXOLITINIB")
    assert rux.source == PriorSourceKind.OPENTARGETS
    assert rux.kind == PriorKind.DRUG
    assert rux.source_id == "CHEMBL1789941"
    assert rux.clinical_stage == "APPROVAL"
    assert "nct03099304" in rux.linked_trial_ids
    assert rux.linked_target_ids  # enriched from mechanisms query


def test_iter_target_priors_parses_top_associations() -> None:
    transport = _FixtureTransport([])
    client = httpx.Client(transport=transport)
    with OpenTargetsClient(client=client, request_delay_s=0) as ot:
        targets = list(ot.iter_target_priors("EFO_0004208", "Vitiligo", limit=2))

    assert len(targets) == 2
    assert all(t.kind == PriorKind.TARGET for t in targets)
    assert all(t.score is not None and t.score > 0 for t in targets)
    assert targets[0].source_id.startswith("ENSG")
