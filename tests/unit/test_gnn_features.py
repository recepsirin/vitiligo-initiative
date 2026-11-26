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


def test_a_merged_entity_is_found_by_the_names_it_absorbed(test_db_path, tmp_path) -> None:
    """The MeSH merge made "calcipotriol" an alias of "calcipotriene", and the
    reranker's labels, looked up by name, silently lost it (and fluticasone)."""
    from sqlmodel import Session

    from vitiligo.gnn.dataset import load_graph_dataset
    from vitiligo.graph.store import upsert_entity
    from vitiligo.storage import get_engine
    from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity, RelationKind

    with Session(get_engine(), expire_on_commit=False) as session:
        drug = upsert_entity(session, kind=EntityKind.DRUG, name="calcipotriene")
        drug.aliases = ["calcipotriene", "Calcipotriol", "vitamin D analogue"]
        other = upsert_entity(session, kind=EntityKind.DRUG, name="tacalcitol")
        other.aliases = ["tacalcitol", "vitamin D analogue"]  # held twice: resolves to neither
        named = upsert_entity(session, kind=EntityKind.DRUG, name="Calcipotriol")  # a display name
        named.aliases = ["Calcipotriol solution"]
        disease = upsert_entity(session, kind=EntityKind.DISEASE, name="Vitiligo")
        for subject in (drug, other, named):
            session.add(
                GraphEdge(
                    subject_id=subject.id,  # type: ignore[arg-type]
                    predicate=RelationKind.TREATS,
                    object_id=disease.id,  # type: ignore[arg-type]
                    confidence=0.5,
                    extraction_method="structured",
                    evidence=[],
                    claim=ClaimKind.ASSERTED,
                )
            )
        session.commit()
    dataset = load_graph_dataset(
        db_path=test_db_path, cache_path=tmp_path / "ds.pt", force_reload=True
    )
    index = {e.name: e.idx for e in dataset.entities}
    assert dataset.name_to_idx["calcipotriol"] == index["Calcipotriol"]  # the display name wins
    del dataset  # and without that entity, the alias finds the merged one:
    with Session(get_engine()) as session:
        session.delete(session.get(GraphEntity, named.id))
        session.commit()
    dataset = load_graph_dataset(
        db_path=test_db_path, cache_path=tmp_path / "ds2.pt", force_reload=True
    )
    index = {e.name: e.idx for e in dataset.entities}
    assert dataset.name_to_idx["calcipotriol"] == index["calcipotriene"]
    assert dataset.name_to_idx["Calcipotriol"] == index["calcipotriene"]
    assert "vitamin d analogue" not in dataset.name_to_idx


def _drug_edge(session, subject, obj, method: str, *source_ids: str) -> None:
    from vitiligo.storage.models import ClaimKind, GraphEdge, RelationKind

    session.add(
        GraphEdge(
            subject_id=subject.id,
            predicate=RelationKind.INHIBITS,
            object_id=obj.id,
            confidence=0.8,
            extraction_method=method,
            evidence=[{"source_type": "prior", "source_id": s} for s in source_ids],
            claim=ClaimKind.ASSERTED,
        )
    )


def test_a_relation_resting_only_on_drugbank_is_not_trained_on(test_db_path, tmp_path) -> None:
    """The public release drops them (its terms forbid redistribution), so the graph the
    model trains on is the graph that was published: 95,238 - 2 = the release's 95,236."""
    from sqlmodel import Session

    from vitiligo.gnn.dataset import load_graph_dataset
    from vitiligo.graph.store import upsert_entity
    from vitiligo.storage import get_engine
    from vitiligo.storage.models import EntityKind

    with Session(get_engine(), expire_on_commit=False) as session:
        drug = upsert_entity(session, kind=EntityKind.DRUG, name="monobenzone")
        drug.external_ids = {"chembl": "CHEMBL1"}
        tyr = upsert_entity(session, kind=EntityKind.TARGET, name="TYR")
        jak1 = upsert_entity(session, kind=EntityKind.TARGET, name="JAK1")
        jak2 = upsert_entity(session, kind=EntityKind.TARGET, name="JAK2")
        _drug_edge(session, drug, tyr, "structured", "drugbank:DB00600")  # dropped
        _drug_edge(session, drug, jak1, "chembl_mechanism", "chembl:CHEMBL1")  # kept
        # Mixed evidence is kept: the release drops the DrugBank row, not the relation.
        _drug_edge(session, drug, jak2, "structured", "drugbank:DB00600", "chembl:CHEMBL1")
        session.commit()
    dataset = load_graph_dataset(
        db_path=test_db_path, cache_path=tmp_path / "ds.pt", force_reload=True
    )
    name_of = {e.idx: e.name for e in dataset.entities}
    objects = [name_of[int(i)] for i in dataset.edge_index[1]]
    assert dataset.num_edges == 2 and sorted(objects) == ["JAK1", "JAK2"]


def test_only_drugs_a_database_or_a_trial_records_are_screenable(test_db_path, tmp_path) -> None:
    """Chloroform, glucose, serotonin and nitrogen ranked among the reverse screen's top
    five for a target, each known only from sentences in papers."""
    from sqlmodel import Session

    from vitiligo.gnn.dataset import load_graph_dataset
    from vitiligo.graph.store import upsert_entity
    from vitiligo.storage import get_engine
    from vitiligo.storage.models import EntityKind

    with Session(get_engine(), expire_on_commit=False) as session:
        target = upsert_entity(session, kind=EntityKind.TARGET, name="JAK1")
        for name, method in (
            ("ruxolitinib", "chembl_mechanism"),  # a drug database records it
            ("selenium", "structured"),  # given in a registered trial
            ("chloroform", "pubtator3"),  # a paper mentions it
            ("glucose", "biored-biomedbert-silver-gold"),  # the extractor read it
        ):
            drug = upsert_entity(session, kind=EntityKind.DRUG, name=name)
            drug.external_ids = {"chembl": f"CHEMBL-{name}"}  # all four are canonical drugs
            _drug_edge(session, drug, target, method, f"{method}:1")
        session.commit()
    dataset = load_graph_dataset(
        db_path=test_db_path, cache_path=tmp_path / "ds.pt", force_reload=True
    )
    name_of = {e.idx: e.name for e in dataset.entities}
    assert sorted(name_of[i] for i in dataset.canonical_drug_indices) == [
        "chloroform",
        "glucose",
        "ruxolitinib",
        "selenium",
    ]
    assert sorted(name_of[i] for i in dataset.screenable_drug_indices) == [
        "ruxolitinib",
        "selenium",
    ]


def test_the_enriched_dataset_keeps_every_field_of_the_base_one() -> None:
    """build_enriched_graph_dataset rebuilds the dataclass by hand, so a field added to
    GraphDataset is silently dropped from the cache the model trains on."""
    import dataclasses
    import inspect

    from vitiligo.gnn import geo_meta
    from vitiligo.gnn.dataset import GraphDataset

    source = inspect.getsource(geo_meta.build_enriched_graph_dataset)
    for f in dataclasses.fields(GraphDataset):
        assert f"{f.name}=" in source, (
            f"GraphDataset.{f.name} is not passed to the enriched dataset"
        )
        assert f'"{f.name}"' in source, f"GraphDataset.{f.name} is not saved in the enriched cache"
