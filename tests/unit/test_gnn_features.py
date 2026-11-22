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


def _gz(path, text: str) -> None:
    import gzip

    with gzip.open(path, "wt") as f:
        f.write(text)


def test_gse150954s_signed_fold_change_reads_as_log2(tmp_path) -> None:
    """Its files sign a linear fold change: -4.0 is untreated over treated."""
    from vitiligo.gnn.geo_meta import gse150954_log2fc

    path = tmp_path / "bulge.csv.gz"
    _gz(
        path,
        "Gene,Common_name,Control_mean,Treatment_mean,Fold_change\n"
        "E1,TNMD,1.0,2.0,2.0\n"
        "E2,DPM1,8.0,2.0,-4.0\n"
        "E3,TNMD,1.0,8.0,8.0\n"  # a second TNMD row
        "E4,KIT,0.02,0.6,30.0\n",  # expressed in neither arm
    )
    assert gse150954_log2fc(path) == {"TNMD": 1.0, "DPM1": -2.0}


def test_gse344141_compares_fluoxetine_with_control_in_mouse_symbols(tmp_path) -> None:
    from vitiligo.gnn.geo_meta import gse344141_log2fc

    path = tmp_path / "fpkm.csv.gz"
    _gz(
        path,
        "#Geneid,Ctrl_Replicate_1,Ctrl_Replicate_2,Flu_Replicate_1,Flu_Replicate_2,NB-UVB_Replicate_1\n"
        "ENSMUSG1,1.9,1.9,7.9,7.9,90\n"  # 2.0 -> 8.0 with the pseudocount; NB-UVB is not read
        "ENSMUSG2,0.2,0.2,0.4,0.4,90\n"  # expressed in neither arm
        "ENSMUSG3,7.9,7.9,3.9,3.9,0\n",  # the same symbol, more expressed: it wins
    )
    cache = tmp_path / "symbols.tsv"
    cache.write_text("ENSMUSG1\tSox17\nENSMUSG2\tTyr\nENSMUSG3\tSox17\n", encoding="utf-8")
    assert gse344141_log2fc(path, cache) == {"SOX17": -1.0}


def test_a_cached_id_is_not_asked_of_mygene_again(tmp_path, monkeypatch) -> None:
    import httpx

    from vitiligo.gnn.geo_meta import mouse_symbols

    cache = tmp_path / "symbols.tsv"
    cache.write_text(
        "ENSMUSG1\tSox17\nENSMUSG2\t\n", encoding="utf-8"
    )  # ENSMUSG2: MyGene knew none

    def refuse(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("asked MyGene.info for an id already held")

    monkeypatch.setattr(httpx, "post", refuse)
    assert mouse_symbols(["ENSMUSG1", "ENSMUSG2"], cache) == {"ENSMUSG1": "Sox17"}


def test_a_genes_gwas_score_is_its_strongest_association(test_db_path) -> None:
    """-log10 p, at most 10; an intergenic hit credits the genes on both sides."""
    from sqlmodel import Session

    from vitiligo.gnn.geo_meta import gwas_locus_scores
    from vitiligo.storage import GeneticAssociation, GeneticSourceKind, get_engine

    hits = (
        ("rs2", "TYR", 1e-9),
        ("rs1", "TYR", 1e-6),
        ("rs3", "PTPN22 - AP4B1-AS1", 1e-40),
        ("rs4", "", 1e-8),
    )
    with Session(get_engine()) as session:
        for variant, gene, p in hits:
            session.add(
                GeneticAssociation(
                    source=GeneticSourceKind.GWAS_CATALOG,
                    source_id=f"GCST1:{variant}",
                    trait="Vitiligo",
                    variant=variant,
                    study_accession="GCST1",
                    mapped_gene=gene,
                    p_value=p,
                )
            )
        session.commit()
    assert gwas_locus_scores() == pytest.approx({"TYR": 9.0, "PTPN22": 10.0, "AP4B1-AS1": 10.0})
