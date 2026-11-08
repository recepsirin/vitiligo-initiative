"""Training and evaluation loop for Relational GNN."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
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

THEAPEUTIC_PREDICATES = frozenset({"TREATS", "INVESTIGATES", "ASSOCIATED_WITH", "INHIBITS", "ACTIVATES", "CAUSES"})


@dataclass
class EvalMetrics:
    hits_at_1: float
    hits_at_5: float
    hits_at_10: float
    mrr: float
    mean_rank: float
    sample_size: int
    median_rank: float = 0.0

    # Filtered metrics (masking known true triples as standard in KG literature)
    filtered_hits_at_1: float = 0.0
    filtered_hits_at_5: float = 0.0
    filtered_hits_at_10: float = 0.0
    filtered_mrr: float = 0.0
    filtered_mean_rank: float = 0.0
    filtered_median_rank: float = 0.0

    # Core therapeutic & discovery subset (TREATS, INVESTIGATES, ASSOCIATED_WITH, INHIBITS, ACTIVATES, CAUSES)
    therapeutic_mrr: float = 0.0
    therapeutic_hits_at_1: float = 0.0
    therapeutic_hits_at_10: float = 0.0
    therapeutic_sample_size: int = 0

    # Per-relation breakdown
    per_relation: dict[str, dict[str, Any]] = field(default_factory=dict)


@torch.no_grad()
def evaluate_link_prediction(
    model: RelationalGNN,
    dataset: GraphDataset,
    eval_edges: dict[str, torch.Tensor],
    *,
    batch_size: int = 256,
    max_eval_samples: int | None = 1000,
    all_true_dict: dict[tuple[int, int], set[int]] | None = None,
) -> EvalMetrics:
    """Evaluate raw and filtered link prediction metrics on held-out edges."""
    model.eval()
    device = model.device

    edge_index = dataset.edge_index.to(device)
    edge_type = dataset.edge_type.to(device)
    h_enc = model.encode(
        edge_index,
        edge_type,
        node_features=dataset.node_features,
        edge_weight=dataset.edge_weight,
    )

    eval_src = eval_edges["edge_index"][0]
    eval_dst = eval_edges["edge_index"][1]
    eval_rel = eval_edges["edge_type"]

    total_eval = len(eval_src)
    if max_eval_samples is not None and total_eval > max_eval_samples:
        indices = torch.randperm(total_eval)[:max_eval_samples]
        eval_src = eval_src[indices]
        eval_dst = eval_dst[indices]
        eval_rel = eval_rel[indices]

    num_samples = len(eval_src)
    if num_samples == 0:
        return EvalMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    # Precompute filter lookup if not supplied
    if all_true_dict is None:
        all_true_dict = {}
        src_l = dataset.edge_index[0].tolist()
        dst_l = dataset.edge_index[1].tolist()
        rel_l = dataset.edge_type.tolist()
        for u, v, r in zip(src_l, dst_l, rel_l, strict=False):
            all_true_dict.setdefault((u, r), set()).add(v)

    raw_ranks: list[float] = []
    filt_ranks: list[float] = []
    rel_ids: list[int] = []

    for i in range(0, num_samples, batch_size):
        b_src = eval_src[i : i + batch_size].to(device)
        b_dst = eval_dst[i : i + batch_size].to(device)
        b_rel = eval_rel[i : i + batch_size].to(device)

        # scores shape: [batch_size, num_nodes]
        scores = model.decode_all_tails(h_enc, b_src, b_rel)
        gt_scores = scores[torch.arange(len(b_src), device=device), b_dst].unsqueeze(1)

        # Raw ranks
        b_raw_ranks = (scores > gt_scores).sum(dim=1) + 1
        raw_ranks.extend(b_raw_ranks.float().cpu().tolist())

        # Filtered ranks: mask out all known true tails except ground truth
        scores_filt = scores.clone()
        for idx in range(len(b_src)):
            u_val = b_src[idx].item()
            r_val = b_rel[idx].item()
            target_v = b_dst[idx].item()
            known_tails = all_true_dict.get((u_val, r_val), set())
            for k_t in known_tails:
                if k_t != target_v:
                    scores_filt[idx, k_t] = -1e9

        b_filt_ranks = (scores_filt > gt_scores).sum(dim=1) + 1
        filt_ranks.extend(b_filt_ranks.float().cpu().tolist())
        rel_ids.extend(b_rel.cpu().tolist())

    raw_t = torch.tensor(raw_ranks)
    filt_t = torch.tensor(filt_ranks)

    mrr = float((1.0 / raw_t).mean().item())
    h1 = float((raw_t <= 1).float().mean().item())
    h5 = float((raw_t <= 5).float().mean().item())
    h10 = float((raw_t <= 10).float().mean().item())
    mr = float(raw_t.mean().item())
    med_r = float(raw_t.median().item())

    f_mrr = float((1.0 / filt_t).mean().item())
    f_h1 = float((filt_t <= 1).float().mean().item())
    f_h5 = float((filt_t <= 5).float().mean().item())
    f_h10 = float((filt_t <= 10).float().mean().item())
    f_mr = float(filt_t.mean().item())
    f_med_r = float(filt_t.median().item())

    # Per-relation breakdown
    per_rel_raw: dict[str, list[float]] = defaultdict(list)
    per_rel_filt: dict[str, list[float]] = defaultdict(list)
    for r_idx, r_val, f_val in zip(rel_ids, raw_ranks, filt_ranks, strict=False):
        r_name = dataset.idx_to_relation[r_idx] if r_idx < len(dataset.idx_to_relation) else f"rel_{r_idx}"
        per_rel_raw[r_name].append(r_val)
        per_rel_filt[r_name].append(f_val)

    per_relation_metrics: dict[str, dict[str, Any]] = {}
    ther_filt: list[float] = []

    for r_name, r_list in per_rel_raw.items():
        r_t = torch.tensor(r_list)
        f_t = torch.tensor(per_rel_filt[r_name])
        per_relation_metrics[r_name] = {
            "count": len(r_list),
            "raw_mrr": round(float((1.0 / r_t).mean().item()), 4),
            "raw_hits_at_10": round(float((r_t <= 10).float().mean().item()), 4),
            "raw_median_rank": round(float(r_t.median().item()), 1),
            "filtered_mrr": round(float((1.0 / f_t).mean().item()), 4),
            "filtered_hits_at_1": round(float((f_t <= 1).float().mean().item()), 4),
            "filtered_hits_at_10": round(float((f_t <= 10).float().mean().item()), 4),
            "filtered_median_rank": round(float(f_t.median().item()), 1),
        }
        if r_name in THEAPEUTIC_PREDICATES:
            ther_filt.extend(per_rel_filt[r_name])

    if ther_filt:
        th_t = torch.tensor(ther_filt)
        therapeutic_mrr = round(float((1.0 / th_t).mean().item()), 4)
        therapeutic_h1 = round(float((th_t <= 1).float().mean().item()), 4)
        therapeutic_h10 = round(float((th_t <= 10).float().mean().item()), 4)
        therapeutic_sample_size = len(ther_filt)
    else:
        therapeutic_mrr = f_mrr
        therapeutic_h1 = f_h1
        therapeutic_h10 = f_h10
        therapeutic_sample_size = num_samples

    return EvalMetrics(
        hits_at_1=round(h1, 4),
        hits_at_5=round(h5, 4),
        hits_at_10=round(h10, 4),
        mrr=round(mrr, 4),
        mean_rank=round(mr, 2),
        median_rank=round(med_r, 1),
        sample_size=num_samples,
        filtered_hits_at_1=round(f_h1, 4),
        filtered_hits_at_5=round(f_h5, 4),
        filtered_hits_at_10=round(f_h10, 4),
        filtered_mrr=round(f_mrr, 4),
        filtered_mean_rank=round(f_mr, 2),
        filtered_median_rank=round(f_med_r, 1),
        therapeutic_mrr=therapeutic_mrr,
        therapeutic_hits_at_1=therapeutic_h1,
        therapeutic_hits_at_10=therapeutic_h10,
        therapeutic_sample_size=therapeutic_sample_size,
        per_relation=per_relation_metrics,
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
    encoder_type: str = "rgat",
    heads: int = 4,
    decoder_type: str = "complex",
    num_neg_samples: int = 4,
    adversarial_temperature: float = 1.0,
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

    logger.info("Initializing Relational GNN on device: %s (encoder: %s, decoder: %s)", device_obj, encoder_type, decoder_type)
    train_ds, val_edges, test_edges = dataset.split_edges(val_ratio=0.1, test_ratio=0.1, seed=random_seed)

    feature_dim = dataset.node_features.size(1) if dataset.node_features is not None else None
    model = RelationalGNN(
        num_nodes=dataset.num_nodes,
        num_relations=dataset.num_relations,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        feature_dim=feature_dim,
        encoder_type=encoder_type,
        heads=heads,
        decoder_type=decoder_type,
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

    # Precompute all true triples for filtered metric ranking
    all_true_dict: dict[tuple[int, int], set[int]] = {}
    src_l = dataset.edge_index[0].tolist()
    dst_l = dataset.edge_index[1].tolist()
    rel_l = dataset.edge_type.tolist()
    for u, v, r in zip(src_l, dst_l, rel_l, strict=False):
        all_true_dict.setdefault((u, r), set()).add(v)

    best_val_mrr = 0.0
    history: list[dict[str, Any]] = []
    start_time = time.time()

    logger.info(
        "Starting training (%d epochs, %d train edges, batch_size=%d, neg_samples=%d)...",
        num_epochs,
        num_train_edges,
        batch_size,
        num_neg_samples,
    )

    for epoch in range(1, num_epochs + 1):
        model.train()
        perm = torch.randperm(num_train_edges, device=device_obj)
        epoch_losses: list[float] = []

        optimizer.zero_grad()
        # Encode full graph once per epoch using multimodal features and causal weights
        h = model.encode(
            train_edge_index,
            train_edge_type,
            node_features=train_ds.node_features,
            edge_weight=train_edge_weight,
        )
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
                num_neg_samples=num_neg_samples,
                adversarial_temperature=adversarial_temperature,
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
            val_metrics = evaluate_link_prediction(
                model,
                train_ds,
                val_edges,
                max_eval_samples=500,
                all_true_dict=all_true_dict,
            )
            logger.info(
                "Epoch %02d/%d | Loss: %.4f | Val Filt MRR: %.4f (Raw: %.4f) | Filt H@10: %.2f%% | Ther MRR: %.4f",
                epoch,
                num_epochs,
                mean_loss,
                val_metrics.filtered_mrr,
                val_metrics.mrr,
                val_metrics.filtered_hits_at_10 * 100,
                val_metrics.therapeutic_mrr,
            )
            if val_metrics.filtered_mrr > best_val_mrr:
                best_val_mrr = val_metrics.filtered_mrr
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
                        "decoder_type": model.decoder_type,
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
                "val_filtered_mrr": val_metrics.filtered_mrr if val_metrics else None,
                "val_filtered_hits10": val_metrics.filtered_hits_at_10 if val_metrics else None,
                "val_therapeutic_mrr": val_metrics.therapeutic_mrr if val_metrics else None,
                "val_raw_mrr": val_metrics.mrr if val_metrics else None,
            }
        )

    # Final evaluation on held-out test edges
    logger.info("Evaluating final model on full held-out test edges...")
    test_metrics = evaluate_link_prediction(
        model,
        train_ds,
        test_edges,
        max_eval_samples=None,
        all_true_dict=all_true_dict,
    )
    total_time = round(time.time() - start_time, 2)

    report = {
        "model_type": f"RelationalGNN (FastRGCN + {model.decoder_type.capitalize()})",
        "decoder_type": model.decoder_type,
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
        "GNN Training complete in %.1fs: Test Filt MRR=%.4f (Raw=%.4f), Filt Hits@10=%.2f%%, Ther MRR=%.4f (saved to %s)",
        total_time,
        test_metrics.filtered_mrr,
        test_metrics.mrr,
        test_metrics.filtered_hits_at_10 * 100,
        test_metrics.therapeutic_mrr,
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

    decoder_type = data.get("decoder_type", "distmult")

    model = RelationalGNN(
        num_nodes=data["num_nodes"],
        num_relations=data["num_relations"],
        hidden_dim=data["hidden_dim"],
        num_layers=data["num_layers"],
        feature_dim=feature_dim,
        decoder_type=decoder_type,
    ).to(device_obj)
    model.load_state_dict(state_dict)
    model.eval()
    return model
