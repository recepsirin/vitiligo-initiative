"""Relational Graph Neural Network for biomedical knowledge graph link prediction."""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.nn import FastRGCNConv

from vitiligo.gnn.dataset import GraphDataset


class RelationalGNN(nn.Module):
    """Multi-layer Relational GNN encoder with a DistMult / Bilinear link prediction decoder.

    Incorporates:
    - Multimodal projection fusing fine-tuned BiomedBERT (768D) and GEO transcriptomics (4D).
    - Basis-decomposed multi-relational message passing.
    - Causal-weight-aware loss modulation.
    - Degree-weighted negative sampling to eliminate hub bias.
    - Fast all-candidate scoring for ranking and discovery.
    """

    def __init__(
        self,
        num_nodes: int,
        num_relations: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        num_bases: int | None = 30,
        feature_dim: int | None = 772,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.num_nodes = num_nodes
        self.num_relations = num_relations
        self.hidden_dim = hidden_dim
        self.feature_dim = feature_dim

        # Initial node representations & multimodal projection
        self.node_emb = nn.Embedding(num_nodes, hidden_dim)
        nn.init.xavier_uniform_(self.node_emb.weight)

        if feature_dim is not None:
            self.node_proj = nn.Sequential(
                nn.Linear(feature_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.Dropout(dropout),
            )
        else:
            self.node_proj = None

        # Relation embeddings for decoder
        self.rel_emb = nn.Embedding(num_relations, hidden_dim)
        nn.init.xavier_uniform_(self.rel_emb.weight)

        # Relational GNN layers
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        for _ in range(num_layers):
            self.convs.append(
                FastRGCNConv(
                    in_channels=hidden_dim,
                    out_channels=hidden_dim,
                    num_relations=num_relations,
                    num_bases=num_bases,
                )
            )
            self.norms.append(nn.LayerNorm(hidden_dim))

        self.dropout = nn.Dropout(dropout)
        self.bce_loss = nn.BCEWithLogitsLoss(reduction="none")

    @property
    def device(self) -> torch.device:
        return self.node_emb.weight.device

    def encode(
        self,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        node_features: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Propagate relational messages across graph edges to obtain updated node representations."""
        edge_index = edge_index.to(self.device)
        edge_type = edge_type.to(self.device)

        if node_features is not None and self.node_proj is not None:
            feat = node_features.to(self.device)
            h = self.node_proj(feat) + self.node_emb.weight
        else:
            h = self.node_emb.weight

        for conv, norm in zip(self.convs, self.norms, strict=False):
            h_next = conv(h, edge_index, edge_type)
            h = norm(h + self.dropout(nn.functional.gelu(h_next)))
        return h

    def decode_triples(
        self,
        h: torch.Tensor,
        head_indices: torch.Tensor,
        rel_indices: torch.Tensor,
        tail_indices: torch.Tensor,
    ) -> torch.Tensor:
        """Compute link scores for specific (h, r, t) triples via DistMult dot product."""
        h_emb = h[head_indices]
        r_emb = self.rel_emb(rel_indices)
        t_emb = h[tail_indices]
        return torch.sum(h_emb * r_emb * t_emb, dim=-1)

    def decode_all_tails(
        self,
        h: torch.Tensor,
        head_indices: torch.Tensor,
        rel_indices: torch.Tensor,
    ) -> torch.Tensor:
        """Compute link prediction scores for all possible tail entities (shape: [batch_size, num_nodes])."""
        h_emb = h[head_indices]
        r_emb = self.rel_emb(rel_indices)
        query = h_emb * r_emb  # [B, hidden_dim]
        # query @ h.T -> [B, num_nodes]
        return torch.matmul(query, h.t())

    def compute_loss(
        self,
        h: torch.Tensor,
        pos_heads: torch.Tensor,
        pos_rels: torch.Tensor,
        pos_tails: torch.Tensor,
        edge_weights: torch.Tensor | None = None,
        sampling_weights: torch.Tensor | None = None,
        num_neg_samples: int = 1,
    ) -> torch.Tensor:
        """Compute causal-weighted binary cross-entropy loss with degree-weighted negative sampling."""
        batch_size = pos_heads.size(0)

        # Positive scores
        pos_scores = self.decode_triples(h, pos_heads, pos_rels, pos_tails)
        pos_targets = torch.ones_like(pos_scores)
        pos_loss = self.bce_loss(pos_scores, pos_targets)

        # Scale positive loss by causal ladder edge weights if provided
        if edge_weights is not None:
            pos_loss = pos_loss * edge_weights
        mean_pos_loss = pos_loss.mean()

        # Degree-weighted negative sampling to penalize hub shortcuts
        total_negs = batch_size * num_neg_samples
        if sampling_weights is not None:
            neg_tails = torch.multinomial(sampling_weights, num_samples=total_negs, replacement=True).to(self.device)
        else:
            neg_tails = torch.randint(0, self.num_nodes, (total_negs,), device=self.device)

        neg_heads = pos_heads.repeat_interleave(num_neg_samples)
        neg_rels = pos_rels.repeat_interleave(num_neg_samples)

        neg_scores = self.decode_triples(h, neg_heads, neg_rels, neg_tails)
        neg_targets = torch.zeros_like(neg_scores)
        mean_neg_loss = self.bce_loss(neg_scores, neg_targets).mean()

        return mean_pos_loss + mean_neg_loss

    @torch.no_grad()
    def predict_top_k(
        self,
        head_name: str,
        rel_name: str,
        dataset: GraphDataset,
        top_k: int = 15,
        target_kind: str | None = None,
        canonical_only: bool = True,
    ) -> list[dict[str, object]]:
        """Predict top-k candidate entities for (head_name, rel_name, ?)."""
        self.eval()
        if head_name.lower() in dataset.name_to_idx:
            head_idx = dataset.name_to_idx[head_name.lower()]
        elif head_name in dataset.name_to_idx:
            head_idx = dataset.name_to_idx[head_name]
        elif head_name in dataset.key_to_idx:
            head_idx = dataset.key_to_idx[head_name]
        else:
            raise KeyError(f"Head entity '{head_name}' not found in dataset.")

        if rel_name not in dataset.relation_to_idx:
            raise KeyError(f"Relation '{rel_name}' not in {dataset.idx_to_relation}")
        rel_idx = dataset.relation_to_idx[rel_name]

        edge_index = dataset.edge_index.to(self.device)
        edge_type = dataset.edge_type.to(self.device)

        h = self.encode(edge_index, edge_type, node_features=dataset.node_features)

        head_t = torch.tensor([head_idx], dtype=torch.long, device=self.device)
        rel_t = torch.tensor([rel_idx], dtype=torch.long, device=self.device)

        scores = self.decode_all_tails(h, head_t, rel_t).squeeze(0)  # [num_nodes]

        # Mask out self
        scores[head_idx] = -1e9

        # Filter by target kind if requested
        if target_kind:
            if target_kind == "DRUG" and canonical_only and dataset.canonical_drug_indices:
                allowed_indices = set(dataset.canonical_drug_indices)
            else:
                allowed_indices = set(dataset.kind_to_indices.get(target_kind, []))
            mask = torch.ones_like(scores, dtype=torch.bool)
            mask[list(allowed_indices)] = False
            scores[mask] = -1e9

        top_scores, top_indices = torch.topk(scores, k=min(top_k, self.num_nodes))

        results: list[dict[str, object]] = []
        for score, idx in zip(top_scores.tolist(), top_indices.tolist(), strict=False):
            if score <= -1e8:
                continue
            entity = dataset.entities[idx]
            results.append(
                {
                    "rank": len(results) + 1,
                    "score": round(float(score), 4),
                    "probability": round(float(torch.sigmoid(torch.tensor(score)).item()), 4),
                    "name": entity.name,
                    "kind": entity.kind,
                    "key": entity.key,
                }
            )
        return results
