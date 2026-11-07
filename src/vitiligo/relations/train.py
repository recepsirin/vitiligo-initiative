"""Training the relation model, and judging it the way BioRED is judged.

A prediction counts when its entity pair and its relation type both match a
gold relation; precision, recall and F1 are over those, micro-averaged, as in
the BioRED paper's relation-type evaluation with given entities. One number is
tuned, on the development split only: how much more the model must believe in
a relation than in none before it says so. The test split is scored once, at
the end, with that number fixed.
"""

from __future__ import annotations

import hashlib
import math
import random
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
from torch import nn

from vitiligo.logging import get_logger
from vitiligo.relations.data import LABELS, Encoded
from vitiligo.relations.model import RelationModel
from vitiligo.relations.scoring import Key, Score, gold_keys, score, untyped

logger = get_logger(__name__)


def pubtator_held_out(pmid: str) -> bool:
    """One abstract in twenty, fixed by its PMID, that silver training never sees.

    Agreement with PubTator on these says how the model reads this corpus,
    which BioRED's general abstracts cannot.
    """
    return int(hashlib.sha256(pmid.encode()).hexdigest(), 16) % 20 == 0


def pubtator_split(kind: str) -> list[Any]:
    """PubTator's abstracts here, held out or not, with only the relations it is sure of."""
    from dataclasses import replace

    from vitiligo.sources.biored import SPLITS, load_split
    from vitiligo.sources.pubtator import cached_documents

    biored = {d.pmid for split in SPLITS for d in load_split(split)}
    held_out = kind == "held-out"
    return [
        replace(d, relations=tuple(r for r in d.relations if r.score >= 0.5))
        for d in cached_documents(kind="abstracts")
        if d.pmid not in biored and pubtator_held_out(d.pmid) == held_out
    ]


def device() -> torch.device:
    return torch.device("mps" if torch.backends.mps.is_available() else "cpu")


@torch.no_grad()
def logits_for(
    model: RelationModel, encoded: Sequence[Encoded], batch_size: int = 8
) -> list[torch.Tensor]:
    """Per input, the logits of each of its candidate pairs, on the CPU."""
    model.eval()
    out: list[torch.Tensor] = []
    for start in range(0, len(encoded), batch_size):
        batch = encoded[start : start + batch_size]
        logits = model(batch).float().cpu()
        cursor = 0
        for item in batch:
            out.append(logits[cursor : cursor + len(item.pairs)])
            cursor += len(item.pairs)
    return out


def predicted_keys(
    encoded: Sequence[Encoded], logits: Sequence[torch.Tensor], bias: float
) -> set[Key]:
    keys: set[Key] = set()
    for item, values in zip(encoded, logits, strict=True):
        shifted = values.clone()
        shifted[:, 0] += bias
        for (i, j), label in zip(item.pairs, shifted.argmax(dim=-1).tolist(), strict=True):
            if label:
                a, b = sorted((item.entities[i], item.entities[j]))
                keys.add((item.unit.doc_id, a, b, LABELS[label]))
    return keys


def tune_bias(
    encoded: Sequence[Encoded], logits: Sequence[torch.Tensor], gold: set[Key]
) -> tuple[float, Score]:
    """The shift on "no relation" that gives the best F1 on these documents."""
    best = (0.0, score(gold, predicted_keys(encoded, logits, 0.0)))
    for step in range(-30, 31):
        bias = step / 5
        result = score(gold, predicted_keys(encoded, logits, bias))
        if result.f1 > best[1].f1:
            best = (bias, result)
    return best


def fit(
    model: RelationModel,
    train: Sequence[Encoded],
    dev: Sequence[Encoded],
    dev_gold: set[Key],
    *,
    epochs: int,
    encoder_lr: float,
    head_lr: float = 1e-4,
    batch_size: int = 4,
    warmup: float = 0.1,
    seed: int = 13,
    log_every: int = 50,
) -> tuple[dict[str, torch.Tensor], float, list[dict[str, Any]]]:
    """Train, scoring dev after each epoch; returns the best epoch's weights and bias."""
    random.seed(seed)
    torch.manual_seed(seed)
    encoder_params = [p for n, p in model.named_parameters() if n.startswith("encoder.")]
    other_params = [p for n, p in model.named_parameters() if not n.startswith("encoder.")]
    optimizer = torch.optim.AdamW(
        [
            {"params": encoder_params, "lr": encoder_lr},
            {"params": other_params, "lr": head_lr},
        ],
        weight_decay=0.01,
    )
    steps = epochs * math.ceil(len(train) / batch_size)
    warm = max(1, int(steps * warmup))

    def schedule(step: int) -> float:
        if step < warm:
            return (step + 1) / warm
        return max(0.0, (steps - step) / max(1, steps - warm))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, schedule)
    loss_fn = nn.CrossEntropyLoss()
    history: list[dict[str, Any]] = []
    best_state: dict[str, torch.Tensor] = {}
    best_bias, best_f1 = 0.0, -1.0
    order = list(range(len(train)))
    step = 0
    for epoch in range(1, epochs + 1):
        model.train()
        random.shuffle(order)
        started, running = time.time(), 0.0
        for start in range(0, len(order), batch_size):
            batch = [train[i] for i in order[start : start + batch_size]]
            labels = torch.tensor(
                [label for item in batch for label in item.labels], device=model.device
            )
            loss = loss_fn(model(batch), labels)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            step += 1
            running += float(loss)
            if step % log_every == 0:
                logger.info(
                    "epoch %d step %d/%d loss %.4f", epoch, step, steps, running / log_every
                )
                running = 0.0
        bias, result = tune_bias(dev, logits_for(model, dev), dev_gold)
        history.append(
            {
                "epoch": epoch,
                "seconds": round(time.time() - started),
                "bias": bias,
                **asdict(result),
            }
        )
        logger.info(
            "epoch %d: dev P %.3f R %.3f F1 %.3f (bias %.1f) in %ds",
            epoch,
            result.precision,
            result.recall,
            result.f1,
            bias,
            time.time() - started,
        )
        if result.f1 > best_f1:
            best_f1, best_bias = result.f1, bias
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    return best_state, best_bias, history


