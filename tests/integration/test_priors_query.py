"""Integration tests for prior retrieval ordering (seeded temp DB)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session

from vitiligo.priors import clinical_stage_rank, list_drug_priors, retrieve_priors_for_hypothesize
from vitiligo.storage import Prior, PriorKind, PriorSourceKind, get_engine

pytestmark = pytest.mark.integration


def _drug(name: str, stage: str | None) -> Prior:
    return Prior(
        source=PriorSourceKind.OPENTARGETS,
        kind=PriorKind.DRUG,
        source_id=f"CHEMBL_{name}",
        disease_id="EFO_0004208",
        name=name,
        clinical_stage=stage,
    )


@pytest.fixture
def seeded_prior_db(test_db_path: Path) -> Path:
    drugs = [_drug("APPROVED_DRUG", "APPROVAL"), _drug("UNKNOWN_DRUG", "UNKNOWN")]
    drugs += [_drug(f"PHASE3_DRUG_{i:02d}", "PHASE_3") for i in range(20)]
    drugs += [_drug("PHASE1_DRUG", "PHASE_1"), _drug("EARLY_DRUG", "EARLY_PHASE_1")]
    with Session(get_engine(), expire_on_commit=False) as session:
        session.add_all(drugs)
        session.commit()
    return test_db_path


def test_clinical_stage_rank_is_ordinal_not_lexical() -> None:
    assert clinical_stage_rank("APPROVAL") > clinical_stage_rank("PHASE_4")
    assert clinical_stage_rank("PHASE_3") > clinical_stage_rank("PHASE_2_3")
    assert clinical_stage_rank("PHASE_1") > clinical_stage_rank("EARLY_PHASE_1")
    assert clinical_stage_rank("UNKNOWN") == clinical_stage_rank(None) == 0


def test_list_drug_priors_orders_by_stage_rank(seeded_prior_db) -> None:
    names = [p.name for p in list_drug_priors(limit=100)]
    assert names[0] == "APPROVED_DRUG"
    assert names.index("PHASE1_DRUG") < names.index("EARLY_DRUG") < names.index("UNKNOWN_DRUG")


def test_hypothesize_priors_keep_approved_drugs(seeded_prior_db) -> None:
    """Approved drugs must survive the drug_limit cut (they sorted last as text)."""
    drugs = [p for p in retrieve_priors_for_hypothesize(drug_limit=15) if p.kind == PriorKind.DRUG]
    names = [p.name for p in drugs]
    assert len(drugs) == 15
    assert names[0] == "APPROVED_DRUG"
    assert "PHASE1_DRUG" not in names


def test_candidate_bundle_keeps_most_advanced_salt_form(test_db_path: Path) -> None:
    """A salt-form prior listed later must not downgrade the parent drug's stage."""
    from vitiligo.reports.candidates import _collect_drug_bundles

    with Session(get_engine(), expire_on_commit=False) as session:
        session.add_all(
            [_drug("RITLECITINIB", "PHASE_3"), _drug("RITLECITINIB TOSYLATE", "PHASE_2")]
        )
        session.commit()

    bundles = _collect_drug_bundles()
    prior = bundles["ritlecitinib"].prior
    assert prior is not None
    assert prior.clinical_stage == "PHASE_3"
