"""Unit tests for the Relational GNN dataset, architecture, and screening engine."""

from __future__ import annotations

import torch

from vitiligo.gnn.dataset import (
    EntityMeta,
    GraphDataset,
    compute_causal_edge_weight,
)
from vitiligo.gnn.model import RelationalGNN


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
        == 0.30
    )
    assert compute_causal_edge_weight("ASSERTED", None, 0.88, predicate="TREATS") >= 0.75
    assert compute_causal_edge_weight("ASSERTED", None, 0.84, predicate="INHIBITS") >= 0.70


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
    from vitiligo.gnn.train import evaluate_link_prediction

    ds = _make_dummy_dataset()
    model = RelationalGNN(
        num_nodes=ds.num_nodes, num_relations=ds.num_relations, hidden_dim=16, num_layers=1
    )
    eval_edges = {
        "edge_index": ds.edge_index,
        "edge_type": ds.edge_type,
    }
    metrics = evaluate_link_prediction(model, ds, eval_edges, max_eval_samples=None)

    assert metrics.sample_size == ds.num_edges
    assert 0.0 <= metrics.mrr <= 1.0
    assert 0.0 <= metrics.filtered_mrr <= 1.0
    assert 0.0 <= metrics.therapeutic_mrr <= 1.0
    assert len(metrics.per_relation) > 0
    assert "TREATS" in metrics.per_relation


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
