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

THEAPEUTIC_PREDICATES = frozenset(
    {
        "TREATS",
        "INVESTIGATES",
        "ASSOCIATED_WITH",
        "INHIBITS",
        "ACTIVATES",
        "PARTICIPATES_IN",
        "EXPRESSED_IN",
        "CAUSES",
    }
)


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

    # Type-constrained filtered metrics (ranking within valid domain/range EntityKind)
    type_constrained_mrr: float = 0.0
    type_constrained_hits_at_1: float = 0.0
    type_constrained_hits_at_10: float = 0.0
    type_constrained_median_rank: float = 0.0

    # Core therapeutic & mechanistic subset
    therapeutic_mrr: float = 0.0
    therapeutic_hits_at_1: float = 0.0
    therapeutic_hits_at_10: float = 0.0
    therapeutic_sample_size: int = 0

    # Per-relation breakdown
    per_relation: dict[str, dict[str, Any]] = field(default_factory=dict)


def build_type_sampler(dataset: GraphDataset, device: torch.device) -> dict[str, torch.Tensor]:
    """Build vectorized lookup tensors for O(1) domain/type-constrained negative sampling."""
    num_nodes = dataset.num_nodes
    node_to_kind = torch.zeros(num_nodes, dtype=torch.long, device=device)
    sorted_nodes_list: list[int] = []
    kind_offsets_list: list[int] = []
    kind_counts_list: list[int] = []

    offset = 0
    for k_idx, (_kind_name, indices) in enumerate(sorted(dataset.kind_to_indices.items())):
        for n_idx in indices:
            node_to_kind[n_idx] = k_idx
        sorted_nodes_list.extend(indices)
        kind_offsets_list.append(offset)
        kind_counts_list.append(len(indices))
        offset += len(indices)

    return {
        "node_to_kind": node_to_kind,
        "sorted_nodes": torch.tensor(sorted_nodes_list, dtype=torch.long, device=device),
        "kind_offsets": torch.tensor(kind_offsets_list, dtype=torch.long, device=device),
        "kind_counts": torch.tensor(kind_counts_list, dtype=torch.long, device=device),
    }


