"""Unit tests for the Relational GNN dataset, architecture, and screening engine."""

from __future__ import annotations

import pytest

try:
    import torch
    import torch_geometric  # noqa: F401

    from vitiligo.gnn.dataset import (
        EntityMeta,
        GraphDataset,
        compute_causal_edge_weight,
    )
    from vitiligo.gnn.model import RelationalGNN

    HAS_GNN_DEPS = True
except ImportError:
    HAS_GNN_DEPS = False

pytestmark = pytest.mark.skipif(
    not HAS_GNN_DEPS, reason="torch and torch_geometric are required for GNN tests"
)


def _make_dummy_dataset() -> GraphDataset:
    entities = [
        EntityMeta(0, 101, "DRUG", "tofacitinib", "tofacitinib"),
        EntityMeta(1, 102, "DRUG", "ritlecitinib", "ritlecitinib"),
        EntityMeta(2, 103, "DISEASE", "vitiligo", "vitiligo"),
        EntityMeta(3, 104, "TARGET", "jak1", "JAK1"),
        EntityMeta(4, 105, "TARGET", "il15", "IL15"),
        EntityMeta(5, 106, "TARGET", "ctnnb1", "CTNNB1"),
    ]
    id_to_idx = {e.db_id: e.idx for e in entities}
    name_to_idx = {e.name: e.idx for e in entities}
    name_to_idx.update({e.name.lower(): e.idx for e in entities})
    key_to_idx = {e.key: e.idx for e in entities}
    kind_to_indices = {
        "DRUG": [0, 1],
        "DISEASE": [2],
        "TARGET": [3, 4, 5],
    }
    relations = ["TREATS", "INHIBITS", "ACTIVATES", "ASSOCIATED_WITH"]
    rel_to_idx = {r: i for i, r in enumerate(relations)}

    # Triples:
    # 0 -> 2 (tofacitinib TREATS vitiligo)
    # 1 -> 2 (ritlecitinib TREATS vitiligo)
    # 0 -> 3 (tofacitinib INHIBITS JAK1)
    # 1 -> 4 (ritlecitinib INHIBITS IL15)
    # 2 -> 3 (vitiligo ASSOCIATED_WITH JAK1)
    edge_index = torch.tensor(
        [[0, 1, 0, 1, 2], [2, 2, 3, 4, 3]],
        dtype=torch.long,
    )
    edge_type = torch.tensor([0, 0, 1, 1, 3], dtype=torch.long)
    edge_weight = torch.tensor([1.0, 0.9, 0.8, 0.7, 0.5], dtype=torch.float)

    return GraphDataset(
        entities=entities,
        id_to_idx=id_to_idx,
        name_to_idx=name_to_idx,
        key_to_idx=key_to_idx,
        kind_to_indices=kind_to_indices,
        relation_to_idx=rel_to_idx,
        idx_to_relation=relations,
        edge_index=edge_index,
        edge_type=edge_type,
        edge_weight=edge_weight,
        canonical_drug_indices=[0, 1],
    )


def test_compute_causal_edge_weight() -> None:
    # Observed clinical perturbation gets highest weight
    assert compute_causal_edge_weight("OBSERVED", "perturbation_in_human", 0.9) == 1.0
    # Observed animal perturbation
    assert compute_causal_edge_weight("OBSERVED", "perturbation_in_animal", 0.9) == 0.85
    # Unverified assertion gets scaled by confidence
    assert compute_causal_edge_weight("ASSERTED", None, 0.8) == 0.40
    # Floor weight for low confidence assertion
    assert compute_causal_edge_weight("ASSERTED", None, 0.1) == 0.20
    # Predicate-specific calibration
    assert (
        compute_causal_edge_weight("OBSERVED", "perturbation_in_human", 0.9, predicate="CHANGES")
        == 0.20
    )
    assert compute_causal_edge_weight("ASSERTED", None, 0.88, predicate="TREATS") >= 0.75
    assert compute_causal_edge_weight("ASSERTED", None, 0.84, predicate="INHIBITS") >= 0.70
    assert (
        compute_causal_edge_weight("OBSERVED", "knowledge_base", 0.92, predicate="PARTICIPATES_IN")
        == 0.90
    )


def test_dataset_conversions() -> None:
    ds = _make_dummy_dataset()
    assert ds.num_nodes == 6
    assert ds.num_edges == 5
    assert ds.num_relations == 4

    pyg_data = ds.to_pyg_data()
    assert pyg_data.num_nodes == 6
    assert pyg_data.edge_index.size(1) == 5

    hetero = ds.to_hetero_data()
    assert "DRUG" in hetero.node_types
    assert "DISEASE" in hetero.node_types
    assert "TARGET" in hetero.node_types
    assert len(hetero.edge_types) > 0


def test_dataset_split() -> None:
    ds = _make_dummy_dataset()
    train_ds, val_edges, test_edges = ds.split_edges(val_ratio=0.2, test_ratio=0.2, seed=42)
    assert (
        train_ds.num_edges + val_edges["edge_index"].size(1) + test_edges["edge_index"].size(1)
        == ds.num_edges
    )


