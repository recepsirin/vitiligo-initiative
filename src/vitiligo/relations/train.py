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
import json
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
    if held_out:
        return [
            replace(d, relations=tuple(r for r in d.relations if r.score >= 0.5))
            for d in cached_documents(kind="abstracts")
            if d.pmid not in biored and pubtator_held_out(d.pmid)
        ]
    out: list[Any] = []
    for d in cached_documents(kind="abstracts"):
        if d.pmid in biored or pubtator_held_out(d.pmid):
            continue
        if not any(r.score >= 0.5 for r in d.relations):
            continue
        rels = tuple(
            r if r.score >= 0.5 else replace(r, score=1.0, type="Ignore")
            for r in d.relations
            if r.score > 0
        )
        out.append(replace(d, relations=rels))
    return out


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
    for step in range(-45, 46):
        bias = round(step / 10, 2)
        result = score(gold, predicted_keys(encoded, logits, bias))
        if result.f1 > best[1].f1:
            best = (bias, result)
    return best


def _at_loss(logits: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
    """Adaptive thresholding loss (Zhou et al., 2021) where class 0 ('None') is the threshold TH."""
    valid = labels >= 0
    if not valid.any():
        return logits.new_tensor(0.0)
    logits = logits[valid]
    labels = labels[valid]
    pos_mask = labels > 0
    loss = logits.new_tensor(0.0)
    if pos_mask.any():
        pos_logits = logits[pos_mask]
        pos_labels = labels[pos_mask]
        th_logit = pos_logits[:, 0]
        target_logit = pos_logits.gather(1, pos_labels.unsqueeze(1)).squeeze(1)
        # Positive class must exceed TH
        p_loss = torch.nn.functional.softplus(th_logit - target_logit).mean()
        # Other classes (including TH) must be dominated by TH
        other_mask = torch.ones_like(pos_logits, dtype=torch.bool)
        other_mask.scatter_(1, pos_labels.unsqueeze(1), False)
        neg_part = pos_logits.masked_fill(~other_mask, -1e4)
        n_loss = (torch.logsumexp(neg_part, dim=-1) - th_logit).mean()
        loss = loss + 0.5 * (p_loss + n_loss)
    neg_mask = ~pos_mask
    if neg_mask.any():
        neg_logits = logits[neg_mask]
        loss = loss + (torch.logsumexp(neg_logits, dim=-1) - neg_logits[:, 0]).mean()
    return loss


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
    class_weights = torch.tensor(
        [1.0, 1.0, 1.05, 1.05, 2.8, 1.8, 1.3, 1.5, 1.0],
        device=model.device,
        dtype=torch.float32,
    )
    loss_fn = nn.CrossEntropyLoss(weight=class_weights, ignore_index=-100)
    history: list[dict[str, Any]] = []
    best_state: dict[str, torch.Tensor] = {}
    best_bias, best_f1 = 0.0, -1.0
    top_states: list[tuple[float, dict[str, torch.Tensor]]] = []
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
            pred_logits = model(batch)
            loss = 0.70 * loss_fn(pred_logits, labels) + 0.30 * _at_loss(pred_logits, labels)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            step += 1
            running += float(loss.detach())
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
        cur_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        top_states.append((result.f1, cur_state))
        top_states.sort(key=lambda x: x[0], reverse=True)
        del top_states[3:]
        if result.f1 > best_f1:
            best_f1, best_bias = result.f1, bias
            best_state = cur_state

    for k_soup in (2, 3):
        if len(top_states) >= k_soup:
            soup_state = {
                key: torch.stack([s[key].float() for _, s in top_states[:k_soup]])
                .mean(dim=0)
                .to(top_states[0][1][key].dtype)
                for key in top_states[0][1]
            }
            model.load_state_dict(soup_state)
            soup_bias, soup_res = tune_bias(dev, logits_for(model, dev), dev_gold)
            logger.info(
                "checkpoint soup (top-%d): dev P %.3f R %.3f F1 %.3f (bias %.1f)",
                k_soup,
                soup_res.precision,
                soup_res.recall,
                soup_res.f1,
                soup_bias,
            )
            if soup_res.f1 > best_f1:
                best_f1, best_bias = soup_res.f1, soup_bias
                best_state = soup_state
    return best_state, best_bias, history


WEIGHTS = "model.safetensors"
SETTINGS = "relations.json"


def save(model: RelationModel, bias: float, path: Path, tokenizer: Any, **meta: Any) -> None:
    """A directory Hugging Face can host as it is.

    The weights are safetensors, which hold tensors and nothing else; a pickled
    checkpoint runs whatever code it carries when it is loaded. Beside them go
    the encoder's config and tokenizer, so loading needs nothing from the
    encoder's own repository, and this model's settings.
    """
    from safetensors.torch import save_file

    path.mkdir(parents=True, exist_ok=True)
    save_file({k: v.contiguous() for k, v in model.state_dict().items()}, str(path / WEIGHTS))
    model.encoder.config.save_pretrained(path)
    tokenizer.save_pretrained(path)
    settings = {
        "base_model": model.encoder_name,
        "bias": bias,
        "labels": list(LABELS),
        "special": [model.cls_id, model.sep_id, model.pad_id],
        **meta,
    }
    (path / SETTINGS).write_text(json.dumps(settings, indent=2) + "\n")


def resolve(source: str | Path) -> Path:
    """A saved model's directory: a local one, or a Hugging Face model id.

    ``id@revision`` pins the id to one commit of its repository, so a model
    cannot change under a run that names it.
    """
    if Path(source).is_dir():
        return Path(source)
    from huggingface_hub import snapshot_download

    repo_id, _, revision = str(source).partition("@")
    return Path(snapshot_download(repo_id, revision=revision or None))


def load(source: str | Path) -> tuple[RelationModel, float, dict[str, Any]]:
    """A model saved by :func:`save`; ``encoder`` in the settings is where its tokenizer is."""
    from safetensors.torch import load_file

    path = resolve(source)
    settings: dict[str, Any] = json.loads((path / SETTINGS).read_text())
    if tuple(settings["labels"]) != LABELS:
        raise ValueError(f"{source} was trained on other labels: {settings['labels']}")
    cls_id, sep_id, pad_id = settings["special"]
    model = RelationModel(str(path), cls_id=cls_id, sep_id=sep_id, pad_id=pad_id, pretrained=False)
    model.load_state_dict(load_file(str(path / WEIGHTS)), strict=False)
    model.encoder_name = settings["base_model"]
    return model.to(device()), float(settings["bias"]), {**settings, "encoder": str(path)}


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
    augmented: bool = False,
    init: Path | None = None,
) -> dict[str, Any]:
    """Train on BioRED's training split, or first on PubTator's reading of this corpus.

    ``silver`` trains on the abstracts PubTator annotated here instead, leaving
    out any BioRED abstract, so that its test split stays unseen, and one in
    twenty of the rest, where agreement with PubTator is measured; ``augmented``
    trains on BioRED Train combined with external gold datasets (BC5CDR, ChemProt);
    ``init`` starts from earlier weights, so silver training can be followed by gold.
    Either way the development split chooses the epoch and the bias.
    """
    from transformers import AutoTokenizer

    from vitiligo.sources.biored import load_split

    tokenizer = AutoTokenizer.from_pretrained(encoder)
    dev_documents = load_split("Dev")
    dev = _encoded(dev_documents, tokenizer)
    if silver:
        train = _encoded(pubtator_split("training"), tokenizer)
    elif augmented:
        from vitiligo.sources.external_gold import load_augmented_training

        train = _encoded(load_augmented_training(), tokenizer)
    else:
        train = _encoded(load_split("Train"), tokenizer)
    logger.info(
        "Training %s on %d inputs (%s)",
        encoder,
        len(train),
        "silver" if silver else ("augmented gold" if augmented else "gold"),
    )
    model = RelationModel(
        encoder,
        cls_id=tokenizer.cls_token_id,
        sep_id=tokenizer.sep_token_id,
        pad_id=tokenizer.pad_token_id,
    )
    if init is not None:
        if Path(init).is_file():
            ckpt = torch.load(Path(init), map_location="cpu", weights_only=False)
            state_to_load = ckpt["state"] if isinstance(ckpt, dict) and "state" in ckpt else ckpt
            model.load_state_dict(state_to_load, strict=False)
        else:
            from safetensors.torch import load_file

            model.load_state_dict(load_file(str(resolve(init) / WEIGHTS)), strict=False)
    model.to(device())
    state, bias, history = fit(
        model, train, dev, gold_keys(dev_documents), epochs=epochs, encoder_lr=encoder_lr
    )
    model.load_state_dict(state)
    save(
        model,
        bias,
        out,
        tokenizer,
        history=history,
        silver=silver,
        init=str(init) if init else None,
    )
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
