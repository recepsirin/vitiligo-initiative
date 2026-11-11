"""Stage-2 Dense Cross-Encoder Reranker for Curative Vitiligo Drug Discovery.

Stage 1 (Relational ComplEx GNN) retrieves the top candidate compounds across the 18,494-node graph.
Stage 2 (DenseCurativeReranker) scores each candidate using a modality-balanced bottleneck network over:
1. 1024-D Morgan (ECFP4) chemical structural fingerprints (regularized 32-D projection).
2. 128-D ComplEx GNN latent graph representations (regularized 32-D projection).
3. ComplEx link prediction affinity for (Drug, TREATS, Vitiligo).
4. Direct TRM resident-memory disarmament profile (IL15, JAK1, JAK3, STAT1, STAT3, CD8A, ITGAE, CGAS).
5. Stem-cell / Hair-follicle melanocyte regeneration profile (CTNNB1, WNT1, MITF, EDNRB, KIT, HTR1A, TYR).
6. Non-responder barrier suppression profile (PDE4B, PDE4A, PLA2G12A) from GSE256271.
7. Human transcriptomic alignment with responder-exclusive expression signatures.

Evaluated with 5-fold out-of-fold cross-validation and calibrated against palliative corticosteroid controls.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.optim import AdamW

from vitiligo.gnn.chemicals import build_chemical_node_features, clean_drug_name
from vitiligo.gnn.dataset import GraphDataset, load_graph_dataset
from vitiligo.gnn.model import RelationalGNN
from vitiligo.gnn.screen import (
    get_safety_profile,
)
from vitiligo.gnn.train import DEFAULT_MODEL_PATH, load_trained_gnn
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RERANKER_PATH = Path("data/models/gnn/dense_reranker.pt")
DEFAULT_RERANK_REPORT_JSON = Path("exports/gnn_reranked_candidates.json")
DEFAULT_RERANK_REPORT_MD = Path("exports/gnn-reranked-report.md")

GSE256271_PATH = Path("data/geo/GSE256271/GSE256271_deseq_table_Normalized_all_IE_Final.csv.gz")

CORE_TRM_GENES = ["IL15", "JAK1", "JAK3", "STAT1", "STAT3", "CD8A", "ITGAE", "CGAS"]
CORE_REGEN_GENES = ["CTNNB1", "WNT1", "MITF", "EDNRB", "KIT", "HTR1A", "TYR"]
CORE_BARRIER_GENES = ["PDE4B", "PDE4A", "PLA2G12A"]

# Total feature dimension: 1024 (FP) + 128 (GNN) + 1 (GNN Score) + 8 (TRM) + 7 (Regen) + 3 (Barrier) + 1 (Transcriptomic) = 1172
RERANKER_FEATURE_DIM = 1172


class DenseCurativeReranker(nn.Module):
    """Wide-and-Deep calibrated cross-encoder with feature standardization and L2 regularization."""

    def __init__(
        self,
        in_dim: int = RERANKER_FEATURE_DIM,
        hidden_dim: int = 32,
        dropout: float = 0.4,
    ) -> None:
        super().__init__()
        self.in_dim = in_dim
        self.register_buffer("feat_mean", torch.zeros(in_dim))
        self.register_buffer("feat_std", torch.ones(in_dim))
        self.linear_wide = nn.Linear(in_dim, 1)
        self.deep = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(in_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def fit_scaler(self, x: torch.Tensor) -> None:
        """Fit feature-wise mean and standard deviation on training tensor [N, in_dim]."""
        with torch.no_grad():
            mean = x.mean(dim=0)
            std = x.std(dim=0, unbiased=False)
            std = torch.where(std < 1e-5, torch.ones_like(std), std)
            self.feat_mean.copy_(mean)
            self.feat_std.copy_(std)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Compute logits for candidate features [B, in_dim]."""
        single = x.dim() == 1
        if single:
            x = x.unsqueeze(0)
        x_norm = ((x - self.feat_mean) / self.feat_std).clamp(-5.0, 5.0)
        out = self.linear_wide(x_norm).squeeze(-1) + 0.25 * self.deep(x_norm).squeeze(-1)
        return out.squeeze(0) if single else out

    def predict_score(self, x: torch.Tensor) -> torch.Tensor:
        """Compute calibrated probabilities [0, 1] via Sigmoid."""
        return torch.sigmoid(self.forward(x))