def test_relational_gnn_forward_and_loss() -> None:
    ds = _make_dummy_dataset()
    model = RelationalGNN(
        num_nodes=ds.num_nodes, num_relations=ds.num_relations, hidden_dim=32, num_layers=1
    )

    h = model.encode(ds.edge_index, ds.edge_type)
    assert h.shape == (ds.num_nodes, 32)

    loss = model.compute_loss(
        h,
        ds.edge_index[0],
        ds.edge_type,
        ds.edge_index[1],
        edge_weights=ds.edge_weight,
    )
    assert loss.item() > 0.0

    predictions = model.predict_top_k("tofacitinib", "TREATS", ds, top_k=3)
    assert len(predictions) > 0
    assert "score" in predictions[0]
    assert "name" in predictions[0]

    # Test reverse prediction: (?, TREATS, vitiligo)
    rev_predictions = model.predict_top_k(
        tail_name="vitiligo", rel_name="TREATS", dataset=ds, top_k=3
    )
    assert len(rev_predictions) > 0
    assert "score" in rev_predictions[0]

    # Test triple scoring: (tofacitinib, TREATS, vitiligo)
    triple_score = model.predict_top_k(
        head_name="tofacitinib", tail_name="vitiligo", rel_name="TREATS", dataset=ds
    )
    assert len(triple_score) == 1
    assert triple_score[0]["head"] == "tofacitinib"
    assert triple_score[0]["tail"] == "vitiligo"
    assert "probability" in triple_score[0]

    # Test decode_all_heads and decode_all_tails consistency
    heads_scores = model.decode_all_heads(h, torch.tensor([0]), torch.tensor([2]))
    assert heads_scores.shape == (1, ds.num_nodes)
    tails_scores = model.decode_all_tails(h, torch.tensor([0]), torch.tensor([0]))
    assert tails_scores.shape == (1, ds.num_nodes)


def test_multimodal_gnn_features_and_sampling() -> None:
    ds = _make_dummy_dataset()
    node_features = torch.randn(ds.num_nodes, 16)
    ds.node_features = node_features

    model = RelationalGNN(
        num_nodes=ds.num_nodes,
        num_relations=ds.num_relations,
        hidden_dim=32,
        num_layers=1,
        feature_dim=16,
    )
    h = model.encode(ds.edge_index, ds.edge_type, node_features=ds.node_features)
    assert h.shape == (ds.num_nodes, 32)

    sampling_weights = torch.tensor([0.1, 0.1, 0.3, 0.2, 0.15, 0.15])
    loss = model.compute_loss(
        h,
        ds.edge_index[0],
        ds.edge_type,
        ds.edge_index[1],
        edge_weights=ds.edge_weight,
        sampling_weights=sampling_weights,
    )
    assert loss.item() > 0.0


def test_screen_candidates(tmp_path) -> None:
    from vitiligo.gnn.screen import screen_candidates

    ds = _make_dummy_dataset()
    model = RelationalGNN(
        num_nodes=ds.num_nodes, num_relations=ds.num_relations, hidden_dim=16, num_layers=1
    )

    json_path = tmp_path / "screen_test.json"
    md_path = tmp_path / "screen_test.md"

    results = screen_candidates(
        model=model,
        dataset=ds,
        top_k=2,
        export_json=json_path,
        export_markdown=md_path,
    )

    assert "durability_top_k" in results
    assert "regeneration_top_k" in results
    assert json_path.exists()
    assert md_path.exists()


def test_evaluate_link_prediction_filtered() -> None:
    from vitiligo.gnn.train import build_type_sampler, evaluate_link_prediction

    ds = _make_dummy_dataset()
    model = RelationalGNN(
        num_nodes=ds.num_nodes, num_relations=ds.num_relations, hidden_dim=16, num_layers=1
    )
    sampler = build_type_sampler(ds, model.device)
    assert "node_to_kind" in sampler
    assert sampler["sorted_nodes"].shape == (ds.num_nodes,)

    eval_edges = {
        "edge_index": ds.edge_index,
        "edge_type": ds.edge_type,
    }
    metrics = evaluate_link_prediction(model, ds, eval_edges, max_eval_samples=None)

    assert metrics.sample_size == ds.num_edges
    assert 0.0 <= metrics.mrr <= 1.0
    assert 0.0 <= metrics.filtered_mrr <= 1.0
    assert 0.0 <= metrics.type_constrained_mrr <= 1.0
    assert 0.0 <= metrics.therapeutic_mrr <= 1.0
    assert len(metrics.per_relation) > 0
    assert "TREATS" in metrics.per_relation
    assert "type_constrained_mrr" in metrics.per_relation["TREATS"]


def test_dense_curative_reranker() -> None:
    from vitiligo.gnn.rerank import RERANKER_FEATURE_DIM, DenseCurativeReranker

    reranker = DenseCurativeReranker(in_dim=RERANKER_FEATURE_DIM, hidden_dim=64)
    dummy_x = torch.randn(4, RERANKER_FEATURE_DIM)
    logits = reranker(dummy_x)
    assert logits.shape == (4,)
    probs = reranker.predict_score(dummy_x)
    assert probs.shape == (4,)
    assert ((probs >= 0.0) & (probs <= 1.0)).all()


