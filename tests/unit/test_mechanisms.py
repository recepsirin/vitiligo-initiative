"""Tests for mechanistic hypothesis records and the gate they must pass."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vitiligo.evidence import EvidenceLevel
from vitiligo.mechanisms import (
    CAUSAL_LADDER,
    causal_rank,
    check_structure,
    from_dict,
    load,
    seal_core,
    seal_hash,
    verify,
)

CURATION = Path(__file__).resolve().parents[2] / "curation" / "mechanisms.json"


def _record(**overrides: Any) -> dict[str, Any]:
    """A record that passes the gate; overrides break one thing at a time."""
    record: dict[str, Any] = {
        "id": "example-claim",
        "title": "An example claim",
        "status": "draft",
        "outcome": 3,
        "biological_state": "Cells of interest persist in treated skin.",
        "mechanistic_claim": "Their survival is necessary for the disease to restart.",
        "intervention": "Block the signal those cells depend on.",
        "experimental_outcome": "The cells fall in treated skin.",
        "clinical_outcome": "Longer time to loss of response.",
        "context": {
            "subtype": "non-segmental",
            "tissue": "repigmented skin",
            "cell_type": "CD8 resident memory T cells",
            "disease_stage": "after withdrawal",
        },
        "upstream": ["IL-15"],
        "downstream": ["loss of response"],
        "evidence": [
            {
                "ref": "pubmed:30021889",
                "stance": "supports",
                "causal_level": "perturbation_in_animal",
                "shows": "Blocking the signal reversed disease in mice.",
            }
        ],
        "competing": [
            {
                "explanation": "The cells are a marker, not a cause.",
                "distinguished_by": "Whether their density predicts relapse.",
            }
        ],
        "test": {
            "question": "Does the score predict loss of response?",
            "data": "Biopsies taken when treatment stops.",
            "if_correct": "Hazard ratio per standard deviation above 1.",
            "if_incorrect": "No association.",
            "decides": "An association leaves the claim standing.",
        },
        "uncertainty": "Small samples.",
        "last_reviewed": "2026-10-23",
    }
    record.update(overrides)
    return record


def _structure(**overrides: Any) -> list[str]:
    return check_structure([from_dict(_record(**overrides))])


def test_a_complete_record_passes_the_structure_gate() -> None:
    assert _structure() == []


def test_causal_support_is_computed_from_supporting_evidence_only() -> None:
    """A claim may not outrank its evidence: stance decides what counts."""
    mechanism = from_dict(
        _record(
            evidence=[
                {
                    "ref": "geo:GSE203262",
                    "stance": "supports",
                    "causal_level": "association",
                    "shows": "Cells are present in lesional skin.",
                },
                {
                    "ref": "trial:NCT04338581",
                    "stance": "bounds",
                    "causal_level": "perturbation_in_human",
                    "shows": "A trial of the same drug asked a different question.",
                },
            ]
        )
    )
    # The human perturbation only bounds the claim, so support stays at association.
    assert mechanism.causal_support == "association"
    assert [e.ref for e in mechanism.bounding()] == ["trial:NCT04338581"]


def test_causal_support_is_none_without_supporting_evidence() -> None:
    mechanism = from_dict(_record(evidence=[]))
    assert mechanism.causal_support == "none"


def test_causal_rank_orders_the_ladder() -> None:
    ranks = [causal_rank(level) for level in CAUSAL_LADDER]
    assert ranks == sorted(ranks)
    assert causal_rank("association") < causal_rank("perturbation_in_human")
    assert causal_rank("not-a-level") == -1


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"id": "Not Kebab Case"}, "kebab-case"),
        ({"outcome": 9}, "outcome must be one of"),
        ({"status": "proven"}, "unknown status"),
        ({"mechanistic_claim": "  "}, "mechanistic_claim is empty"),
        ({"uncertainty": ""}, "uncertainty is empty"),
        ({"competing": []}, "no competing explanation"),
        ({"evidence": []}, "no supporting evidence"),
        ({"last_reviewed": "23/10/2026"}, "is not an ISO date"),
        ({"status": "sealed"}, "needs a seal"),
    ],
)
def test_structure_gate_rejects(overrides: dict[str, Any], expected: str) -> None:
    problems = _structure(**overrides)
    assert any(expected in p for p in problems), problems


def test_a_claim_that_cannot_fail_is_rejected() -> None:
    same = dict(
        _record()["test"], if_correct="Something happens.", if_incorrect="Something happens."
    )
    assert any("it cannot fail" in p for p in _structure(test=same))


def test_context_must_be_filled_in() -> None:
    thin = dict(_record()["context"], cell_type="   ")
    assert any("context.cell_type is empty" in p for p in _structure(context=thin))


def test_competing_explanation_needs_a_way_to_tell_them_apart() -> None:
    problems = _structure(competing=[{"explanation": "A rival.", "distinguished_by": ""}])
    assert any("distinguished_by" in p for p in problems)


def test_evidence_stance_and_level_must_be_known() -> None:
    problems = _structure(
        evidence=[
            {
                "ref": "pubmed:30021889",
                "stance": "proves",
                "causal_level": "obviously_causal",
                "shows": "x",
            }
        ]
    )
    assert any("unknown stance" in p for p in problems)
    assert any("unknown causal level" in p for p in problems)


def test_verify_reports_citations_that_do_not_resolve() -> None:
    problems = verify(
        [from_dict(_record())],
        resolve=lambda ref: f"{ref} is not in the corpus",
        level_of=lambda ref: None,
    )
    assert any("is not in the corpus" in p for p in problems)


def test_verify_rejects_a_human_claim_on_a_mouse_study() -> None:
    """The corpus decides what a source is, not the curator."""
    record = _record(
        evidence=[
            {
                "ref": "pubmed:30021889",
                "stance": "supports",
                "causal_level": "perturbation_in_human",
                "shows": "Overstated.",
            }
        ]
    )
    problems = verify(
        [from_dict(record)],
        resolve=lambda ref: None,
        level_of=lambda ref: EvidenceLevel.MOUSE,
    )
    assert any("cannot carry 'perturbation_in_human'" in p for p in problems)


def test_an_animal_claim_on_a_mouse_study_is_fine() -> None:
    problems = verify(
        [from_dict(_record())],
        resolve=lambda ref: None,
        level_of=lambda ref: EvidenceLevel.MOUSE,
    )
    assert problems == []


def test_an_in_vitro_source_cannot_carry_an_animal_claim() -> None:
    record = _record(
        evidence=[
            {
                "ref": "geo:GSE203262",
                "stance": "supports",
                "causal_level": "perturbation_in_animal",
                "shows": "Overstated.",
            }
        ]
    )
    problems = verify(
        [from_dict(record)], resolve=lambda ref: None, level_of=lambda ref: EvidenceLevel.IN_VITRO
    )
    assert any("cannot carry 'perturbation_in_animal'" in p for p in problems)


def test_duplicate_ids_are_rejected() -> None:
    problems = check_structure([from_dict(_record()), from_dict(_record())])
    assert any("duplicate id" in p for p in problems)


def test_seal_covers_the_claim_and_test_but_not_the_evidence() -> None:
    mechanism = from_dict(_record())
    sealed = seal_hash(mechanism)
    assert "evidence" not in seal_core(mechanism)

    grown = _record(
        evidence=[
            *_record()["evidence"],
            {
                "ref": "geo:GSE203262",
                "stance": "supports",
                "causal_level": "association",
                "shows": "A source found later.",
            },
        ],
        note="Rewritten note.",
    )
    assert seal_hash(from_dict(grown)) == sealed

    reworded = _record(mechanistic_claim="A quietly different claim.")
    assert seal_hash(from_dict(reworded)) != sealed


def test_a_tampered_seal_is_caught() -> None:
    original = from_dict(_record())
    tampered = from_dict(
        _record(
            mechanistic_claim="Reworded after sealing.",
            status="sealed",
            seal={"sha256": seal_hash(original), "sealed_at": "2026-10-23T00:00:00Z"},
        )
    )
    assert any("seal does not match" in p for p in check_structure([tampered]))


def test_a_matching_seal_passes() -> None:
    mechanism = from_dict(_record(status="sealed"))
    sealed = from_dict(
        _record(
            status="sealed",
            seal={"sha256": seal_hash(mechanism), "sealed_at": "2026-10-23T00:00:00Z"},
        )
    )
    assert check_structure([sealed]) == []


def test_curated_mechanisms_pass_the_structure_gate() -> None:
    """The shipped records must be well-formed without a corpus (citations need one)."""
    mechanisms = load(CURATION)
    assert len(mechanisms) >= 2
    assert check_structure(mechanisms) == []


def test_curated_mechanisms_cite_only_known_reference_kinds() -> None:
    kinds = {e.ref.split(":")[0] for m in load(CURATION) for e in m.evidence}
    assert kinds <= {"pubmed", "pmc", "geo", "trial", "gwas"}


def test_curation_file_is_valid_json_with_provenance() -> None:
    raw = json.loads(CURATION.read_text())
    assert raw["description"] and raw["curated"]


def test_a_partial_record_is_reported_not_crashed() -> None:
    """A curator's half-written record must reach the gate, not raise in the loader."""
    mechanism = from_dict({"id": "half-written"})
    problems = check_structure([mechanism])
    assert any("title is empty" in p for p in problems)
    assert any("no supporting evidence" in p for p in problems)
    assert any("no competing explanation" in p for p in problems)