def save(model: RelationModel, bias: float, path: Path, **meta: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state": model.state_dict(),
            "encoder": model.encoder_name,
            "bias": bias,
            "labels": LABELS,
            "special": (model.cls_id, model.sep_id, model.pad_id),
            **meta,
        },
        path,
    )


def load(path: Path) -> tuple[RelationModel, float, dict[str, Any]]:
    saved: dict[str, Any] = torch.load(path, map_location="cpu", weights_only=False)
    if tuple(saved["labels"]) != LABELS:
        raise ValueError(f"{path} was trained on other labels: {saved['labels']}")
    cls_id, sep_id, pad_id = saved["special"]
    model = RelationModel(saved["encoder"], cls_id=cls_id, sep_id=sep_id, pad_id=pad_id)
    model.load_state_dict(saved["state"])
    return model.to(device()), float(saved["bias"]), saved


def _encoded(documents: Iterable[Any], tokenizer: Any) -> list[Encoded]:
    from vitiligo.relations.data import document_unit, encode

    return [e for d in documents if (e := encode(document_unit(d), tokenizer)) is not None]


def train_model(
    encoder: str,
    out: Path,
    *,
    epochs: int,
    encoder_lr: float,
    silver: bool = False,
    init: Path | None = None,
) -> dict[str, Any]:
    """Train on BioRED's training split, or first on PubTator's reading of this corpus.

    ``silver`` trains on the abstracts PubTator annotated here instead, leaving
    out any BioRED abstract, so that its test split stays unseen, and one in
    twenty of the rest, where agreement with PubTator is measured; ``init`` starts
    from earlier weights, so silver training can be followed by gold. Either
    way the development split chooses the epoch and the bias.
    """
    from transformers import AutoTokenizer

    from vitiligo.sources.biored import load_split

    tokenizer = AutoTokenizer.from_pretrained(encoder)
    dev_documents = load_split("Dev")
    dev = _encoded(dev_documents, tokenizer)
    if silver:
        train = _encoded(pubtator_split("training"), tokenizer)
    else:
        train = _encoded(load_split("Train"), tokenizer)
    logger.info(
        "Training %s on %d inputs (%s)", encoder, len(train), "silver" if silver else "gold"
    )
    model = RelationModel(
        encoder,
        cls_id=tokenizer.cls_token_id,
        sep_id=tokenizer.sep_token_id,
        pad_id=tokenizer.pad_token_id,
    )
    if init is not None:
        model.load_state_dict(torch.load(init, map_location="cpu", weights_only=False)["state"])
    model.to(device())
    state, bias, history = fit(
        model, train, dev, gold_keys(dev_documents), epochs=epochs, encoder_lr=encoder_lr
    )
    model.load_state_dict(state)
    save(model, bias, out, history=history, silver=silver, init=str(init) if init else None)
    return max(history, key=lambda h: h["f1"])


def evaluate_model(path: Path, split: str = "Test") -> dict[str, Score]:
    """A saved model's score on a BioRED split, or its agreement with PubTator.

    ``split`` "PubTator" scores it against PubTator's own relations in the
    held-out abstracts of this corpus. The bias is the one development fixed.
    """
    from transformers import AutoTokenizer

    from vitiligo.sources.biored import load_split

    model, bias, saved = load(path)
    tokenizer = AutoTokenizer.from_pretrained(saved["encoder"])
    documents = pubtator_split("held-out") if split == "PubTator" else load_split(split)
    encoded = _encoded(documents, tokenizer)
    predicted = predicted_keys(encoded, logits_for(model, encoded), bias)
    gold = gold_keys(documents)
    return {"relation": score(gold, predicted), "pair": score(untyped(gold), untyped(predicted))}