@torch.no_grad()
def evaluate_link_prediction(
    model: RelationalGNN,
    dataset: GraphDataset,
    eval_edges: dict[str, torch.Tensor],
    *,
    batch_size: int = 256,
    max_eval_samples: int | None = 1000,
    all_true_dict: dict[tuple[int, int], set[int]] | None = None,
    all_true_heads_dict: dict[tuple[int, int], set[int]] | None = None,
) -> EvalMetrics:
    """Evaluate raw, filtered, and type-constrained link prediction metrics on held-out edges.

    For edges pointing into the global disease hub ('vitiligo'), evaluates head prediction (?, r, vitiligo)
    rather than trivial tail prediction (h, r, vitiligo) to avoid hub-memorization inflation.
    """
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
        gen = torch.Generator().manual_seed(42)
        indices = torch.randperm(total_eval, generator=gen)[:max_eval_samples]
        eval_src = eval_src[indices]
        eval_dst = eval_dst[indices]
        eval_rel = eval_rel[indices]

    num_samples = len(eval_src)
    if num_samples == 0:
        return EvalMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    # Precompute filter lookups if not supplied
    if all_true_dict is None or all_true_heads_dict is None:
        all_true_dict = {}
        all_true_heads_dict = {}
        src_l = dataset.edge_index[0].tolist()
        dst_l = dataset.edge_index[1].tolist()
        rel_l = dataset.edge_type.tolist()
        for u, v, r in zip(src_l, dst_l, rel_l, strict=False):
            all_true_dict.setdefault((u, r), set()).add(v)
            all_true_heads_dict.setdefault((r, v), set()).add(u)

    # Precompute kind masks on device for fast type-constrained ranking
    kind_masks: dict[str, torch.Tensor] = {}
    for kind_name, idx_list in dataset.kind_to_indices.items():
        m = torch.zeros(dataset.num_nodes, dtype=torch.bool, device=device)
        m[idx_list] = True
        kind_masks[kind_name] = m

    raw_ranks: list[float] = []
    filt_ranks: list[float] = []
    typed_ranks: list[float] = []
    rel_ids: list[int] = []

    for i in range(0, num_samples, batch_size):
        b_src = eval_src[i : i + batch_size].to(device)
        b_dst = eval_dst[i : i + batch_size].to(device)
        b_rel = eval_rel[i : i + batch_size].to(device)

        tail_scores = model.decode_all_tails(h_enc, b_src, b_rel)

        for idx in range(len(b_src)):
            u_val = int(b_src[idx].item())
            v_val = int(b_dst[idx].item())
            r_val = int(b_rel[idx].item())

            row_scores = tail_scores[idx]
            gt_score = row_scores[v_val]
            target_idx = v_val
            target_kind = dataset.entities[v_val].kind
            known_set = all_true_dict.get((u_val, r_val), set())

            raw_r = int((row_scores > gt_score).sum().item()) + 1
            raw_ranks.append(float(raw_r))

            scores_filt = row_scores.clone()
            for k_node in known_set:
                if k_node != target_idx:
                    scores_filt[k_node] = -1e9

            filt_r = int((scores_filt > gt_score).sum().item()) + 1
            filt_ranks.append(float(filt_r))

            # Type-constrained filtered rank (rank only among candidates of target_kind)
            k_mask = kind_masks.get(target_kind)
            if k_mask is not None:
                typed_r = int((scores_filt[k_mask] > gt_score).sum().item()) + 1
            else:
                typed_r = filt_r
            typed_ranks.append(float(typed_r))
            rel_ids.append(r_val)

    raw_t = torch.tensor(raw_ranks)
    filt_t = torch.tensor(filt_ranks)
    typed_t = torch.tensor(typed_ranks)

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

    tc_mrr = float((1.0 / typed_t).mean().item())
    tc_h1 = float((typed_t <= 1).float().mean().item())
    tc_h10 = float((typed_t <= 10).float().mean().item())
    tc_med_r = float(typed_t.median().item())

    # Per-relation breakdown
    per_rel_raw: dict[str, list[float]] = defaultdict(list)
    per_rel_filt: dict[str, list[float]] = defaultdict(list)
    per_rel_typed: dict[str, list[float]] = defaultdict(list)
    for r_idx, r_val, f_val, t_val in zip(
        rel_ids, raw_ranks, filt_ranks, typed_ranks, strict=False
    ):
        r_name = (
            dataset.idx_to_relation[r_idx]
            if r_idx < len(dataset.idx_to_relation)
            else f"rel_{r_idx}"
        )
        per_rel_raw[r_name].append(r_val)
        per_rel_filt[r_name].append(f_val)
        per_rel_typed[r_name].append(t_val)

    per_relation_metrics: dict[str, dict[str, Any]] = {}
    ther_typed: list[float] = []

    for r_name, r_list in per_rel_raw.items():
        r_t = torch.tensor(r_list)
        f_t = torch.tensor(per_rel_filt[r_name])
        t_t = torch.tensor(per_rel_typed[r_name])
        per_relation_metrics[r_name] = {
            "count": len(r_list),
            "raw_mrr": round(float((1.0 / r_t).mean().item()), 4),
            "raw_hits_at_10": round(float((r_t <= 10).float().mean().item()), 4),
            "raw_median_rank": round(float(r_t.median().item()), 1),
            "filtered_mrr": round(float((1.0 / f_t).mean().item()), 4),
            "filtered_hits_at_1": round(float((f_t <= 1).float().mean().item()), 4),
            "filtered_hits_at_10": round(float((f_t <= 10).float().mean().item()), 4),
            "filtered_median_rank": round(float(f_t.median().item()), 1),
            "type_constrained_mrr": round(float((1.0 / t_t).mean().item()), 4),
            "type_constrained_hits_at_10": round(float((t_t <= 10).float().mean().item()), 4),
            "type_constrained_median_rank": round(float(t_t.median().item()), 1),
        }
        if r_name in THEAPEUTIC_PREDICATES:
            ther_typed.extend(per_rel_typed[r_name])

    if ther_typed:
        th_t = torch.tensor(ther_typed)
        therapeutic_mrr = round(float((1.0 / th_t).mean().item()), 4)
        therapeutic_h1 = round(float((th_t <= 1).float().mean().item()), 4)
        therapeutic_h10 = round(float((th_t <= 10).float().mean().item()), 4)
        therapeutic_sample_size = len(ther_typed)
    else:
        therapeutic_mrr = tc_mrr
        therapeutic_h1 = tc_h1
        therapeutic_h10 = tc_h10
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
        type_constrained_mrr=round(tc_mrr, 4),
        type_constrained_hits_at_1=round(tc_h1, 4),
        type_constrained_hits_at_10=round(tc_h10, 4),
        type_constrained_median_rank=round(tc_med_r, 1),
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
    """Train the Relational GNN with relation-balanced causal loss and type-constrained negative sampling."""
    torch.manual_seed(random_seed)
    if dataset is None:
        dataset = load_graph_dataset()

    if device is None:
        device_obj = torch.device(
            "mps"
            if torch.backends.mps.is_available()
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
    else:
        device_obj = torch.device(device)

    logger.info(
        "Initializing Relational GNN on device: %s (encoder: %s, decoder: %s)",
        device_obj,
        encoder_type,
        decoder_type,
    )
    train_ds, val_edges, test_edges = dataset.split_edges(
        val_ratio=0.1, test_ratio=0.1, seed=random_seed
    )

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

    # Compute mild relation-balanced loss weights so CHANGES does not swamp mechanism edges
    rel_counts = (
        torch.bincount(train_edge_type, minlength=dataset.num_relations).float().clamp(min=1.0)
    )
    rel_inv_weights = rel_counts**-0.20
    changes_rel_idx = dataset.relation_to_idx.get("CHANGES")
    if changes_rel_idx is not None and changes_rel_idx < len(rel_inv_weights):
        rel_inv_weights[changes_rel_idx] *= 0.40
    edge_rel_scale = rel_inv_weights[train_edge_type]
    edge_rel_scale = edge_rel_scale / edge_rel_scale.mean().clamp(min=1e-6)
    balanced_loss_weights = (train_edge_weight * edge_rel_scale).clamp(min=0.10, max=2.5)

    # Degree-weighted negative sampling distribution (p(v) ~ deg(v)^0.75)
    dst_degrees = torch.bincount(train_edge_index[1], minlength=dataset.num_nodes).float()
    sampling_weights = (dst_degrees**0.75).clamp(min=1.0)
    sampling_weights = (sampling_weights / sampling_weights.sum()).to(device_obj)

    # Vectorized type-constrained negative sampler
    type_sampler = build_type_sampler(dataset, device_obj)

    # Precompute all true triples for filtered metric ranking (both tail and head)
    all_true_dict: dict[tuple[int, int], set[int]] = {}
    all_true_heads_dict: dict[tuple[int, int], set[int]] = {}
    src_l = dataset.edge_index[0].tolist()
    dst_l = dataset.edge_index[1].tolist()
    rel_l = dataset.edge_type.tolist()
    for u, v, r in zip(src_l, dst_l, rel_l, strict=False):
        all_true_dict.setdefault((u, r), set()).add(v)
        all_true_heads_dict.setdefault((r, v), set()).add(u)

    best_val_mrr = -1.0
    save_path_obj = Path(save_path)
    save_path_obj.parent.mkdir(parents=True, exist_ok=True)
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
        step_size = max(batch_size, 18500)

        for i in range(0, num_train_edges, step_size):
            batch_idx = perm[i : i + step_size]
            b_src = train_edge_index[0, batch_idx]
            b_dst = train_edge_index[1, batch_idx]
            b_rel = train_edge_type[batch_idx]
            b_w = balanced_loss_weights[batch_idx]

            optimizer.zero_grad()
            h = model.encode(
                train_edge_index,
                train_edge_type,
                node_features=train_ds.node_features,
                edge_weight=train_edge_weight,
            )
            batch_loss = model.compute_loss(
                h,
                b_src,
                b_rel,
                b_dst,
                edge_weights=b_w,
                sampling_weights=sampling_weights,
                num_neg_samples=num_neg_samples,
                adversarial_temperature=adversarial_temperature,
                type_sampler=type_sampler,
            )
            batch_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_losses.append(float(batch_loss.item()))

        scheduler.step()
        mean_loss = float(sum(epoch_losses) / max(len(epoch_losses), 1))

        # Validation check every 5 epochs or last epoch
        val_metrics: EvalMetrics | None = None
        if epoch % 5 == 0 or epoch == num_epochs:
            val_metrics = evaluate_link_prediction(
                model,
                train_ds,
                val_edges,
                max_eval_samples=600,
                all_true_dict=all_true_dict,
                all_true_heads_dict=all_true_heads_dict,
            )
            logger.info(
                "Epoch %02d/%d | Loss: %.4f | Val Typed MRR: %.4f (Filt: %.4f) | Typed H@10: %.2f%% | Ther MRR: %.4f",
                epoch,
                num_epochs,
                mean_loss,
                val_metrics.type_constrained_mrr,
                val_metrics.filtered_mrr,
                val_metrics.type_constrained_hits_at_10 * 100,
                val_metrics.therapeutic_mrr,
            )
            if val_metrics.filtered_mrr > best_val_mrr:
                best_val_mrr = val_metrics.filtered_mrr
                torch.save(
                    {
                        "model_state_dict": model.state_dict(),
                        "hidden_dim": hidden_dim,
                        "num_layers": num_layers,
                        "num_nodes": dataset.num_nodes,
                        "num_relations": dataset.num_relations,
                        "feature_dim": feature_dim,
                        "encoder_type": model.encoder_type,
                        "heads": model.heads,
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
                "val_type_constrained_mrr": val_metrics.type_constrained_mrr
                if val_metrics
                else None,
                "val_filtered_hits10": val_metrics.filtered_hits_at_10 if val_metrics else None,
                "val_type_constrained_hits10": (
                    val_metrics.type_constrained_hits_at_10 if val_metrics else None
                ),
                "val_therapeutic_mrr": val_metrics.therapeutic_mrr if val_metrics else None,
                "val_raw_mrr": val_metrics.mrr if val_metrics else None,
            }
        )

    # Reload best validation checkpoint before final held-out test evaluation
    if save_path_obj.exists():
        best_ckpt = torch.load(save_path_obj, map_location=device_obj, weights_only=False)
        model.load_state_dict(best_ckpt["model_state_dict"])

    logger.info("Evaluating best validation model on full held-out test edges...")
    test_metrics = evaluate_link_prediction(
        model,
        train_ds,
        test_edges,
        max_eval_samples=None,
        all_true_dict=all_true_dict,
        all_true_heads_dict=all_true_heads_dict,
    )
    total_time = round(time.time() - start_time, 2)

    enc_label = f"RGAT-{model.heads}H" if model.encoder_type == "rgat" else "FastRGCN"
    report = {
        "model_type": f"RelationalGNN ({enc_label} + {model.decoder_type.capitalize()})",
        "encoder_type": model.encoder_type,
        "heads": model.heads,
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
        "GNN Training complete in %.1fs: Test Typed MRR=%.4f (Filt=%.4f), Typed Hits@10=%.2f%%, Ther MRR=%.4f (saved to %s)",
        total_time,
        test_metrics.type_constrained_mrr,
        test_metrics.filtered_mrr,
        test_metrics.type_constrained_hits_at_10 * 100,
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
            "mps"
            if torch.backends.mps.is_available()
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
    else:
        device_obj = torch.device(device)

    data = torch.load(checkpoint_path, map_location=device_obj, weights_only=False)
    state_dict = data["model_state_dict"]
    feature_dim = data.get("feature_dim")
    if feature_dim is None and "node_proj.0.weight" in state_dict:
        feature_dim = state_dict["node_proj.0.weight"].size(1)

    encoder_type = data.get("encoder_type")
    if encoder_type is None:
        encoder_type = "rgat" if "convs.0.lin_src.weight" in state_dict else "rgcn"
    heads = int(data.get("heads", 4))
    decoder_type = data.get("decoder_type", "distmult")

    model = RelationalGNN(
        num_nodes=data["num_nodes"],
        num_relations=data["num_relations"],
        hidden_dim=data["hidden_dim"],
        num_layers=data["num_layers"],
        feature_dim=feature_dim,
        encoder_type=encoder_type,
        heads=heads,
        decoder_type=decoder_type,
    ).to(device_obj)
    model.load_state_dict(state_dict)
    model.eval()
    return model
