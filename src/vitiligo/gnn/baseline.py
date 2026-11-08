"""PyKEEN baseline benchmark for relational knowledge graph embeddings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

from vitiligo.gnn.dataset import GraphDataset, load_graph_dataset
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EXPORT_PATH = Path("exports/gnn_baseline_results.json")


@dataclass
class BaselineMetrics:
    model_name: str
    num_triples: int
    num_entities: int
    num_relations: int
    num_epochs: int
    hits_at_1: float
    hits_at_5: float
    hits_at_10: float
    mean_reciprocal_rank: float
    mean_rank: float


def run_kge_baseline(
    dataset: GraphDataset | None = None,
    *,
    model_name: str = "ComplEx",
    num_epochs: int = 25,
    embedding_dim: int = 64,
    batch_size: int = 512,
    random_seed: int = 42,
    export_path: Path | str = DEFAULT_EXPORT_PATH,
) -> BaselineMetrics:
    """Train and evaluate a standard Knowledge Graph Embedding baseline (ComplEx / RotatE / TransE)."""
    if dataset is None:
        dataset = load_graph_dataset()

    logger.info("Extracting %d triples for PyKEEN baseline...", dataset.num_edges)
    src = dataset.edge_index[0].tolist()
    dst = dataset.edge_index[1].tolist()
    rel = dataset.edge_type.tolist()

    labeled_triples = np.array(
        [
            [dataset.entities[u].name, dataset.idx_to_relation[r], dataset.entities[v].name]
            for u, v, r in zip(src, dst, rel, strict=False)
        ]
    )

    tf = TriplesFactory.from_labeled_triples(labeled_triples)
    training, testing = tf.split([0.85, 0.15], random_state=random_seed)

    logger.info(
        "Running %s baseline (epochs=%d, dim=%d, train_triples=%d, test_triples=%d)...",
        model_name,
        num_epochs,
        embedding_dim,
        training.num_triples,
        testing.num_triples,
    )

    result = pipeline(
        training=training,
        testing=testing,
        model=model_name,
        model_kwargs={"embedding_dim": embedding_dim},
        training_kwargs={
            "num_epochs": num_epochs,
            "batch_size": batch_size,
            "use_tqdm": True,
        },
        random_seed=random_seed,
    )

    mrr = float(result.get_metric("mean_reciprocal_rank"))
    hits1 = float(result.get_metric("hits_at_1"))
    hits5 = float(result.get_metric("hits_at_5"))
    hits10 = float(result.get_metric("hits_at_10"))
    mr = float(result.get_metric("mean_rank"))

    metrics = BaselineMetrics(
        model_name=model_name,
        num_triples=len(labeled_triples),
        num_entities=tf.num_entities,
        num_relations=tf.num_relations,
        num_epochs=num_epochs,
        hits_at_1=round(hits1, 4),
        hits_at_5=round(hits5, 4),
        hits_at_10=round(hits10, 4),
        mean_reciprocal_rank=round(mrr, 4),
        mean_rank=round(mr, 2),
    )

    export_path = Path(export_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(asdict(metrics), f, indent=2)

    logger.info(
        "%s Baseline completed: Hits@10=%.4f, MRR=%.4f (saved to %s)",
        model_name,
        metrics.hits_at_10,
        metrics.mean_reciprocal_rank,
        export_path,
    )
    return metrics