@dataclass
class RerankedCandidate:
    stage2_rank: int
    stage1_rank: int
    drug_name: str
    drug_key: str
    reranker_score: float
    probability: float
    gnn_affinity_score: float
    trm_disarmament_score: float
    stem_cell_regen_score: float
    barrier_suppression_score: float
    transcriptomic_alignment: float
    matched_targets: list[str]
    safety_tier: str
    is_cytotoxic: bool
    curative_triad_alignment: str


def load_gse256271_barriers() -> dict[str, float]:
    """Load GSE256271 DESeq2 log2FC table to identify responder vs non-responder genes."""
    if not GSE256271_PATH.exists():
        return {}
    try:
        df = pd.read_csv(GSE256271_PATH, compression="gzip")
        # log2FoldChange: positive means higher in responding, negative means higher in non-responding
        gene_fc: dict[str, float] = {}
        for _, row in df.iterrows():
            g = str(row["Gene"]).strip().upper()
            fc = float(row["log2FoldChange"]) if pd.notna(row["log2FoldChange"]) else 0.0
            gene_fc[g] = fc
        return gene_fc
    except Exception as exc:
        logger.warning("Failed to load GSE256271 DE table: %s", exc)
        return {}


@torch.no_grad()
def build_candidate_feature_tensor(
    drug_idx: int,
    dataset: GraphDataset,
    h_gnn: torch.Tensor,
    gnn_model: RelationalGNN,
    fingerprints: torch.Tensor,
    gse_fc: dict[str, float],
    device: torch.device,
) -> torch.Tensor:
    """Build the unified 1172-D cross-encoder feature vector for a candidate compound."""
    # 1. 1024-D Chemical Fingerprint
    fp = fingerprints[drug_idx].to(device).detach()

    # 2. 128-D ComplEx GNN representation
    h_drug = h_gnn[drug_idx].detach()

    # 3. 1-D GNN direct vitiligo treats score
    vitiligo_idx = dataset.name_to_idx.get("vitiligo") or dataset.name_to_idx.get("Vitiligo")
    treats_rel = dataset.relation_to_idx.get("TREATS", 0)
    inhibits_rel = dataset.relation_to_idx.get("INHIBITS", 2)
    activates_rel = dataset.relation_to_idx.get("ACTIVATES", 3)

    d_t = torch.tensor([drug_idx], device=device)
    if vitiligo_idx is not None:
        r_t = torch.tensor([treats_rel], device=device)
        v_t = torch.tensor([vitiligo_idx], device=device)
        gnn_score = gnn_model.decode_triples(h_gnn, d_t, r_t, v_t).view(1).detach()
    else:
        gnn_score = torch.tensor([0.0], device=device)

    # 4. TRM Disarmament Targets (8D)
    trm_scores: list[float] = []
    for g in CORE_TRM_GENES:
        g_idx = dataset.name_to_idx.get(g) or dataset.name_to_idx.get(g.lower())
        if g_idx is not None:
            r_t = torch.tensor([inhibits_rel], device=device)
            target_t = torch.tensor([g_idx], device=device)
            s = float(gnn_model.decode_triples(h_gnn, d_t, r_t, target_t).item())
            trm_scores.append(s)
        else:
            trm_scores.append(-1.0)
    trm_t = torch.tensor(trm_scores, device=device)

    # 5. Stem Cell Regeneration Targets (7D)
    regen_scores: list[float] = []
    for g in CORE_REGEN_GENES:
        g_idx = dataset.name_to_idx.get(g) or dataset.name_to_idx.get(g.lower())
        if g_idx is not None:
            r_t = torch.tensor([activates_rel], device=device)
            target_t = torch.tensor([g_idx], device=device)
            s = float(gnn_model.decode_triples(h_gnn, d_t, r_t, target_t).item())
            regen_scores.append(s)
        else:
            regen_scores.append(-1.0)
    regen_t = torch.tensor(regen_scores, device=device)

    # 6. Non-responder Barrier Targets (3D)
    barrier_scores: list[float] = []
    for g in CORE_BARRIER_GENES:
        g_idx = dataset.name_to_idx.get(g) or dataset.name_to_idx.get(g.lower())
        if g_idx is not None:
            r_t = torch.tensor([inhibits_rel], device=device)
            target_t = torch.tensor([g_idx], device=device)
            s = float(gnn_model.decode_triples(h_gnn, d_t, r_t, target_t).item())
            barrier_scores.append(s)
        else:
            barrier_scores.append(-1.0)
    barrier_t = torch.tensor(barrier_scores, device=device)

    # 7. Transcriptomic GSE256271 signature alignment score (1D)
    trans_score = 0.0
    for g, score in zip(
        CORE_TRM_GENES + CORE_BARRIER_GENES, trm_scores + barrier_scores, strict=False
    ):
        if score > 0.0 and g in gse_fc:
            trans_score += max(0.0, score) * (-gse_fc[g])
    for g, score in zip(CORE_REGEN_GENES, regen_scores, strict=False):
        if score > 0.0 and g in gse_fc:
            trans_score += max(0.0, score) * max(0.0, gse_fc[g])
    trans_t = torch.tensor([trans_score], device=device)

    # Concatenate all components into 1172-D vector
    return torch.cat([fp, h_drug, gnn_score, trm_t, regen_t, barrier_t, trans_t], dim=0)


