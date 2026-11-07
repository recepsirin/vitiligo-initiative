"""An encoder that reads a text once and classifies every entity pair in it.

The text is encoded once; each entity is the log-sum-exp of the states at its
mentions' opening markers, so a concept mentioned five times is not five
inputs; and each pair is classified from the two entities and their types.
Reading once per text rather than once per pair is what makes the full texts
affordable on one machine: a passage with thirty entities has 435 pairs and
still costs one forward pass. (The design is ATLOP's, Zhou et al. 2021,
without its context pooling.)

A text longer than the encoder's window is read in overlapping windows and a
token takes the mean of the states it was given.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import torch
from torch import nn
from transformers import AutoConfig, AutoModel

from vitiligo.relations.data import ENTITY_TYPES, LABELS, WINDOW, Encoded, window_starts


class RelationModel(nn.Module):
    def __init__(
        self, encoder: str, *, cls_id: int, sep_id: int, pad_id: int, pretrained: bool = True
    ) -> None:
        super().__init__()
        self.encoder_name = encoder
        # Explicitly float32: transformers 5 loads a checkpoint in the precision it
        # was saved in, which for DeBERTa-v3 is float16, and the first optimiser
        # step in float16 overflows every weight to NaN. A saved model holds every
        # encoder weight, so loading one needs only the encoder's shape.
        config = AutoConfig.from_pretrained(encoder)
        self.encoder: Any = (
            AutoModel.from_pretrained(encoder, dtype=torch.float32)
            if pretrained
            else AutoModel.from_config(config, dtype=torch.float32)  # type: ignore[no-untyped-call]
        )
        hidden = int(self.encoder.config.hidden_size)
        self.type_embedding = nn.Embedding(len(ENTITY_TYPES), 64)
        self.head = nn.Sequential(
            nn.Linear(3 * hidden + 128, hidden),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden, len(LABELS)),
        )
        self.cls_id, self.sep_id, self.pad_id = cls_id, sep_id, pad_id

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    def token_states(self, documents: Sequence[list[int]]) -> list[torch.Tensor]:
        """Each document's token states, its windows stitched back together."""
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
        out = self.encoder(
            input_ids=ids.to(self.device), attention_mask=mask.to(self.device)
        ).last_hidden_state
        hidden = out.shape[-1]
        sums = [out.new_zeros((len(d), hidden)) for d in documents]
        counts = [out.new_zeros((len(d), 1)) for d in documents]
        for row, (index, start, n) in enumerate(owners):
            sums[index][start : start + n] += out[row, 1 : 1 + n]
            counts[index][start : start + n] += 1
        return [s / c.clamp(min=1) for s, c in zip(sums, counts, strict=True)]

    def forward(self, batch: Sequence[Encoded]) -> torch.Tensor:
        """Logits over LABELS for every candidate pair in the batch, in order."""
        states = self.token_states([e.input_ids for e in batch])
        features: list[torch.Tensor] = []
        for encoded, tokens in zip(batch, states, strict=True):
            entities = torch.stack(
                [torch.logsumexp(tokens[positions], dim=0) for positions in encoded.mention_tokens]
            )
            types = self.type_embedding(
                torch.tensor(encoded.entity_types, device=self.device, dtype=torch.long)
            )
            head = torch.tensor([p[0] for p in encoded.pairs], device=self.device)
            tail = torch.tensor([p[1] for p in encoded.pairs], device=self.device)
            h, t = entities[head], entities[tail]
            features.append(torch.cat([h, t, h * t, types[head], types[tail]], dim=-1))
        logits: torch.Tensor = self.head(torch.cat(features))
        return logits
