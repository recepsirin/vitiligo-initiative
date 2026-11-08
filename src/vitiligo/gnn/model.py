"""Relational Graph Neural Network for biomedical knowledge graph link prediction."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional
from torch_geometric.nn import FastRGCNConv
from torch_geometric.utils import softmax

from vitiligo.gnn.dataset import GraphDataset


class RelationalGATConv(nn.Module):
    """Memory-efficient multi-head Relational Graph Attention layer.

    Projects nodes and relation types into query, key, value attention spaces,
    computing multi-head attention scores with causal edge weights and residual skip connections:
    alpha_{ij} = Softmax_j( LeakyReLU( (W_q h_i + W_k h_j + W_r e_r) * a ) )
    message = (W_v h_j + W_vr e_r) * alpha_{ij}
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        num_relations: int,
        heads: int = 4,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.heads = heads
        self.head_dim = out_channels // heads
        if self.head_dim * heads != out_channels:
            raise ValueError(f"out_channels ({out_channels}) must be divisible by heads ({heads})")

        self.lin_src = nn.Linear(in_channels, out_channels, bias=False)
        self.lin_dst = nn.Linear(in_channels, out_channels, bias=False)
        self.rel_emb = nn.Embedding(num_relations, out_channels)
        self.attn = nn.Parameter(torch.empty(1, heads, self.head_dim))
        self.root = nn.Linear(in_channels, out_channels, bias=True)
        self.dropout = nn.Dropout(dropout)

        nn.init.xavier_uniform_(self.lin_src.weight)
        nn.init.xavier_uniform_(self.lin_dst.weight)
        nn.init.xavier_uniform_(self.rel_emb.weight)
        nn.init.xavier_uniform_(self.attn)
        self.scale = 1.0 / (self.head_dim**0.5)
        self._alpha: torch.Tensor | None = None

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        edge_weight: torch.Tensor | None = None,
    ) -> torch.Tensor:
        num_nodes = x.size(0)
        src, dst = edge_index[0], edge_index[1]

        h_src = self.lin_src(x).view(-1, self.heads, self.head_dim)
        h_dst = self.lin_dst(x).view(-1, self.heads, self.head_dim)
        r_emb = self.rel_emb(edge_type).view(-1, self.heads, self.head_dim)

        edge_h = functional.leaky_relu(h_src[src] + h_dst[dst] + r_emb, negative_slope=0.2)
        logits = (edge_h * self.attn).sum(dim=-1) * self.scale
        if edge_weight is not None:
            logits = logits + torch.log(edge_weight.unsqueeze(-1).clamp(min=1e-4))
        alpha = softmax(logits, dst, num_nodes=num_nodes)
        self._alpha = alpha.detach()
        alpha = self.dropout(alpha)

        msg = (h_src[src] + r_emb) * alpha.unsqueeze(-1)
        msg = msg.view(-1, self.out_channels)

        out = torch.zeros(num_nodes, self.out_channels, device=x.device, dtype=x.dtype)
        out.index_add_(0, dst, msg)
        out = out + self.root(x)
        return out