def test_malformed_nested_values_are_reported_not_crashed() -> None:
    mechanism = from_dict({"id": "malformed", "context": "a string", "evidence": "not a list"})
    assert any("context.subtype is empty" in p for p in check_structure([mechanism]))


def test_non_text_fields_are_reported_not_crashed() -> None:
    mechanism = from_dict({"id": 5, "title": 12, "last_reviewed": 2026, "seal": "oops"})
    problems = check_structure([mechanism])
    assert any("id must be kebab-case" in p for p in problems)
    assert any("title is empty" in p for p in problems)
    assert any("is not an ISO date" in p for p in problems)


def test_a_gwas_study_is_a_citable_source() -> None:
    """Human genetics is a rung of the ladder, so records must be able to cite it."""
    record = _record(
        evidence=[
            {
                "ref": "gwas:GCST004785",
                "stance": "supports",
                "causal_level": "human_genetics",
                "shows": "A variant near the gene associates with the disease.",
            }
        ]
    )
    problems = verify([from_dict(record)], resolve=lambda ref: None, level_of=lambda ref: None)
    assert problems == []


def test_an_unknown_citation_kind_is_still_rejected() -> None:
    record = _record(
        evidence=[
            {"ref": "doi:10.1/x", "stance": "supports", "causal_level": "association", "shows": "y"}
        ]
    )
    problems = verify(
        [from_dict(record)],
        resolve=__import__("vitiligo.mechanisms.verify", fromlist=["resolve_ref"]).resolve_ref,
    )
    assert any("malformed citation" in p for p in problems)


def test_a_declared_need_for_new_data_must_say_what_is_missing() -> None:
    """A flag with no reason cannot be acted on, and hides the real blocker."""
    test = dict(_record()["test"], needs_new_data=True, new_data="")
    assert any("test.new_data must say" in p for p in _structure(test=test))

    stated = dict(_record()["test"], needs_new_data=True, new_data="Skin after withdrawal.")
    assert _structure(test=stated) == []