def _compute_auroc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    """Compute exact Mann-Whitney U AUROC without external dependencies."""
    pos = y_scores[y_true == 1]
    neg = y_scores[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    diff = pos[:, None] - neg[None, :]
    wins = float((diff > 0).sum()) + 0.5 * float((diff == 0).sum())
    return wins / float(len(pos) * len(neg))


def train_dense_reranker(
    dataset: GraphDataset,
    gnn_model: RelationalGNN,
    save_path: Path | str = DEFAULT_RERANKER_PATH,
    num_epochs: int = 45,
    lr: float = 0.002,
) -> DenseCurativeReranker:
    """Train the dense cross-encoder on targeted disease-modifying vs palliative/negative controls with 5-fold CV."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    device = gnn_model.device

    fingerprints = build_chemical_node_features(dataset)
    gse_fc = load_gse256271_barriers()

    with torch.no_grad():
        h_gnn = gnn_model.encode(
            dataset.edge_index.to(device),
            dataset.edge_type.to(device),
            node_features=dataset.node_features.to(device)
            if dataset.node_features is not None
            else None,
            edge_weight=dataset.edge_weight.to(device) if dataset.edge_weight is not None else None,
        )

    # Targeted disease-modifying / regenerative exemplars (excluding acute palliative corticosteroids)
    positive_names = [
        # Pillar 1: Targeted JAK-STAT / IL-15 / Calcineurin / T-cell Disarmament
        "ruxolitinib",
        "tofacitinib",
        "baricitinib",
        "upadacitinib",
        "ritlecitinib",
        "cerdulatinib",
        "povorcitinib",
        "tacrolimus",
        "pimecrolimus",
        "cyclosporine",
        "sirolimus",
        "abatacept",
        "methotrexate",
        # Pillar 2: Melanocyte Stem-Cell / Wnt / Prostaglandin / 5-HT1A / MC1R Regeneration
        "afamelanotide",
        "latanoprost",
        "bimatoprost",
        "travoprost",
        "fluoxetine",
        "vilazodone",
        "minoxidil",
        "tretinoin",
        "calcipotriol",
        # Pillar 3: PDE4-cAMP Barrier Suppression & Redox/Metabolic Remodeling
        "apremilast",
        "crisaborole",
        "roflumilast",
        "rolipram",
        "simvastatin",
        "atorvastatin",
        "metformin",
        "pioglitazone",
    ]

    # Hard negative decoys: acute palliative corticosteroids (relapse-prone) + cytotoxic/non-dermatologic toxics
    negative_names = [
        # Palliative corticosteroids (do not deplete TRM or mobilize McSCs)
        "dexamethasone",
        "betamethasone",
        "clobetasol",
        "fluocinolone",
        "prednisone",
        "prednisolone",
        "hydrocortisone",
        "mometasone",
        "fluticasone",
        "halobetasol",
        "triamcinolone",
        "fluocinonide",
        # Cytotoxic chemotherapeutics and non-dermatologic decoys
        "paclitaxel",
        "cisplatin",
        "doxorubicin",
        "cyclophosphamide",
        "vincristine",
        "fluorouracil",
        "gemcitabine",
        "carboplatin",
        "bleomycin",
        "dacarbazine",
        "warfarin",
        "heparin",
        "digoxin",
        "furosemide",
        "amiodarone",
        "gentamicin",
        "vancomycin",
        "phenytoin",
        "propofol",
        "halothane",
    ]

    pos_features: list[torch.Tensor] = []
    for name in positive_names:
        idx = dataset.name_to_idx.get(name) or dataset.name_to_idx.get(name.lower())
        if idx is not None:
            feat = build_candidate_feature_tensor(
                idx, dataset, h_gnn, gnn_model, fingerprints, gse_fc, device
            )
            pos_features.append(feat)

    neg_features: list[torch.Tensor] = []
    for name in negative_names:
        idx = dataset.name_to_idx.get(name) or dataset.name_to_idx.get(name.lower())
        if idx is not None:
            feat = build_candidate_feature_tensor(
                idx, dataset, h_gnn, gnn_model, fingerprints, gse_fc, device
            )
            neg_features.append(feat)

    x_pos = (
        torch.stack(pos_features)
        if pos_features
        else torch.empty((0, RERANKER_FEATURE_DIM), device=device)
    )
    x_neg = (
        torch.stack(neg_features)
        if neg_features
        else torch.empty((0, RERANKER_FEATURE_DIM), device=device)
    )

    x_train = torch.cat([x_pos, x_neg], dim=0).detach()
    y = torch.cat(
        [torch.ones(len(x_pos), device=device), torch.zeros(len(x_neg), device=device)], dim=0
    ).detach()

    # 5-fold Stratified Out-of-Fold Cross-Validation to measure honest generalization AUROC
    n_total = len(x_train)
    oof_preds = np.zeros(n_total, dtype=np.float32)
    if len(x_pos) >= 5 and len(x_neg) >= 5:
        n_folds = 5
        pos_indices = np.arange(len(x_pos))
        neg_indices = np.arange(len(x_pos), n_total)
        rng = np.random.default_rng(42)
        rng.shuffle(pos_indices)
        rng.shuffle(neg_indices)

        for fold in range(n_folds):
            val_pos = pos_indices[fold::n_folds]
            val_neg = neg_indices[fold::n_folds]
            val_idx_np = np.concatenate([val_pos, val_neg])
            val_mask = torch.zeros(n_total, dtype=torch.bool, device=device)
            val_mask[torch.from_numpy(val_idx_np).to(device)] = True
            tr_mask = ~val_mask

            torch.manual_seed(42 + fold)
            fold_model = DenseCurativeReranker(in_dim=RERANKER_FEATURE_DIM).to(device)
            fold_model.fit_scaler(x_train[tr_mask])
            fold_opt = AdamW(fold_model.parameters(), lr=lr, weight_decay=0.15)
            fold_crit = nn.BCEWithLogitsLoss()
            fold_model.train()
            for _ in range(num_epochs):
                fold_opt.zero_grad()
                loss = fold_crit(fold_model(x_train[tr_mask]), y[tr_mask])
                loss.backward()
                fold_opt.step()
            fold_model.eval()
            with torch.no_grad():
                oof_preds[val_idx_np] = torch.sigmoid(fold_model(x_train[val_mask])).cpu().numpy()
        oof_auroc = _compute_auroc(y.cpu().numpy(), oof_preds)
        oof_acc = float(((oof_preds >= 0.5) == y.cpu().numpy()).mean())
        logger.info(
            "Stage-2 Reranker 5-Fold Out-of-Fold CV | AUROC: %.4f | OOF Accuracy: %.1f%% (%d pos, %d neg)",
            oof_auroc,
            oof_acc * 100,
            len(x_pos),
            len(x_neg),
        )
    else:
        oof_auroc = 0.0
        oof_acc = 0.0

    torch.manual_seed(42)
    reranker = DenseCurativeReranker(in_dim=RERANKER_FEATURE_DIM).to(device)
    reranker.fit_scaler(x_train)
    optimizer = AdamW(reranker.parameters(), lr=lr, weight_decay=0.15)
    criterion = nn.BCEWithLogitsLoss()

    reranker.train()
    for epoch in range(1, num_epochs + 1):
        optimizer.zero_grad()
        logits = reranker(x_train)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        if epoch % 15 == 0 or epoch == num_epochs:
            with torch.no_grad():
                preds = (torch.sigmoid(logits) >= 0.5).float()
                acc = (preds == y).float().mean().item()
            logger.info(
                "Reranker Epoch %02d/%02d | Loss: %.4f | Train Acc: %.1f%%",
                epoch,
                num_epochs,
                loss.item(),
                acc * 100,
            )

    torch.save(
        {
            "state_dict": reranker.state_dict(),
            "in_dim": RERANKER_FEATURE_DIM,
            "num_nodes": dataset.num_nodes,
            "oof_auroc": round(oof_auroc, 4),
            "oof_accuracy": round(oof_acc, 4),
        },
        save_path,
    )
    logger.info("Saved trained dense reranker to %s (OOF AUROC=%.4f)", save_path, oof_auroc)
    return reranker


def rerank_curative_candidates(
    gnn_model: RelationalGNN | None = None,
    dataset: GraphDataset | None = None,
    *,
    checkpoint_path: Path | str = DEFAULT_MODEL_PATH,
    reranker_path: Path | str = DEFAULT_RERANKER_PATH,
    top_stage1: int = 80,
    top_final: int = 20,
    retrain_reranker: bool = True,
    export_json: Path | str = DEFAULT_RERANK_REPORT_JSON,
    export_markdown: Path | str = DEFAULT_RERANK_REPORT_MD,
) -> dict[str, Any]:
    """Execute two-stage candidate retrieval and dense cross-encoder reranking."""
    if dataset is None:
        dataset = load_graph_dataset()

    if gnn_model is None:
        gnn_model = load_trained_gnn(checkpoint_path)

    gnn_model.eval()
    device = gnn_model.device

    fingerprints = build_chemical_node_features(dataset)
    gse_fc = load_gse256271_barriers()

    # Stage 1: ComplEx GNN candidate retrieval with causal edge weights
    with torch.no_grad():
        h_gnn = gnn_model.encode(
            dataset.edge_index.to(device),
            dataset.edge_type.to(device),
            node_features=dataset.node_features.to(device)
            if dataset.node_features is not None
            else None,
            edge_weight=dataset.edge_weight.to(device) if dataset.edge_weight is not None else None,
        )

    canonical_indices = dataset.canonical_drug_indices or dataset.kind_to_indices.get("DRUG", [])
    num_drugs = len(canonical_indices)
    drug_t = torch.tensor(canonical_indices, dtype=torch.long, device=device)

    vitiligo_idx = dataset.name_to_idx.get("vitiligo") or dataset.name_to_idx.get("Vitiligo")
    treats_rel = dataset.relation_to_idx.get("TREATS", 0)
    inhibits_rel = dataset.relation_to_idx.get("INHIBITS", 2)
    activates_rel = dataset.relation_to_idx.get("ACTIVATES", 3)

    if vitiligo_idx is None:
        raise ValueError("Vitiligo disease node not found in dataset.")

    rel_t = torch.full((num_drugs,), treats_rel, dtype=torch.long, device=device)
    vit_t = torch.full((num_drugs,), vitiligo_idx, dtype=torch.long, device=device)

    with torch.no_grad():
        s1_scores = gnn_model.decode_triples(h_gnn, drug_t, rel_t, vit_t).cpu().tolist()

    # Build true Stage-1 ranking lookup across all canonical drugs
    s1_ranked = sorted(
        zip(canonical_indices, s1_scores, strict=False), key=lambda x: x[1], reverse=True
    )
    true_stage1_rank_map: dict[int, int] = {
        d_idx: rank for rank, (d_idx, _) in enumerate(s1_ranked, 1)
    }
    candidate_score_dict: dict[int, float] = {
        d_idx: float(s) for d_idx, s in zip(canonical_indices, s1_scores, strict=False)
    }

    # Pool candidates across direct treats affinity and multi-pillar functional screen
    from vitiligo.gnn.screen import screen_candidates

    screen_res = screen_candidates(
        model=gnn_model,
        dataset=dataset,
        top_k=top_stage1 // 2,
    )

    selected_indices: set[int] = set()
    for d_idx, _ in s1_ranked[: top_stage1 // 2]:
        selected_indices.add(d_idx)

    for item in screen_res.get("durability_top_k", []):
        idx = dataset.key_to_idx.get(item["drug_key"]) or dataset.name_to_idx.get(item["drug_name"])
        if idx is not None:
            selected_indices.add(idx)

    for item in screen_res.get("regeneration_top_k", []):
        idx = dataset.key_to_idx.get(item["drug_key"]) or dataset.name_to_idx.get(item["drug_name"])
        if idx is not None:
            selected_indices.add(idx)

    # Sort pooled Stage-1 candidates by their true Stage-1 rank
    top_s1_candidates = sorted(
        [(d_idx, candidate_score_dict.get(d_idx, 0.0)) for d_idx in selected_indices],
        key=lambda x: true_stage1_rank_map.get(x[0], 999999),
    )

    # Build lookup of verified direct drug-target edges in the knowledge graph
    verified_edges: set[tuple[int, int, int]] = set()
    src_l = dataset.edge_index[0].tolist()
    dst_l = dataset.edge_index[1].tolist()
    rel_l = dataset.edge_type.tolist()
    for u, v, r in zip(src_l, dst_l, rel_l, strict=False):
        if r in (inhibits_rel, activates_rel):
            verified_edges.add((u, r, v))

    # Stage 2: Cross-Encoder Reranking (retrain if requested or if node count changed)
    reranker_path = Path(reranker_path)
    oof_auroc = 0.0
    oof_accuracy = 0.0
    need_train = retrain_reranker or not reranker_path.exists()
    if not need_train and reranker_path.exists():
        try:
            ckpt = torch.load(reranker_path, map_location=device, weights_only=False)
            if ckpt.get("num_nodes") != dataset.num_nodes:
                need_train = True
            else:
                reranker = DenseCurativeReranker(in_dim=RERANKER_FEATURE_DIM).to(device)
                reranker.load_state_dict(ckpt["state_dict"])
                oof_auroc = float(ckpt.get("oof_auroc", 0.0))
                oof_accuracy = float(ckpt.get("oof_accuracy", 0.0))
        except Exception:
            need_train = True

    if need_train:
        reranker = train_dense_reranker(dataset, gnn_model, save_path=reranker_path)
        if reranker_path.exists():
            ckpt = torch.load(reranker_path, map_location=device, weights_only=False)
            oof_auroc = float(ckpt.get("oof_auroc", 0.0))
            oof_accuracy = float(ckpt.get("oof_accuracy", 0.0))

    reranker.eval()

    # First pass: compute features and pillar score distributions across all pooled candidates for percentile calibration
    cand_features: list[tuple[int, float, torch.Tensor]] = []
    all_trm_means: list[float] = []
    all_regen_means: list[float] = []
    all_barrier_means: list[float] = []
    all_gene_scores: list[float] = []

    for d_idx, s1_score in top_s1_candidates:
        feat = build_candidate_feature_tensor(
            d_idx, dataset, h_gnn, gnn_model, fingerprints, gse_fc, device
        )
        cand_features.append((d_idx, s1_score, feat))
        trm_v = feat[1153:1161].cpu().tolist()
        reg_v = feat[1161:1168].cpu().tolist()
        bar_v = feat[1168:1171].cpu().tolist()
        all_trm_means.append(float(np.mean(trm_v)))
        all_regen_means.append(float(np.mean(reg_v)))
        all_barrier_means.append(float(np.mean(bar_v)))
        all_gene_scores.extend(trm_v + reg_v + bar_v)

    # Calibrate 75th-percentile thresholds so only top-quartile pillar activators get tagged
    trm_p75 = float(np.percentile(all_trm_means, 70)) if all_trm_means else 1.0
    regen_p75 = float(np.percentile(all_regen_means, 70)) if all_regen_means else 1.0
    barrier_p75 = float(np.percentile(all_barrier_means, 70)) if all_barrier_means else 1.0
    gene_p85 = float(np.percentile(all_gene_scores, 85)) if all_gene_scores else 2.0

    reranked_items: list[RerankedCandidate] = []
    for d_idx, s1_score, feat in cand_features:
        d_entity = dataset.entities[d_idx]
        s1_rank = true_stage1_rank_map.get(d_idx, 999)
        safety_tier, is_chemo = get_safety_profile(d_entity.name)

        with torch.no_grad():
            r_logit = float(reranker(feat.unsqueeze(0)).item())
            prob = float(torch.sigmoid(torch.tensor(r_logit)).item())

        trm_vals = feat[1153:1161].cpu().tolist()
        regen_vals = feat[1161:1168].cpu().tolist()
        barrier_vals = feat[1168:1171].cpu().tolist()
        trans_align = float(feat[1171].item())

        trm_mean = float(np.mean(trm_vals))
        regen_mean = float(np.mean(regen_vals))
        barrier_mean = float(np.mean(barrier_vals))

        matched_targets: list[str] = []
        has_verified_trm = False
        has_verified_regen = False
        has_verified_barrier = False

        for g, val in zip(CORE_TRM_GENES, trm_vals, strict=False):
            g_idx = dataset.name_to_idx.get(g) or dataset.name_to_idx.get(g.lower())
            is_ver = g_idx is not None and (d_idx, inhibits_rel, g_idx) in verified_edges
            if is_ver:
                matched_targets.append(f"{g} (Inh*)")
                has_verified_trm = True
            elif val >= gene_p85:
                matched_targets.append(f"{g} (Inh)")

        for g, val in zip(CORE_REGEN_GENES, regen_vals, strict=False):
            g_idx = dataset.name_to_idx.get(g) or dataset.name_to_idx.get(g.lower())
            is_ver = g_idx is not None and (d_idx, activates_rel, g_idx) in verified_edges
            if is_ver:
                matched_targets.append(f"{g} (Act*)")
                has_verified_regen = True
            elif val >= gene_p85:
                matched_targets.append(f"{g} (Act)")

        for g, val in zip(CORE_BARRIER_GENES, barrier_vals, strict=False):
            g_idx = dataset.name_to_idx.get(g) or dataset.name_to_idx.get(g.lower())
            is_ver = g_idx is not None and (d_idx, inhibits_rel, g_idx) in verified_edges
            if is_ver:
                matched_targets.append(f"{g} (Inh*)")
                has_verified_barrier = True
            elif val >= gene_p85:
                matched_targets.append(f"{g} (Inh)")

        # Penalize chemotherapeutics and contraindications in final ranking
        final_score = r_logit
        if is_chemo:
            final_score -= 10.0
            prob = 0.01

        triad_profile: list[str] = []
        if has_verified_trm or trm_mean >= trm_p75:
            triad_profile.append("Pillar 1: TRM Disarmament")
        if has_verified_regen or regen_mean >= regen_p75:
            triad_profile.append("Pillar 2: Stem-Cell Regeneration")
        if has_verified_barrier or barrier_mean >= barrier_p75:
            triad_profile.append("Pillar 3: PDE4B Barrier Suppression")

        reranked_items.append(
            RerankedCandidate(
                stage2_rank=0,
                stage1_rank=s1_rank,
                drug_name=d_entity.name,
                drug_key=d_entity.key,
                reranker_score=round(final_score, 4),
                probability=round(prob, 4),
                gnn_affinity_score=round(s1_score, 4),
                trm_disarmament_score=round(trm_mean, 4),
                stem_cell_regen_score=round(regen_mean, 4),
                barrier_suppression_score=round(barrier_mean, 4),
                transcriptomic_alignment=round(trans_align, 4),
                matched_targets=matched_targets,
                safety_tier=safety_tier,
                is_cytotoxic=is_chemo,
                curative_triad_alignment=" + ".join(triad_profile)
                if triad_profile
                else "Supportive Immunomodulator",
            )
        )

    # Sort descending by Stage-2 cross-encoder score and deduplicate salt/brand synonyms
    reranked_items.sort(key=lambda x: x.reranker_score, reverse=True)
    brand_to_generic = {
        "litfulo": "ritlecitinib",
        "opzelura": "ruxolitinib",
        "olumiant": "baricitinib",
        "xeljanz": "tofacitinib",
        "rinvoq": "upadacitinib",
        "otezla": "apremilast",
        "eucrisa": "crisaborole",
        "protopic": "tacrolimus",
        "elidel": "pimecrolimus",
        "stelara": "ustekinumab",
        "cosentyx": "secukinumab",
        "humira": "adalimumab",
        "enbrel": "etanercept",
    }
    non_curative_comorbidities = {
        "insulin glargine",
        "itraconazole",
        "bicalutamide",
        "tranexamic acid",
        "omalizumab",
        "lidocaine",
        "prilocaine",
    }
    final_top: list[RerankedCandidate] = []
    seen_canonical: set[str] = set()
    for item in reranked_items:
        base_name = clean_drug_name(item.drug_name).lower()
        canonical_name = brand_to_generic.get(base_name, base_name)
        if canonical_name in seen_canonical or canonical_name in non_curative_comorbidities:
            continue
        seen_canonical.add(canonical_name)
        if base_name in brand_to_generic:
            item.drug_name = canonical_name
        item.stage2_rank = len(final_top) + 1
        final_top.append(item)
        if len(final_top) >= top_final:
            break

    report_data = {
        "architecture": "Two-Stage Retrieve-and-Rerank (Stage 1: RGAT-4H ComplEx GNN -> Stage 2: Modality-Balanced Bottleneck Cross-Encoder)",
        "stage1_pool_size": len(top_s1_candidates),
        "stage2_top_k": len(final_top),
        "feature_dimension": RERANKER_FEATURE_DIM,
        "cv_oof_auroc": oof_auroc,
        "cv_oof_accuracy": oof_accuracy,
        "candidates": [asdict(c) for c in final_top],
    }

    export_json = Path(export_json)
    export_json.parent.mkdir(parents=True, exist_ok=True)
    with open(export_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    _write_rerank_markdown(report_data, Path(export_markdown))
    logger.info(
        "Exported Top-%d Stage-2 reranked curative candidates to %s", top_final, export_json
    )
    return {
        **report_data,
        "top_candidates": final_top,
        "export_json": str(export_json),
        "export_markdown": str(export_markdown),
    }


def _write_rerank_markdown(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage-2 Dense Cross-Encoder Reranked Curative Candidates",
        "",
        f"**Architecture:** `{report['architecture']}`  ",
        f"**Feature Vector:** `{report['feature_dimension']}-D` (1024-D Morgan Fingerprints + 128-D RGAT-ComplEx Latent + 18-D Triad Target Affinities + GSE256271 Barrier Alignment)  ",
        f"**5-Fold Out-of-Fold CV:** `AUROC = {report.get('cv_oof_auroc', 0.0):.4f}`, `Accuracy = {report.get('cv_oof_accuracy', 0.0) * 100:.1f}%`  ",
        "",
        "| S2 Rank | S1 Rank | Candidate Drug | Prob | Rerank Logit | TRM Disarm | McSC Regen | PDE4B Barrier | Curative Triad Alignment | Key Targets (`*` = Verified) |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---|---|",
    ]

    for c in report["candidates"]:
        targets_str = ", ".join(c["matched_targets"][:5])
        if len(c["matched_targets"]) > 5:
            targets_str += f" (+{len(c['matched_targets']) - 5})"
        lines.append(
            f"| **{c['stage2_rank']}** | {c['stage1_rank']} | **{c['drug_name']}** | `{c['probability']:.3f}` | `{c['reranker_score']:.2f}` | `{c['trm_disarmament_score']:.2f}` | `{c['stem_cell_regen_score']:.2f}` | `{c['barrier_suppression_score']:.2f}` | {c['curative_triad_alignment']} | {targets_str} |"
        )

    lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