class RelationalGNN(nn.Module):
    """Multi-layer Relational GNN encoder with a ComplEx / DistMult link prediction decoder.

    Incorporates:
    - Multimodal projection fusing fine-tuned BiomedBERT (768D), Morgan fingerprints (1024D),
      HGNC families (128D), and 16-D consensus GEO transcriptomics.
    - Relational Graph Attention (RGAT) with multi-head attention across typed biological relations
      or basis-decomposed FastRGCN with LayerNorm and GeLU activations.
    - Asymmetric ComplEx Hermitian link decoder in C^d (or symmetric DistMult).
    - Bidirectional self-adversarial negative sampling (corrupting heads and tails).
    - Causal-weight-aware loss modulation.
    - Fast all-candidate parallel scoring for ranking and discovery.
    """

    def __init__(
        self,
        num_nodes: int,
        num_relations: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        num_bases: int | None = 30,
        feature_dim: int | None = 772,
        encoder_type: str = "rgat",
        heads: int = 4,
        decoder_type: str = "complex",
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.num_nodes = num_nodes
        self.num_relations = num_relations
        self.hidden_dim = hidden_dim
        self.half_dim = hidden_dim // 2
        self.feature_dim = feature_dim
        self.encoder_type = encoder_type.lower()
        self.decoder_type = decoder_type.lower()
        self.heads = heads

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

        # Relational GNN layers: RGAT multi-head attention or FastRGCN
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        for _ in range(num_layers):
            if self.encoder_type == "rgat":
                self.convs.append(
                    RelationalGATConv(
                        in_channels=hidden_dim,
                        out_channels=hidden_dim,
                        num_relations=num_relations,
                        heads=heads,
                        dropout=dropout,
                    )
                )
            else:
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
        edge_weight: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Propagate relational messages across graph edges to obtain updated node representations."""
        edge_index = edge_index.to(self.device)
        edge_type = edge_type.to(self.device)
        if edge_weight is not None:
            edge_weight = edge_weight.to(self.device)

        if node_features is not None and self.node_proj is not None:
            feat = node_features.to(self.device)
            h = self.node_proj(feat) + self.node_emb.weight
        else:
            h = self.node_emb.weight

        for conv, norm in zip(self.convs, self.norms, strict=False):
            if isinstance(conv, RelationalGATConv):
                h_next = conv(h, edge_index, edge_type, edge_weight=edge_weight)
            else:
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
        """Compute link scores for specific (h, r, t) triples via ComplEx Hermitian or DistMult dot product."""
        h_emb = h[head_indices]
        r_emb = self.rel_emb(rel_indices)
        t_emb = h[tail_indices]

        if self.decoder_type == "distmult":
            return torch.sum(h_emb * r_emb * t_emb, dim=-1)

        # ComplEx Hermitian product: Re <h, r, conj(t)>
        h_re, h_im = h_emb[:, : self.half_dim], h_emb[:, self.half_dim :]
        r_re, r_im = r_emb[:, : self.half_dim], r_emb[:, self.half_dim :]
        t_re, t_im = t_emb[:, : self.half_dim], t_emb[:, self.half_dim :]

        return (
            torch.sum(r_re * h_re * t_re, dim=-1)
            + torch.sum(r_re * h_im * t_im, dim=-1)
            + torch.sum(r_im * h_re * t_im, dim=-1)
            - torch.sum(r_im * h_im * t_re, dim=-1)
        )

    def decode_all_tails(
        self,
        h: torch.Tensor,
        head_indices: torch.Tensor,
        rel_indices: torch.Tensor,
    ) -> torch.Tensor:
        """Compute link prediction scores for all possible tail entities (shape: [batch_size, num_nodes])."""
        h_emb = h[head_indices]
        r_emb = self.rel_emb(rel_indices)

        if self.decoder_type == "distmult":
            query = h_emb * r_emb  # [B, hidden_dim]
            return torch.matmul(query, h.t())

        # ComplEx parallel tail scoring:
        # q_re = h_re * r_re - h_im * r_im
        # q_im = h_re * r_im + h_im * r_re
        # scores = q_re @ t_re.T + q_im @ t_im.T
        h_re, h_im = h_emb[:, : self.half_dim], h_emb[:, self.half_dim :]
        r_re, r_im = r_emb[:, : self.half_dim], r_emb[:, self.half_dim :]
        t_re = h[:, : self.half_dim]
        t_im = h[:, self.half_dim :]

        q_re = h_re * r_re - h_im * r_im
        q_im = h_re * r_im + h_im * r_re

        return torch.matmul(q_re, t_re.t()) + torch.matmul(q_im, t_im.t())

    def decode_all_heads(
        self,
        h: torch.Tensor,
        rel_indices: torch.Tensor,
        tail_indices: torch.Tensor,
    ) -> torch.Tensor:
        """Compute link scores for all possible heads h against batch queries (?, r, t).

        Returns tensor of shape [batch_size, num_nodes].
        """
        r_emb = self.rel_emb(rel_indices)
        t_emb = h[tail_indices]

        if self.decoder_type == "distmult":
            query = r_emb * t_emb
            return torch.matmul(query, h.t())

        # ComplEx: Re(<h, r, conj(t)>) = a(ce + df) + b(cf - de)
        # where h = a + ib, r = c + id, t = e + if
        r_re, r_im = r_emb[:, : self.half_dim], r_emb[:, self.half_dim :]
        t_re, t_im = t_emb[:, : self.half_dim], t_emb[:, self.half_dim :]
        all_h_re = h[:, : self.half_dim]
        all_h_im = h[:, self.half_dim :]

        w_re = r_re * t_re + r_im * t_im
        w_im = r_re * t_im - r_im * t_re

        return torch.matmul(w_re, all_h_re.t()) + torch.matmul(w_im, all_h_im.t())

    def compute_loss(
        self,
        h: torch.Tensor,
        pos_heads: torch.Tensor,
        pos_rels: torch.Tensor,
        pos_tails: torch.Tensor,
        edge_weights: torch.Tensor | None = None,
        sampling_weights: torch.Tensor | None = None,
        num_neg_samples: int = 4,
        adversarial_temperature: float = 1.0,
    ) -> torch.Tensor:
        """Compute causal-weighted BCE loss with bidirectional self-adversarial negative sampling."""
        batch_size = pos_heads.size(0)

        # Positive scores
        pos_scores = self.decode_triples(h, pos_heads, pos_rels, pos_tails)
        pos_targets = torch.ones_like(pos_scores)
        pos_loss = self.bce_loss(pos_scores, pos_targets)

        # Scale positive loss by causal ladder edge weights if provided
        if edge_weights is not None:
            pos_loss = pos_loss * edge_weights
        mean_pos_loss = pos_loss.mean()

        # Draw negative candidates with bidirectional corruption (50% head, 50% tail)
        total_negs = batch_size * num_neg_samples
        if sampling_weights is not None:
            corrupt_nodes = torch.multinomial(
                sampling_weights, num_samples=total_negs, replacement=True
            ).to(self.device)
        else:
            corrupt_nodes = torch.randint(0, self.num_nodes, (total_negs,), device=self.device)

        neg_heads = pos_heads.repeat_interleave(num_neg_samples)
        neg_tails = pos_tails.repeat_interleave(num_neg_samples)
        neg_rels = pos_rels.repeat_interleave(num_neg_samples)

        corrupt_head_mask = torch.rand(total_negs, device=self.device) < 0.5
        neg_heads = torch.where(corrupt_head_mask, corrupt_nodes, neg_heads)
        neg_tails = torch.where(~corrupt_head_mask, corrupt_nodes, neg_tails)

        neg_scores = self.decode_triples(h, neg_heads, neg_rels, neg_tails)
        neg_scores_matrix = neg_scores.view(batch_size, num_neg_samples)
        neg_targets = torch.zeros_like(neg_scores_matrix)

        neg_losses = self.bce_loss(neg_scores_matrix, neg_targets)

        # Self-adversarial weighting: penalize hard negative candidates proportionally
        if adversarial_temperature > 0.0 and num_neg_samples > 1:
            adv_weights = torch.softmax(
                adversarial_temperature * neg_scores_matrix, dim=-1
            ).detach()
            mean_neg_loss = (adv_weights * neg_losses).sum(dim=-1).mean()
        else:
            mean_neg_loss = neg_losses.mean()

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
