"""Dataset builder and tensor exporter for knowledge graph neural networks."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch_geometric.data import Data, HeteroData

from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path("data/vitiligo.db")
DEFAULT_CACHE_DIR = Path("data/cache/gnn")

PREDICATES = [
    "TREATS",
    "TARGETS",
    "INHIBITS",
    "ACTIVATES",
    "ASSOCIATED_WITH",
    "TESTED_IN",
    "INVESTIGATES",
    "CHANGES",
    "EXPRESSED_IN",
    "OCCURS_IN",
    "CAUSES",
    "COMBINED_WITH",
]

CAUSAL_LEVEL_WEIGHTS: dict[str, float] = {
    "perturbation_in_human": 1.0,
    "perturbation_in_animal": 0.85,
    "perturbation_in_vitro": 0.70,
    "human_genetics": 0.75,
    "association": 0.50,
}


@dataclass(frozen=True)
class EntityMeta:
    idx: int
    db_id: int
    kind: str
    key: str
    name: str


@dataclass
class GraphDataset:
    entities: list[EntityMeta]
    id_to_idx: dict[int, int]
    name_to_idx: dict[str, int]
    key_to_idx: dict[str, int]
    kind_to_indices: dict[str, list[int]]
    relation_to_idx: dict[str, int]
    idx_to_relation: list[str]

    edge_index: torch.Tensor  # shape (2, E)
    edge_type: torch.Tensor   # shape (E,)
    edge_weight: torch.Tensor # shape (E,)

    # Optional node features (fused BiomedBERT + GEO transcriptomics + GWAS)
    node_features: torch.Tensor | None = None
    canonical_drug_indices: list[int] = field(default_factory=list)

    @property
    def num_nodes(self) -> int:
        return len(self.entities)

    @property
    def num_relations(self) -> int:
        return len(self.relation_to_idx)

    @property
    def num_edges(self) -> int:
        return int(self.edge_index.size(1))

    def to_pyg_data(self) -> Data:
        """Return a unified PyTorch Geometric Data object."""
        return Data(
            edge_index=self.edge_index,
            edge_type=self.edge_type,
            edge_weight=self.edge_weight,
            x=self.node_features,
            num_nodes=self.num_nodes,
        )

    def to_hetero_data(self) -> HeteroData:
        """Return a heterogeneous PyTorch Geometric HeteroData object grouped by node/edge types."""
        data = HeteroData()
        # Group node counts
        for kind, indices in self.kind_to_indices.items():
            data[kind].num_nodes = len(indices)

        # Build mapping from global idx to per-kind local idx
        local_mapping: dict[int, int] = {}
        for _kind, indices in self.kind_to_indices.items():
            for local_idx, global_idx in enumerate(indices):
                local_mapping[global_idx] = local_idx

        # Group edges by (src_kind, relation, dst_kind)
        src_nodes = self.edge_index[0].tolist()
        dst_nodes = self.edge_index[1].tolist()
        rel_types = self.edge_type.tolist()
        weights = self.edge_weight.tolist()

        hetero_edges: dict[tuple[str, str, str], tuple[list[int], list[int], list[float]]] = {}
        for u, v, r, w in zip(src_nodes, dst_nodes, rel_types, weights, strict=False):
            u_kind = self.entities[u].kind
            v_kind = self.entities[v].kind
            rel_name = self.idx_to_relation[r]
            edge_key = (u_kind, rel_name, v_kind)
            if edge_key not in hetero_edges:
                hetero_edges[edge_key] = ([], [], [])
            hetero_edges[edge_key][0].append(local_mapping[u])
            hetero_edges[edge_key][1].append(local_mapping[v])
            hetero_edges[edge_key][2].append(w)

        for (u_kind, rel_name, v_kind), (u_list, v_list, w_list) in hetero_edges.items():
            data[u_kind, rel_name, v_kind].edge_index = torch.tensor([u_list, v_list], dtype=torch.long)
            data[u_kind, rel_name, v_kind].edge_weight = torch.tensor(w_list, dtype=torch.float)

        return data

    def export_triples_tsv(self, output_path: Path | str) -> None:
        """Export triples as TSV for PyKEEN or standard KGE benchmarking."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        src = self.edge_index[0].tolist()
        dst = self.edge_index[1].tolist()
        rel = self.edge_type.tolist()

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            for u, v, r in zip(src, dst, rel, strict=False):
                writer.writerow([self.entities[u].name, self.idx_to_relation[r], self.entities[v].name])
        logger.info("Exported %d triples to %s", len(src), output_path)

    def split_edges(
        self,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        seed: int = 42,
    ) -> tuple[GraphDataset, dict[str, torch.Tensor], dict[str, torch.Tensor]]:
        """Split edges into train, validation, and test edge sets."""
        generator = torch.Generator().manual_seed(seed)
        num_edges = self.num_edges
        perm = torch.randperm(num_edges, generator=generator)

        n_val = int(num_edges * val_ratio)
        n_test = int(num_edges * test_ratio)
        n_train = num_edges - n_val - n_test

        train_indices = perm[:n_train]
        val_indices = perm[n_train : n_train + n_val]
        test_indices = perm[n_train + n_val :]

        train_dataset = GraphDataset(
            entities=self.entities,
            id_to_idx=self.id_to_idx,
            name_to_idx=self.name_to_idx,
            key_to_idx=self.key_to_idx,
            kind_to_indices=self.kind_to_indices,
            relation_to_idx=self.relation_to_idx,
            idx_to_relation=self.idx_to_relation,
            edge_index=self.edge_index[:, train_indices],
            edge_type=self.edge_type[train_indices],
            edge_weight=self.edge_weight[train_indices],
            node_features=self.node_features,
            canonical_drug_indices=self.canonical_drug_indices,
        )

        val_edges = {
            "edge_index": self.edge_index[:, val_indices],
            "edge_type": self.edge_type[val_indices],
            "edge_weight": self.edge_weight[val_indices],
        }
        test_edges = {
            "edge_index": self.edge_index[:, test_indices],
            "edge_type": self.edge_type[test_indices],
            "edge_weight": self.edge_weight[test_indices],
        }

        return train_dataset, val_edges, test_edges


