"""Offline tests for the DrugBank XML parser."""

from __future__ import annotations

from tests.helpers.paths import FIXTURES_DIR

from vitiligo.sources.drugbank import (
    count_drugbank_drugs,
    iter_drugbank_priors,
    normalize_drug_name,
)
from vitiligo.storage.models import PriorKind, PriorSourceKind

FIXTURE = FIXTURES_DIR / "drugbank_vitiligo_sample.xml"


def test_count_drugs_in_fixture() -> None:
    assert count_drugbank_drugs(FIXTURE) == 3


def test_filters_to_vitiligo_drugs_and_targets() -> None:
    priors = list(iter_drugbank_priors(FIXTURE, query="vitiligo"))
    drugs = [p for p in priors if p.kind == PriorKind.DRUG]
    targets = [p for p in priors if p.kind == PriorKind.TARGET]

    assert len(drugs) == 2
    assert {d.source_id for d in drugs} == {"DB00600", "DB08877"}
    assert all(d.source == PriorSourceKind.DRUGBANK for d in drugs)
    assert drugs[0].clinical_stage == "APPROVAL"
    assert "vitiligo" in (drugs[0].raw_metadata.get("indication") or "").lower()

    assert len(targets) == 2
    assert {t.source_id for t in targets} == {"P14679", "P23458"}
    assert any(t.name == "JAK1" for t in targets)


def test_seed_name_matching_without_query_hit() -> None:
    priors = list(
        iter_drugbank_priors(
            FIXTURE,
            query="unlikely-term-xyz",
            seed_names={normalize_drug_name("Ruxolitinib")},
        )
    )
    drug_ids = {p.source_id for p in priors if p.kind == PriorKind.DRUG}
    assert drug_ids == {"DB08877"}
