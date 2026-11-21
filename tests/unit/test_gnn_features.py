"""The graph model's node features: rebuilt from recorded inputs, compared block by block."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")


def test_a_drug_pubchem_could_not_resolve_is_asked_again_only_on_request(
    tmp_path, monkeypatch
) -> None:
    import vitiligo.gnn.chemicals as chem

    cache = tmp_path / "drug_smiles.json"
    cache.write_text(json.dumps({"tofacitinib": "CC1CCNCC1", "brand-x": None}))
    asked: list[str] = []

    def fetch(name: str, held: dict[str, str | None]) -> None:
        asked.append(name)
        held[name] = None  # as PubChem answers for a name it does not know

    monkeypatch.setattr(chem, "fetch_pubchem_smiles", fetch)
    names = ("tofacitinib", "brand-x", "zasocitinib")
    dataset = SimpleNamespace(
        canonical_drug_indices=[0, 1, 2],
        kind_to_indices={},
        entities=[SimpleNamespace(name=n) for n in names],
    )
    assert chem.resolve_all_drug_smiles(dataset, cache_path=cache) == {"tofacitinib": "CC1CCNCC1"}
    assert asked == ["zasocitinib"]  # only the name never looked up
    asked.clear()
    chem.resolve_all_drug_smiles(dataset, cache_path=cache, refresh_unresolved=True)
    assert sorted(asked) == ["brand-x", "zasocitinib"]


def test_empty_dimensions_are_the_columns_no_entity_fills() -> None:
    from vitiligo.gnn.geo_meta import empty_dimensions

    features = torch.zeros(3, 4)
    features[0, 1], features[2, 3] = 0.5, -1.0
    assert empty_dimensions(features) == [0, 2]


def test_only_the_block_that_differs_is_flagged() -> None:
    from vitiligo.gnn.geo_meta import compare_feature_blocks

    saved = torch.zeros(2, 1936)
    rebuilt = saved.clone()
    rebuilt[1, 1800] = 0.25  # an HGNC gene-group column
    rows = compare_feature_blocks(saved, rebuilt)
    assert [(r["block"], r["identical"]) for r in rows] == [
        ("BiomedBERT name embedding", True),
        ("Morgan fingerprint", True),
        ("HGNC gene groups", False),
        ("GEO profile", True),
    ]
    assert rows[2]["max_difference"] == 0.25