def compute_causal_edge_weight(
    claim: str | None,
    causal_level: str | None,
    confidence: float,
    predicate: str | None = None,
) -> float:
    """Compute continuous scalar edge weight incorporating causal ladder, predicate semantics, and confidence."""
    claim_upper = (claim or "ASSERTED").upper()

    # Moderate adverse event clinical trial listings (CHANGES) to prevent overpowering mechanism signals
    if predicate == "CHANGES":
        return 0.30

    # Boost verified pharmacological mechanisms (TREATS, INHIBITS, ACTIVATES, TARGETS)
    if predicate in ("TREATS", "TARGETS", "INHIBITS", "ACTIVATES"):
        if claim_upper == "OBSERVED":
            return 1.0
        return max(0.60, float(confidence) * 0.90)

    if claim_upper == "OBSERVED":
        if causal_level and causal_level in CAUSAL_LEVEL_WEIGHTS:
            return float(CAUSAL_LEVEL_WEIGHTS[causal_level])
        return max(0.65, float(confidence))
    # ASSERTED: scale down by confidence
    return max(0.20, float(confidence) * 0.50)


def load_graph_dataset(
    db_path: Path | str = DEFAULT_DB_PATH,
    *,
    cache_path: Path | str | None = None,
    force_reload: bool = False,
) -> GraphDataset:
    """Load graph entities and edges from SQLite, constructing a GraphDataset."""
    db_path = Path(db_path)
    if cache_path is None:
        cache_path = DEFAULT_CACHE_DIR / "vitiligo_gnn_dataset.pt"
    cache_path = Path(cache_path)

    if not force_reload and cache_path.exists():
        try:
            logger.info("Loading cached GNN dataset from %s", cache_path)
            data_dict = torch.load(cache_path, weights_only=False)
            return GraphDataset(**data_dict)
        except Exception as e:
            logger.warning("Failed to load cache (%s); rebuilding from %s", e, db_path)

    logger.info("Building GNN dataset from %s", db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # 1. Fetch entities
    entity_rows = cur.execute(
        "SELECT id, kind, key, name, external_ids FROM graph_entities ORDER BY id"
    ).fetchall()

    entities: list[EntityMeta] = []
    id_to_idx: dict[int, int] = {}
    name_to_idx: dict[str, int] = {}
    key_to_idx: dict[str, int] = {}
    kind_to_indices: dict[str, list[int]] = {}
    canonical_drug_indices: list[int] = []

    for idx, (db_id, kind, key, name, ext_raw) in enumerate(entity_rows):
        meta = EntityMeta(idx=idx, db_id=db_id, kind=kind, key=key, name=name)
        entities.append(meta)
        id_to_idx[db_id] = idx
        name_to_idx[name] = idx
        name_to_idx[name.lower()] = idx
        key_to_idx[key] = idx
        kind_to_indices.setdefault(kind, []).append(idx)

        if kind == "DRUG":
            ext = json.loads(ext_raw) if ext_raw else {}
            has_id = any(k in ext for k in ["mesh", "drugbank", "opentargets", "pubchem", "chembl"])
            name_l = name.lower()
            not_artifact = not any(w in name_l for w in ["placebo", "vehicle", "sham", "control", ":n/a;", "unspecified"])
            if has_id and not_artifact:
                canonical_drug_indices.append(idx)

    # 2. Map predicates
    pred_set = list(PREDICATES)
    # Check for any unexpected predicates in database
    db_preds = [
        r[0] for r in cur.execute("SELECT DISTINCT predicate FROM graph_edges").fetchall()
    ]
    for p in db_preds:
        if p not in pred_set:
            pred_set.append(p)

    rel_to_idx = {p: i for i, p in enumerate(pred_set)}
    idx_to_rel = pred_set

    # 3. Fetch edges
    edge_rows = cur.execute(
        "SELECT subject_id, predicate, object_id, confidence, claim, causal_level FROM graph_edges"
    ).fetchall()

    src_list: list[int] = []
    dst_list: list[int] = []
    rel_list: list[int] = []
    w_list: list[float] = []

    for s_id, pred, o_id, conf, claim, causal in edge_rows:
        if s_id not in id_to_idx or o_id not in id_to_idx:
            continue
        u = id_to_idx[s_id]
        v = id_to_idx[o_id]
        r = rel_to_idx[pred]
        w = compute_causal_edge_weight(claim, causal, conf or 0.5, predicate=pred)

        src_list.append(u)
        dst_list.append(v)
        rel_list.append(r)
        w_list.append(w)

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
    edge_type = torch.tensor(rel_list, dtype=torch.long)
    edge_weight = torch.tensor(w_list, dtype=torch.float)

    # 4. Attach multimodal node features if cached
    feature_cache = Path("data/cache/gnn/multimodal_node_features.pt")
    node_features: torch.Tensor | None = None
    if feature_cache.exists():
        try:
            node_features = torch.load(feature_cache, weights_only=True)
            logger.info("Loaded multimodal node features from %s", feature_cache)
        except Exception as e:
            logger.warning("Could not load multimodal feature cache: %s", e)

    dataset = GraphDataset(
        entities=entities,
        id_to_idx=id_to_idx,
        name_to_idx=name_to_idx,
        key_to_idx=key_to_idx,
        kind_to_indices=kind_to_indices,
        relation_to_idx=rel_to_idx,
        idx_to_relation=idx_to_rel,
        edge_index=edge_index,
        edge_type=edge_type,
        edge_weight=edge_weight,
        node_features=node_features,
        canonical_drug_indices=canonical_drug_indices,
    )

    # Save to cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "entities": dataset.entities,
            "id_to_idx": dataset.id_to_idx,
            "name_to_idx": dataset.name_to_idx,
            "key_to_idx": dataset.key_to_idx,
            "kind_to_indices": dataset.kind_to_indices,
            "relation_to_idx": dataset.relation_to_idx,
            "idx_to_relation": dataset.idx_to_relation,
            "edge_index": dataset.edge_index,
            "edge_type": dataset.edge_type,
            "edge_weight": dataset.edge_weight,
            "node_features": dataset.node_features,
            "canonical_drug_indices": dataset.canonical_drug_indices,
        },
        cache_path,
    )
    logger.info("Saved GNN dataset cache to %s (%d nodes, %d edges)", cache_path, dataset.num_nodes, dataset.num_edges)
    return dataset
