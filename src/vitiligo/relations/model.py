"""An encoder that reads a text once and classifies every entity pair in it.

The text is encoded once; each entity pools its mention markers and spans;
and each pair is classified from the two entities, their types, ATLOP localized
context pooling (joint self-attention of the pair), and the span between their
closest mentions. Reading once per text rather than once per pair is what makes
the full texts affordable on one machine: a passage with thirty entities has
435 pairs and still costs one forward pass.

A text longer than the encoder's window is read in overlapping windows and a
token takes the mean of the states it was given.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import torch
from torch import nn
from transformers import AutoConfig, AutoModel

from vitiligo.relations.data import (
    ALLOWED_LABELS_BY_TYPE_PAIR,
    ENTITY_TYPES,
    LABELS,
    WINDOW,
    Encoded,
    window_starts,
)


def _build_type_pair_mask() -> torch.Tensor:
    mask = torch.zeros((len(ENTITY_TYPES), len(ENTITY_TYPES), len(LABELS)), dtype=torch.float32)
    for i, t1 in enumerate(ENTITY_TYPES):
        for j, t2 in enumerate(ENTITY_TYPES):
            key = (t1, t2) if (t1, t2) in ALLOWED_LABELS_BY_TYPE_PAIR else (t2, t1)
            allowed = ALLOWED_LABELS_BY_TYPE_PAIR.get(key, LABELS)
            for k, lbl in enumerate(LABELS):
                if lbl not in allowed:
                    mask[i, j, k] = -1e4
    return mask


class RelationModel(nn.Module):
    def __init__(
        self, encoder: str, *, cls_id: int, sep_id: int, pad_id: int, pretrained: bool = True
    ) -> None:
        super().__init__()
        self.encoder_name = encoder
        # Explicitly float32 and eager attention so last-layer attentions are available
        # for ATLOP localized context pooling.
        config = AutoConfig.from_pretrained(encoder, attn_implementation="eager")
        self.encoder: Any = (
            AutoModel.from_pretrained(encoder, dtype=torch.float32, attn_implementation="eager")
            if pretrained
            else AutoModel.from_config(config, dtype=torch.float32, attn_implementation="eager")  # type: ignore[no-untyped-call]
        )
        hidden = int(self.encoder.config.hidden_size)
        self.type_embedding = nn.Embedding(len(ENTITY_TYPES), 64)
        self.head = nn.Sequential(
            nn.Linear(3 * hidden + 128, hidden),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden, len(LABELS)),
        )
        proj_dim = 256
        ctx_dim = 2 * hidden + 4 * proj_dim + 64
        self.dist_embedding = nn.Embedding(8, 32)
        self.cosent_embedding = nn.Embedding(3, 32)
        self.head_proj = nn.Linear(3 * hidden + 64, proj_dim)
        self.tail_proj = nn.Linear(3 * hidden + 64, proj_dim)
        self.mention_type_proj = nn.Linear(64, hidden, bias=False)
        nn.init.zeros_(self.mention_type_proj.weight)
        self.pair_type_embedding = nn.Embedding(len(ENTITY_TYPES) * len(ENTITY_TYPES), 64)
        self.type_gate = nn.Linear(64, ctx_dim)
        nn.init.zeros_(self.type_gate.weight)
        nn.init.zeros_(self.type_gate.bias)
        self.type_pair_bias = nn.Parameter(
            torch.zeros((len(ENTITY_TYPES), len(ENTITY_TYPES), len(LABELS)))
        )
        ctx_out = nn.Linear(hidden // 2, len(LABELS))
        nn.init.zeros_(ctx_out.weight)
        nn.init.zeros_(ctx_out.bias)
        self.context_head = nn.Sequential(
            nn.LayerNorm(ctx_dim),
            nn.Dropout(0.15),
            nn.Linear(ctx_dim, hidden // 2),
            nn.GELU(),
            nn.Dropout(0.1),
            ctx_out,
        )
        self.register_buffer("type_pair_mask", _build_type_pair_mask(), persistent=False)
        self.cls_id, self.sep_id, self.pad_id = cls_id, sep_id, pad_id

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    def token_states_and_attentions(
        self, documents: Sequence[list[int]]
    ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """Each document's token states and stitched token-to-token attention matrices."""
        windows: list[list[int]] = []
        owners: list[tuple[int, int, int]] = []
        for index, document in enumerate(documents):
            for start in window_starts(len(document)):
                chunk = document[start : start + WINDOW - 2]
                windows.append([self.cls_id, *chunk, self.sep_id])
                owners.append((index, start, len(chunk)))
        width = max(len(w) for w in windows)
        ids = torch.full((len(windows), width), self.pad_id, dtype=torch.long)
        mask = torch.zeros((len(windows), width), dtype=torch.long)
        for row, window in enumerate(windows):
            ids[row, : len(window)] = torch.tensor(window)
            mask[row, : len(window)] = 1
        enc_out = self.encoder(
            input_ids=ids.to(self.device),
            attention_mask=mask.to(self.device),
            output_attentions=True,
        )
        out = enc_out.last_hidden_state
        win_att = enc_out.attentions[-1].mean(dim=1)  # (num_windows, width, width)
        hidden = out.shape[-1]
        sums = [out.new_zeros((len(d), hidden)) for d in documents]
        counts = [out.new_zeros((len(d), 1)) for d in documents]
        att_sums = [out.new_zeros((len(d), len(d))) for d in documents]
        for row, (index, start, n) in enumerate(owners):
            sums[index][start : start + n] += out[row, 1 : 1 + n]
            counts[index][start : start + n] += 1
            att_sums[index][start : start + n, start : start + n] += win_att[
                row, 1 : 1 + n, 1 : 1 + n
            ]
        states = [s / c.clamp(min=1) for s, c in zip(sums, counts, strict=True)]
        atts = [a / a.sum(dim=-1, keepdim=True).clamp(min=1e-7) for a in att_sums]
        return states, atts

    def token_states(self, documents: Sequence[list[int]]) -> list[torch.Tensor]:
        """Each document's token states, its windows stitched back together."""
        states, _ = self.token_states_and_attentions(documents)
        return states

    def forward(self, batch: Sequence[Encoded]) -> torch.Tensor:
        """Logits over LABELS for every candidate pair in the batch, in order."""
        states, atts = self.token_states_and_attentions([e.input_ids for e in batch])
        base_fwd_list: list[torch.Tensor] = []
        base_rev_list: list[torch.Tensor] = []
        ctx_fwd_list: list[torch.Tensor] = []
        ctx_rev_list: list[torch.Tensor] = []
        same_type_list: list[torch.Tensor] = []
        mask_offsets: list[torch.Tensor] = []
        type_pair_mask: torch.Tensor = self.type_pair_mask  # type: ignore[assignment]
        sym_type_bias = 0.5 * (self.type_pair_bias + self.type_pair_bias.transpose(0, 1))

        for encoded, tokens, doc_att in zip(batch, states, atts, strict=True):
            ent_type_ids = torch.tensor(encoded.entity_types, device=self.device, dtype=torch.long)
            types = self.type_embedding(ent_type_ids)
            mention_type_vecs = self.mention_type_proj(types)

            entities_open = torch.stack(
                [torch.logsumexp(tokens[positions], dim=0) for positions in encoded.mention_tokens]
            )
            ctx_tokens = tokens.clone()
            if encoded.mention_end_tokens and len(encoded.mention_end_tokens) == len(
                encoded.mention_tokens
            ):
                span_vecs = []
                for ent_idx, (starts, ends) in enumerate(
                    zip(encoded.mention_tokens, encoded.mention_end_tokens, strict=True)
                ):
                    m_means = []
                    for s, e in zip(starts, ends, strict=True):
                        hi = max(s + 1, e + 1)
                        m_means.append(tokens[s:hi].mean(dim=0))
                        ctx_tokens[s:hi] = ctx_tokens[s:hi] + mention_type_vecs[ent_idx]
                    span_vecs.append(torch.logsumexp(torch.stack(m_means), dim=0))
                entities_span = torch.stack(span_vecs)
            else:
                for ent_idx, starts in enumerate(encoded.mention_tokens):
                    ctx_tokens[starts] = ctx_tokens[starts] + mention_type_vecs[ent_idx]
                entities_span = entities_open

            ent_att = torch.stack(
                [doc_att[positions].mean(dim=0) for positions in encoded.mention_tokens]
            )  # (E, L)

            head = torch.tensor([p[0] for p in encoded.pairs], device=self.device, dtype=torch.long)
            tail = torch.tensor([p[1] for p in encoded.pairs], device=self.device, dtype=torch.long)
            th, tt = ent_type_ids[head], ent_type_ids[tail]
            same_type_list.append((th == tt).unsqueeze(-1))

            h_open, t_open = entities_open[head], entities_open[tail]
            base_fwd_list.append(
                torch.cat([h_open, t_open, h_open * t_open, types[head], types[tail]], dim=-1)
            )
            base_rev_list.append(
                torch.cat([t_open, h_open, h_open * t_open, types[tail], types[head]], dim=-1)
            )

            joint_att = ent_att[head] * ent_att[tail]  # (P, L)
            joint_att = joint_att / (joint_att.sum(dim=-1, keepdim=True) + 1e-7)
            c_lop = joint_att @ ctx_tokens  # (P, hidden)

            h_span, t_span = entities_span[head], entities_span[tail]
            if encoded.pair_features and len(encoded.pair_features) == len(encoded.pairs):
                c_span = torch.stack(
                    [ctx_tokens[bs:be].mean(dim=0) for bs, be, _, _ in encoded.pair_features]
                )
                dist_ids = torch.tensor(
                    [db for _, _, db, _ in encoded.pair_features],
                    device=self.device,
                    dtype=torch.long,
                )
                cosent_ids = torch.tensor(
                    [cs for _, _, _, cs in encoded.pair_features],
                    device=self.device,
                    dtype=torch.long,
                )
            else:
                c_span = 0.5 * (h_span + t_span)
                dist_ids = torch.zeros(len(encoded.pairs), device=self.device, dtype=torch.long)
                cosent_ids = torch.zeros(len(encoded.pairs), device=self.device, dtype=torch.long)

            cosent_rev_ids = torch.where(
                cosent_ids == 1,
                torch.full_like(cosent_ids, 2),
                torch.where(cosent_ids == 2, torch.ones_like(cosent_ids), cosent_ids),
            )
            dist_e = self.dist_embedding(dist_ids)
            cosent_fwd_e = self.cosent_embedding(cosent_ids)
            cosent_rev_e = self.cosent_embedding(cosent_rev_ids)

            pt_fwd = self.pair_type_embedding(th * len(ENTITY_TYPES) + tt)
            pt_rev = self.pair_type_embedding(tt * len(ENTITY_TYPES) + th)
            gate_fwd = 1.0 + torch.tanh(self.type_gate(pt_fwd))
            gate_rev = 1.0 + torch.tanh(self.type_gate(pt_rev))

            z_h_fwd = nn.functional.gelu(
                self.head_proj(torch.cat([h_span, c_lop, c_span, types[head]], dim=-1))
            )
            z_t_fwd = nn.functional.gelu(
                self.tail_proj(torch.cat([t_span, c_lop, c_span, types[tail]], dim=-1))
            )
            raw_ctx_fwd = torch.cat(
                [
                    c_lop,
                    c_span,
                    z_h_fwd,
                    z_t_fwd,
                    z_h_fwd * z_t_fwd,
                    torch.abs(z_h_fwd - z_t_fwd),
                    dist_e,
                    cosent_fwd_e,
                ],
                dim=-1,
            )
            ctx_fwd_list.append(raw_ctx_fwd * gate_fwd)

            z_h_rev = nn.functional.gelu(
                self.head_proj(torch.cat([t_span, c_lop, c_span, types[tail]], dim=-1))
            )
            z_t_rev = nn.functional.gelu(
                self.tail_proj(torch.cat([h_span, c_lop, c_span, types[head]], dim=-1))
            )
            raw_ctx_rev = torch.cat(
                [
                    c_lop,
                    c_span,
                    z_h_rev,
                    z_t_rev,
                    z_h_rev * z_t_rev,
                    torch.abs(z_h_rev - z_t_rev),
                    dist_e,
                    cosent_rev_e,
                ],
                dim=-1,
            )
            ctx_rev_list.append(raw_ctx_rev * gate_rev)
            mask_offsets.append(type_pair_mask[th, tt] + sym_type_bias[th, tt])

        same_type = torch.cat(same_type_list)
        logits_fwd = self.head(torch.cat(base_fwd_list)) + self.context_head(
            torch.cat(ctx_fwd_list)
        )
        logits_rev = self.head(torch.cat(base_rev_list)) + self.context_head(
            torch.cat(ctx_rev_list)
        )
        logits: torch.Tensor = torch.where(
            same_type, 0.5 * (logits_fwd + logits_rev), logits_fwd
        ) + torch.cat(mask_offsets)
        return logits