def test_rgat_forward_and_loss() -> None:
    ds = _make_dummy_dataset()
    node_features = torch.randn(ds.num_nodes, 16)
    ds.node_features = node_features
    model = RelationalGNN(
        num_nodes=ds.num_nodes,
        num_relations=ds.num_relations,
        hidden_dim=32,
        num_layers=2,
        encoder_type="rgat",
        heads=2,
        feature_dim=16,
    )
    h = model.encode(ds.edge_index, ds.edge_type, node_features=ds.node_features)
    assert h.shape == (ds.num_nodes, 32)
    loss = model.compute_loss(
        h,
        ds.edge_index[0],
        ds.edge_type,
        ds.edge_index[1],
        edge_weights=ds.edge_weight,
    )
    assert loss.item() > 0.0


def test_synergy_metrics_and_screening(tmp_path) -> None:
    import json

    import numpy as np

    from vitiligo.gnn.synergy import (
        compute_tanimoto,
        compute_target_orthogonality,
        screen_pairwise_synergy,
    )

    # Test compute_tanimoto
    fp1 = np.array([1, 0, 1, 1, 0], dtype=bool)
    fp2 = np.array([1, 0, 0, 1, 1], dtype=bool)
    assert compute_tanimoto(fp1, fp2) == pytest.approx(0.5)
    assert compute_tanimoto(np.zeros(5), np.zeros(5)) == 0.0

    # Test compute_target_orthogonality
    targets_a = ["JAK1 (Act)", "JAK3 (Act)"]
    targets_b = ["TYR (Act)", "MITF (Act)"]
    assert compute_target_orthogonality(targets_a, targets_b) == pytest.approx(1.0)

    targets_c = ["JAK1 (Act)", "TYR (Act)"]
    assert compute_target_orthogonality(targets_a, targets_c) == pytest.approx(2.0 / 3.0)

    assert compute_target_orthogonality([], []) == 1.0

    # Test screen_pairwise_synergy with dummy candidates json
    candidates_data = {
        "candidates": [
            {
                "drug_name": "Tofacitinib",
                "curative_triad_alignment": "Pillar 1",
                "probability": 0.85,
                "trm_disarmament_score": 2.5,
                "stem_cell_regen_score": 0.2,
                "barrier_suppression_score": 0.1,
                "matched_targets": ["JAK1", "JAK3"],
                "safety_tier": "Oral Systemic",
            },
            {
                "drug_name": "Afamelanotide",
                "curative_triad_alignment": "Pillar 2",
                "probability": 0.80,
                "trm_disarmament_score": 0.1,
                "stem_cell_regen_score": 2.8,
                "barrier_suppression_score": 0.2,
                "matched_targets": ["MC1R", "MITF"],
                "safety_tier": "Subcutaneous Implant",
            },
            {
                "drug_name": "Roflumilast",
                "curative_triad_alignment": "Pillar 3",
                "probability": 0.78,
                "trm_disarmament_score": 0.3,
                "stem_cell_regen_score": 0.4,
                "barrier_suppression_score": 2.6,
                "matched_targets": ["PDE4B", "PDE4D"],
                "safety_tier": "Topical",
            },
        ]
    }
    cand_file = tmp_path / "candidates.json"
    with open(cand_file, "w") as f:
        json.dump(candidates_data, f)

    out_json = tmp_path / "synergy.json"
    out_md = tmp_path / "synergy.md"

    results = screen_pairwise_synergy(
        top_candidates_path=cand_file,
        top_n_candidates=10,
        top_k_pairs=5,
        out_json=out_json,
        out_md=out_md,
    )

    assert len(results) > 0
    assert out_json.exists()
    assert out_md.exists()
    top = results[0]
    assert top.rank == 1
    assert top.synergy_score > 0
    assert 0.0 <= top.virtual_ci <= 1.0
    assert 0.0 <= top.target_orthogonality <= 1.0


def test_reverse_target_screening(tmp_path) -> None:
    from vitiligo.gnn.reverse_screen import run_reverse_target_screening

    dataset = _make_dummy_dataset()
    model = RelationalGNN(
        num_nodes=dataset.num_nodes,
        num_relations=dataset.num_relations,
        hidden_dim=16,
        num_layers=1,
    )

    out_json = tmp_path / "reverse_screen.json"
    out_md = tmp_path / "reverse_screen.md"

    results = run_reverse_target_screening(
        dataset=dataset,
        gnn_model=model,
        top_per_target=5,
        filter_cytotoxic=True,
        out_json=out_json,
        out_md=out_md,
    )

    assert out_json.exists()
    assert out_md.exists()
    assert len(results) > 0
    assert "INHIBITS_JAK1" in results
    assert "INHIBITS_IL15" in results
    assert "TREATS_Vitiligo" in results
    jak1_hits = results["INHIBITS_JAK1"].hits
    assert len(jak1_hits) > 0
    assert jak1_hits[0].drug_name in ["tofacitinib", "ritlecitinib"]
