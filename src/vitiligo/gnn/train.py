"""Training and evaluation loop for Relational GNN."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from vitiligo.gnn.dataset import GraphDataset, load_graph_dataset
from vitiligo.gnn.model import RelationalGNN
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL_PATH = Path("data/models/gnn/relational_gnn.pt")
DEFAULT_REPORT_PATH = Path("exports/gnn_train_results.json")


@dataclass
class EvalMetrics:
    hits_at_1: float
    hits_at_5: float
    hits_at_10: float
    mrr: float
    mean_rank: float
    sample_size: int


@torch.no_grad()
def evaluate_link_prediction(
    model: RelationalGNN,
    dataset: GraphDataset,
    eval_edges: dict[str, torch.Tensor],
    *,
    batch_size: int = 256,
    max_eval_samples: int = 1000,
) -> EvalMetrics:
    """Evaluate link prediction metrics (Hits@1, 5, 10, MRR, Mean Rank) on held-out edges."""
    model.eval()
    device = model.device

    edge_index = dataset.edge_index.to(device)
    edge_type = dataset.edge_type.to(device)
    h_enc = model.encode(edge_index, edge_type, node_features=dataset.node_features)

    eval_src = eval_edges["edge_index"][0]
    eval_dst = eval_edges["edge_index"][1]
    eval_rel = eval_edges["edge_type"]

    total_eval = len(eval_src)
    if total_eval > max_eval_samples:
        indices = torch.randperm(total_eval)[:max_eval_samples]
        eval_src = eval_src[indices]
        eval_dst = eval_dst[indices]
        eval_rel = eval_rel[indices]

    ranks: list[float] = []
    num_samples = len(eval_src)

    for i in range(0, num_samples, batch_size):
        b_src = eval_src[i : i + batch_size].to(device)
        b_dst = eval_dst[i : i + batch_size].to(device)
        b_rel = eval_rel[i : i + batch_size].to(device)

        # scores shape: [batch_size, num_nodes]
        scores = model.decode_all_tails(h_enc, b_src, b_rel)
        gt_scores = scores[torch.arange(len(b_src), device=device), b_dst].unsqueeze(1)

        # Rank = count of entities scoring higher than true tail + 1
        b_ranks = (scores > gt_scores).sum(dim=1) + 1
        ranks.extend(b_ranks.float().cpu().tolist())

    ranks_t = torch.tensor(ranks)
    mrr = float((1.0 / ranks_t).mean().item())
    h1 = float((ranks_t <= 1).float().mean().item())
    h5 = float((ranks_t <= 5).float().mean().item())
    h10 = float((ranks_t <= 10).float().mean().item())
    mr = float(ranks_t.mean().item())

    return EvalMetrics(
        hits_at_1=round(h1, 4),
        hits_at_5=round(h5, 4),
        hits_at_10=round(h10, 4),
        mrr=round(mrr, 4),
        mean_rank=round(mr, 2),
        sample_size=num_samples,
    )


def train_relational_gnn(
    dataset: GraphDataset | None = None,
    *,
    num_epochs: int = 30,
    lr: float = 0.005,
    hidden_dim: int = 128,
    num_layers: int = 2,
    batch_size: int = 4096,
    weight_decay: float = 1e-4,
    device: str | None = None,
    save_path: Path | str = DEFAULT_MODEL_PATH,
    report_path: Path | str = DEFAULT_REPORT_PATH,
    random_seed: int = 42,
) -> tuple[RelationalGNN, dict[str, Any]]:
    """Train the Relational GNN with causal-weighted message passing and evaluation."""
    torch.manual_seed(random_seed)
    if dataset is None:
        dataset = load_graph_dataset()

    if device is None:
        device_obj = torch.device(
            "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        )
    else:
        device_obj = torch.device(device)

    logger.info("Initializing Relational GNN on device: %s", device_obj)
    train_ds, val_edges, test_edges = dataset.split_edges(val_ratio=0.1, test_ratio=0.1, seed=random_seed)

    feature_dim = dataset.node_features.size(1) if dataset.node_features is not None else None
    model = RelationalGNN(
        num_nodes=dataset.num_nodes,
        num_relations=dataset.num_relations,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        feature_dim=feature_dim,
    ).to(device_obj)

    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=num_epochs, eta_min=lr * 0.1)

    train_edge_index = train_ds.edge_index.to(device_obj)
    train_edge_type = train_ds.edge_type.to(device_obj)
    train_edge_weight = train_ds.edge_weight.to(device_obj)
    num_train_edges = train_ds.num_edges

    # Degree-weighted negative sampling distribution (p(v) ~ deg(v)^0.75) to combat hub bias
    dst_degrees = torch.bincount(train_edge_index[1], minlength=dataset.num_nodes).float()
    sampling_weights = (dst_degrees**0.75).clamp(min=1.0)
    sampling_weights = (sampling_weights / sampling_weights.sum()).to(device_obj)

    best_val_mrr = 0.0
    history: list[dict[str, Any]] = []
    start_time = time.time()

    logger.info(
        "Starting training (%d epochs, %d train edges, batch_size=%d)...",
        num_epochs,
        num_train_edges,
        batch_size,
    )

    for epoch in range(1, num_epochs + 1):
        model.train()
        perm = torch.randperm(num_train_edges, device=device_obj)
        epoch_losses: list[float] = []

        optimizer.zero_grad()
        # Encode full graph once per epoch using multimodal features
        h = model.encode(train_edge_index, train_edge_type, node_features=train_ds.node_features)
        total_epoch_loss = torch.tensor(0.0, device=device_obj)

        for i in range(0, num_train_edges, batch_size):
            batch_idx = perm[i : i + batch_size]
            b_src = train_edge_index[0, batch_idx]
            b_dst = train_edge_index[1, batch_idx]
            b_rel = train_edge_type[batch_idx]
            b_w = train_edge_weight[batch_idx]

            batch_loss = model.compute_loss(
                h,
                b_src,
                b_rel,
                b_dst,
                edge_weights=b_w,
                sampling_weights=sampling_weights,
            )
            weight_factor = len(batch_idx) / num_train_edges
            total_epoch_loss = total_epoch_loss + batch_loss * weight_factor
            epoch_losses.append(float(batch_loss.item()))

        total_epoch_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        mean_loss = float(total_epoch_loss.item())

        # Validation check every 5 epochs or last epoch
        val_metrics: EvalMetrics | None = None
        if epoch % 5 == 0 or epoch == num_epochs:
            val_metrics = evaluate_link_prediction(model, dataset, val_edges, max_eval_samples=500)
            logger.info(
                "Epoch %02d/%d | Loss: %.4f | Val MRR: %.4f | Val Hits@10: %.4f",
                epoch,
                num_epochs,
                mean_loss,
                val_metrics.mrr,
                val_metrics.hits_at_10,
            )
            if val_metrics.mrr > best_val_mrr:
                best_val_mrr = val_metrics.mrr
                save_path_obj = Path(save_path)
                save_path_obj.parent.mkdir(parents=True, exist_ok=True)
                torch.save(
                    {
                        "model_state_dict": model.state_dict(),
                        "hidden_dim": hidden_dim,
                        "num_layers": num_layers,
                        "num_nodes": dataset.num_nodes,
                        "num_relations": dataset.num_relations,
                        "feature_dim": feature_dim,
                        "best_val_mrr": best_val_mrr,
                    },
                    save_path_obj,
                )
        else:
            logger.info("Epoch %02d/%d | Loss: %.4f", epoch, num_epochs, mean_loss)

        history.append(
            {
                "epoch": epoch,
                "loss": round(mean_loss, 4),
                "val_mrr": val_metrics.mrr if val_metrics else None,
                "val_hits10": val_metrics.hits_at_10 if val_metrics else None,
            }
        )

    # Final evaluation on held-out test edges
    logger.info("Evaluating final model on held-out test edges...")
    test_metrics = evaluate_link_prediction(model, dataset, test_edges, max_eval_samples=1000)
    total_time = round(time.time() - start_time, 2)

    report = {
        "model_type": "RelationalGNN (FastRGCN + DistMult)",
        "num_nodes": dataset.num_nodes,
        "num_relations": dataset.num_relations,
        "num_train_edges": num_train_edges,
        "training_time_seconds": total_time,
        "best_val_mrr": best_val_mrr,
        "test_metrics": asdict(test_metrics),
        "history": history,
    }

    report_path_obj = Path(report_path)
    report_path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path_obj, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(
        "GNN Training complete in %.1fs: Test Hits@10=%.4f, Test MRR=%.4f (saved to %s)",
        total_time,
        test_metrics.hits_at_10,
        test_metrics.mrr,
        report_path_obj,
    )
    return model, report


def load_trained_gnn(
    checkpoint_path: Path | str = DEFAULT_MODEL_PATH,
    device: str | None = None,
) -> RelationalGNN:
    """Load a trained Relational GNN from checkpoint."""
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint {checkpoint_path} not found. Run training first.")

    if device is None:
        device_obj = torch.device(
            "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        )
    else:
        device_obj = torch.device(device)

    data = torch.load(checkpoint_path, map_location=device_obj, weights_only=False)
    state_dict = data["model_state_dict"]
    feature_dim = data.get("feature_dim")
    if feature_dim is None and "node_proj.0.weight" in state_dict:
        feature_dim = state_dict["node_proj.0.weight"].size(1)

    model = RelationalGNN(
        num_nodes=data["num_nodes"],
        num_relations=data["num_relations"],
        hidden_dim=data["hidden_dim"],
        num_layers=data["num_layers"],
        feature_dim=feature_dim,
    ).to(device_obj)
    model.load_state_dict(state_dict)
    model.eval()
    return model
