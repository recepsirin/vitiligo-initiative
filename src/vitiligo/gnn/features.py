"""Multimodal feature extractor fusing fine-tuned BiomedBERT, GEO transcriptomics, and GWAS."""

from __future__ import annotations

import csv
import gzip
import math
import sqlite3
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import load_file
from transformers import AutoModel, AutoTokenizer

from vitiligo.gnn.dataset import GraphDataset
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_FEATURE_CACHE = Path("data/cache/gnn/multimodal_node_features.pt")
DEFAULT_BIOMEDBERT_PATH = Path("data/models/relations/biomedbert-silver-gold")
DEFAULT_HGNC_PATH = Path("data/geo/hgnc_complete_set.txt")
DEFAULT_GSE311770_PATH = Path("data/geo/GSE311770/GSE311770_all_samples_rsem_gene_counts.tsv.gz")
DEFAULT_GSE150954_PATH = Path("data/geo/GSE150954/GSE150954_Untreated_v_Treated_MCBG.csv.gz")
DEFAULT_GSE344141_PATH = Path("data/geo/GSE344141/GSE344141_FPKMs_All_Samples.csv.gz")


def load_hgnc_mappings(hgnc_path: Path = DEFAULT_HGNC_PATH) -> dict[str, str]:
    """Map Ensembl gene ID to official HGNC gene symbol."""
    ens_to_symbol: dict[str, str] = {}
    if not hgnc_path.exists():
        logger.warning("HGNC mapping file not found at %s", hgnc_path)
        return ens_to_symbol

    with open(hgnc_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ens = row.get("ensembl_gene_id")
            sym = row.get("symbol")
            if ens and sym:
                ens_to_symbol[ens.strip()] = sym.strip().upper()
    return ens_to_symbol


def extract_geo_target_features(
    db_path: Path = Path("data/vitiligo.db"),
    hgnc_path: Path = DEFAULT_HGNC_PATH,
    gse311770_path: Path = DEFAULT_GSE311770_PATH,
    gse150954_path: Path = DEFAULT_GSE150954_PATH,
    gse344141_path: Path = DEFAULT_GSE344141_PATH,
) -> dict[str, list[float]]:
    """Extract continuous 4D transcriptomic/genomic vector for every gene symbol:

    1. GSE311770: Human lesional vs. unaffected skin log2 fold-change (51 lesions vs 31 controls)
    2. GSE150954: Hair follicle bulge melanocyte stem cell log2 fold-change (treated vs untreated)
    3. GSE344141: Fluoxetine 5-HT1A/Wnt melanocyte activation log2 fold-change
    4. GWAS Risk: Log odds-ratio scaled by -log10(p-value)
    """
    logger.info("Extracting GEO transcriptomics and GWAS risk scores...")
    ens_to_sym = load_hgnc_mappings(hgnc_path)

    # 1. GSE311770: 105 human 1mm biopsies
    gse311770_fc: dict[str, float] = {}
    if gse311770_path.exists():
        with gzip.open(gse311770_path, "rt", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            lesion_cols = [i for i, c in enumerate(header[1:], 1) if "lesioneel" in c]
            ctrl_cols = [i for i, c in enumerate(header[1:], 1) if "gezond" in c or "controle" in c]

            for row in reader:
                ens = row[0].split(".")[0].strip()
                sym = ens_to_sym.get(ens)
                if not sym:
                    continue
                try:
                    l_vals = [float(row[c]) for c in lesion_cols]
                    c_vals = [float(row[c]) for c in ctrl_cols]
                    l_mean = float(np.mean(l_vals))
                    c_mean = float(np.mean(c_vals))
                    log2fc = math.log2((l_mean + 1.0) / (c_mean + 1.0))
                    # Clamp extreme values for stability
                    gse311770_fc[sym] = max(-5.0, min(5.0, log2fc))
                except (ValueError, IndexError):
                    pass

    # 2. GSE150954: Hair-follicle bulge McSCs
    gse150954_fc: dict[str, float] = {}
    if gse150954_path.exists():
        with gzip.open(gse150954_path, "rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Common_name", "").strip().upper()
                if not name:
                    continue
                try:
                    fc = float(row.get("Fold_change", 1.0))
                    log2fc = math.log2(fc) if fc > 0 else 0.0
                    gse150954_fc[name] = max(-5.0, min(5.0, log2fc))
                except (ValueError, KeyError):
                    pass

    # 3. GSE344141: Fluoxetine 5-HT1A McSC activation
    gse344141_fc: dict[str, float] = {}
    if gse344141_path.exists():
        with gzip.open(gse344141_path, "rt", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            ctrl_cols = [i for i, c in enumerate(header) if "Ctrl" in c]
            treat_cols = [i for i, c in enumerate(header) if "RPT" in c]
            for row in reader:
                ens = row[0].strip().split(".")[0]
                sym = ens_to_sym.get(ens)
                if not sym:
                    continue
                try:
                    c_vals = [float(row[c]) for c in ctrl_cols]
                    t_vals = [float(row[c]) for c in treat_cols]
                    c_mean = float(np.mean(c_vals))
                    t_mean = float(np.mean(t_vals))
                    log2fc = math.log2((t_mean + 0.01) / (c_mean + 0.01))
                    gse344141_fc[sym] = max(-5.0, min(5.0, log2fc))
                except (ValueError, IndexError):
                    pass

    # 4. GWAS Catalog risk scores from vitiligo.db
    gwas_scores: dict[str, float] = {}
    if db_path.exists():
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        rows = cur.execute(
            "SELECT mapped_gene, p_value, odds_ratio_or_beta FROM genetic_associations WHERE mapped_gene IS NOT NULL"
        ).fetchall()
        for gene_raw, p, or_val in rows:
            if not gene_raw or not p:
                continue
            for gene in gene_raw.split(","):
                g = gene.strip().upper()
                p_score = -math.log10(max(p, 1e-50))
                or_score = abs(math.log2(max(or_val or 1.0, 0.01)))
                weight = p_score * (1.0 + or_score)
                gwas_scores[g] = max(gwas_scores.get(g, 0.0), weight)
        con.close()

    # Normalize GWAS scores to [0, 5.0]
    max_gwas = max(gwas_scores.values()) if gwas_scores else 1.0
    normalized_gwas = {g: (s / max_gwas) * 5.0 for g, s in gwas_scores.items()}

    # Merge all into 4D vector per gene
    all_genes = set(gse311770_fc.keys()) | set(gse150954_fc.keys()) | set(gse344141_fc.keys()) | set(normalized_gwas.keys())
    target_features: dict[str, list[float]] = {}
    for g in all_genes:
        target_features[g] = [
            gse311770_fc.get(g, 0.0),
            gse150954_fc.get(g, 0.0),
            gse344141_fc.get(g, 0.0),
            normalized_gwas.get(g, 0.0),
        ]

    logger.info("Compiled 4D GEO/GWAS features for %d genes.", len(target_features))
    return target_features


def extract_biomedbert_node_embeddings(
    dataset: GraphDataset,
    biomedbert_dir: Path = DEFAULT_BIOMEDBERT_PATH,
    device: str | None = None,
    batch_size: int = 256,
) -> torch.Tensor:
    """Encode all entity names using the exact fine-tuned BiomedBERT model checkpoint."""
    if device is None:
        device_obj = torch.device(
            "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        )
    else:
        device_obj = torch.device(device)

    logger.info("Encoding %d entities with fine-tuned BiomedBERT on %s...", dataset.num_nodes, device_obj)
    tokenizer = AutoTokenizer.from_pretrained(biomedbert_dir)
    bert = AutoModel.from_pretrained("microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext").to(device_obj)

    # Load fine-tuned weights
    weights_path = biomedbert_dir / "model.safetensors"
    st = load_file(str(weights_path))
    encoder_weights = {k[len("encoder.") :]: v for k, v in st.items() if k.startswith("encoder.")}
    bert.load_state_dict(encoder_weights, strict=False)
    bert.eval()

    all_texts = [e.name for e in dataset.entities]
    embeddings_list: list[torch.Tensor] = []

    with torch.no_grad():
        for i in range(0, len(all_texts), batch_size):
            batch_texts = all_texts[i : i + batch_size]
            inputs = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=64,
                return_tensors="pt",
            ).to(device_obj)
            out = bert(**inputs)
            # Use mean pooling over token embeddings
            mask = inputs["attention_mask"].unsqueeze(-1)
            mean_pooled = (out.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            # L2 normalize
            normalized = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
            embeddings_list.append(normalized.cpu())

    embeddings = torch.cat(embeddings_list, dim=0)
    logger.info("BiomedBERT entity embeddings completed: shape %s", list(embeddings.shape))
    return embeddings


def build_multimodal_node_features(
    dataset: GraphDataset,
    *,
    biomedbert_dir: Path = DEFAULT_BIOMEDBERT_PATH,
    cache_path: Path = DEFAULT_FEATURE_CACHE,
    force_rebuild: bool = False,
    device: str | None = None,
) -> torch.Tensor:
    """Fuse fine-tuned BiomedBERT (768D) with GEO transcriptomics & GWAS (4D) into 772D feature tensor."""
    cache_path = Path(cache_path)
    if not force_rebuild and cache_path.exists():
        try:
            logger.info("Loading cached multimodal node features from %s", cache_path)
            return torch.load(cache_path, weights_only=True)
        except Exception as e:
            logger.warning("Failed to load feature cache (%s); rebuilding...", e)

    # 1. BiomedBERT text features (N, 768)
    bert_features = extract_biomedbert_node_embeddings(dataset, biomedbert_dir=biomedbert_dir, device=device)

    # 2. GEO transcriptomic & GWAS features (N, 4)
    geo_features = extract_geo_target_features()
    geo_tensor = torch.zeros((dataset.num_nodes, 4), dtype=torch.float32)

    for entity in dataset.entities:
        name_key = entity.name.upper()
        if name_key in geo_features:
            geo_tensor[entity.idx] = torch.tensor(geo_features[name_key], dtype=torch.float32)
        elif entity.key.upper() in geo_features:
            geo_tensor[entity.idx] = torch.tensor(geo_features[entity.key.upper()], dtype=torch.float32)

    # 3. Concatenate into multimodal node feature matrix (N, 772)
    multimodal_x = torch.cat([bert_features, geo_tensor], dim=1)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(multimodal_x, cache_path)
    logger.info("Saved multimodal node features (shape %s) to %s", list(multimodal_x.shape), cache_path)
    return multimodal_x
