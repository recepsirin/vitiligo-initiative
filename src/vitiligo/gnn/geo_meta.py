"""Cross-cohort transcriptomics meta-analysis and functional co-expression network mining across 54 GEO datasets.

Ingests multi-cohort human vitiligo biopsies, melanocyte cultures, and targeted interventions:
1. GSE311770 (105 human punch biopsies: lesional vs perilesional vs non-lesional healthy skin).
2. GSE186928 (5 paired patients: NP1-5 normal skin vs VP1-5 active vitiligo skin).
3. GSE256271 (Paired responder vs non-responder RNA-seq identifying the +9.09 log2FC PDE4B barrier).
4. GSE272551 (Selective PDE4 inhibitor Crisaborole 72h response vs DMSO).
5. GSE150954 (Melanocyte stem cell bulge mobilization and activation).
6. GSE344141 (Serotonergic 5-HT1A McSC differentiation signature).
7. GSE171161 (Pmel autoreactive skin-resident memory T-cell transcriptomes).

Outputs:
- A 16-D consensus cross-cohort transcriptomic profile for all target entities.
- A functional gene-gene co-expression interaction network (|r| >= 0.70, p < 1e-5) directly measured from human vitiligo skin.
"""

from __future__ import annotations

import csv
import gzip
import re
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from vitiligo.gnn.dataset import GraphDataset, load_graph_dataset
from vitiligo.logging import get_logger

logger = get_logger(__name__)

HGNC_PATH = Path("data/geo/hgnc_complete_set.txt")
GSE311770_PATH = Path("data/geo/GSE311770/GSE311770_all_samples_rsem_gene_counts.tsv.gz")
GSE186928_DIR = Path("data/geo/GSE186928")
GSE256271_PATH = Path("data/geo/GSE256271/GSE256271_deseq_table_Normalized_all_IE_Final.csv.gz")
GSE272551_CRISA = Path("data/geo/GSE272551/GSE272551_Crisa_vs_DMSO_72h_CSV.csv.gz")
GSE272551_PDE4 = Path("data/geo/GSE272551/GSE272551_PDE4_vs_DMSO_72h_CSV.csv.gz")
GSE150954_MC = Path("data/geo/GSE150954/GSE150954_Untreated_v_Treated_MCBG.csv.gz")
GSE150954_KC = Path("data/geo/GSE150954/GSE150954_Untreated_v_Treated_KCBG.csv.gz")
GSE344141_PATH = Path("data/geo/GSE344141/GSE344141_FPKMs_All_Samples.csv.gz")
GSE171161_PATH = Path("data/geo/GSE171161/GSE171161_Pmel_Memory_counts.txt.gz")
GSE344141_SYMBOLS = Path("data/geo/GSE344141/ensembl_mouse_symbols.tsv")
_MYGENE_QUERY = "https://mygene.info/v3/query"

DEFAULT_BASE_DATASET_PATH = Path("data/cache/gnn/vitiligo_gnn_dataset.pt")
DEFAULT_GEO_CONSENSUS_PATH = Path("data/cache/gnn/geo_consensus_16d.pt")
DEFAULT_COEXPRESSION_PATH = Path("data/cache/gnn/coexpression_edges.pt")
DEFAULT_ENRICHED_DATASET_PATH = Path("data/cache/gnn/vitiligo_gnn_dataset_enriched.pt")

GEO_FEATURE_DIM = 16
# What each GEO dimension holds as extract_multi_cohort_expression_signatures fills it.
GEO_DIMENSIONS = (
    "GSE311770 lesional vs healthy log2FC, blended with the project's limma results",
    "GSE311770 perilesional vs healthy log2FC",
    "GSE311770 baseline mean expression (log2 CPM)",
    "GSE311770 between-patient variance (SD of log2 CPM)",
    "GSE186928 paired normal vs vitiligo log2FC",
    "GSE186928 significance (-log10 q)",
    "GSE256271 non-responder vs responder log2FC",
    "GSE256271 significance (-log10 padj)",
    "GSE272551 crisaborole 72 h log2FC",
    "GSE272551 pan-PDE4 inhibitor 72 h log2FC",
    "GSE150954 bulge melanocyte stem-cell log2FC",
    "GSE150954 bulge keratinocyte stem-cell log2FC",
    "GSE344141 fluoxetine vs control log2FC (mouse skin; 5-HT1A)",
    "GSE298871 single-cell T-cell effector score (11 TRM markers set to at least 2.5)",
    "GSE298871 single-cell melanocyte depletion score (7 markers set to at most -2.5)",
    "GWAS Catalog risk-locus score",
)
# The node-feature matrix the graph model reads: 768 + 1,024 + 128 + 16 = 1,936 columns.
FEATURE_BLOCKS = (
    ("BiomedBERT name embedding", 0, 768),
    ("Morgan fingerprint", 768, 1792),
    ("HGNC gene groups", 1792, 1920),
    ("GEO profile", 1920, 1936),
)


def gse150954_log2fc(path: Path) -> dict[str, float]:
    """Each gene's log2 change, NB-UVB-treated over untreated bulge precursors.

    The file signs its linear fold change: 2.04 is treated over untreated, -2.82
    untreated over treated (on the 11,908 melanocyte genes with both means above
    1, the signed log2 equals log2 of the means' ratio, r = 1.000). A gene counts
    where its mean is at least 1 in either arm, as in GSE344141; a symbol written
    twice keeps its first row.
    """
    with gzip.open(path, "rt") as f:
        df = pd.read_csv(
            f, usecols=["Common_name", "Control_mean", "Treatment_mean", "Fold_change"]
        )
    expressed = df[(df["Control_mean"] >= 1) | (df["Treatment_mean"] >= 1)].dropna()
    changes: dict[str, float] = {}
    for name, fold in expressed[["Common_name", "Fold_change"]].itertuples(index=False):
        if fold:
            changes.setdefault(
                str(name).strip().upper(), float(np.sign(fold) * np.log2(max(abs(fold), 1.0)))
            )
    return changes


def mouse_symbols(ids: list[str], cache: Path = GSE344141_SYMBOLS) -> dict[str, str]:
    """Mouse Ensembl gene ids' symbols: from MyGene.info once, then from ``cache``."""
    held: dict[str, str] = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            ensembl, _, symbol = line.partition("\t")
            held[ensembl] = symbol
    missing = [i for i in dict.fromkeys(ids) if i not in held]
    if missing:
        import httpx

        for start in range(0, len(missing), 1000):
            batch = missing[start : start + 1000]
            response = httpx.post(
                _MYGENE_QUERY,
                data={
                    "q": ",".join(batch),
                    "scopes": "ensembl.gene",
                    "fields": "symbol",
                    "species": "mouse",
                },
                timeout=120,
            )
            response.raise_for_status()
            for hit in response.json():
                held.setdefault(
                    str(hit["query"]), "" if hit.get("notfound") else str(hit.get("symbol") or "")
                )
            for ensembl in batch:
                held.setdefault(ensembl, "")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text("".join(f"{k}\t{v}\n" for k, v in sorted(held.items())), encoding="utf-8")
    return {k: v for k, v in held.items() if v}


def gse344141_log2fc(path: Path, symbols_cache: Path = GSE344141_SYMBOLS) -> dict[str, float]:
    """Each gene's log2 change in mouse skin on fluoxetine over control (GSE344141).

    Fluoxetine acts through the epithelial 5-HT1A receptor, as the series' title
    says. A gene counts where expressed at FPKM >= 1 in either arm, its mouse
    symbol written the human way (Sox17 is SOX17); a symbol two ids share takes
    the more expressed one.
    """
    with gzip.open(path, "rt") as f:
        df = pd.read_csv(f)
    control = df.filter(like="Ctrl_").mean(axis=1)
    fluoxetine = df.filter(like="Flu_").mean(axis=1)
    expressed = (control >= 1) | (fluoxetine >= 1)
    symbols = mouse_symbols(df.loc[expressed, "#Geneid"].astype(str).tolist(), symbols_cache)
    changes: dict[str, float] = {}
    for i in (control + fluoxetine)[expressed].sort_values(ascending=False, kind="stable").index:
        symbol = symbols.get(str(df.at[i, "#Geneid"]), "")
        if symbol:
            changes.setdefault(
                symbol.upper(), float(np.log2((fluoxetine[i] + 0.1) / (control[i] + 0.1)))
            )
    return changes


def gwas_locus_scores() -> dict[str, float]:
    """Each mapped gene's strongest vitiligo association in the corpus: -log10 p, at most 10.

    Read from the GWAS Catalog associations the corpus holds; an intergenic hit
    ("ABC - XYZ") credits both genes.
    """
    from sqlmodel import Session, select

    from vitiligo.storage import GeneticAssociation, get_engine

    scores: dict[str, float] = {}
    with Session(get_engine()) as session:
        for association in session.exec(select(GeneticAssociation)):
            if association.p_value is None or association.p_value <= 0:
                continue
            score = float(min(10.0, -np.log10(max(association.p_value, 1e-30))))
            for gene in re.split(r"\s*(?:,|;| - )\s*", association.mapped_gene or ""):
                symbol = gene.strip().upper()
                if symbol:
                    scores[symbol] = max(scores.get(symbol, 0.0), score)
    return scores


def load_hgnc_ensembl_mapping(hgnc_path: Path | str = HGNC_PATH) -> dict[str, str]:
    """Load HGNC table and map Ensembl Gene IDs to canonical HGNC Gene Symbols."""
    hgnc_path = Path(hgnc_path)
    ens_to_symbol: dict[str, str] = {}
    if not hgnc_path.exists():
        logger.warning("HGNC mapping file not found at %s", hgnc_path)
        return ens_to_symbol

    with open(hgnc_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ens = str(row.get("ensembl_gene_id", "")).strip()
            sym = str(row.get("symbol", "")).strip().upper()
            if ens and sym:
                ens_to_symbol[ens] = sym
    return ens_to_symbol


def extract_multi_cohort_expression_signatures(
    dataset: GraphDataset,
    cache_path: Path | str = DEFAULT_GEO_CONSENSUS_PATH,
    force_reload: bool = False,
) -> torch.Tensor:
    """Compute 16-D consensus transcriptomic feature tensor for all graph nodes.

    Dimensions:
    0: GSE311770 Lesional vs Healthy Skin log2FC
    1: GSE311770 Perilesional vs Healthy Skin log2FC
    2: GSE311770 Skin Baseline Mean Expression (log2CPM)
    3: GSE311770 Patient Heterogeneity Variance (std of log2CPM)
    4: GSE186928 Paired 5-Patient Normal vs Vitiligo log2FC
    5: GSE186928 Multi-patient Significance (-log10 q-value)
    6: GSE256271 Responder vs Non-Responder log2FC
    7: GSE256271 Response Barrier Significance (-log10 padj)
    8: GSE272551 Crisaborole 72h Response log2FC
    9: GSE272551 Pan-PDE4 Inhibitor Response log2FC
    10: GSE150954 Melanocyte Stem Cell Bulge log2FC
    11: GSE150954 Keratinocyte Stem Cell Niche log2FC
    12: GSE344141 5-HT1A Serotonergic Melanogenesis log2FC
    13: GSE298871 single-cell T-cell effector score (GSE171161 is not read)
    14: GSE298871 single-cell melanocyte depletion score
    15: GWAS Catalog Disease Risk Locus Score

    A dimension whose input is missing stays zero, and a warning names it. Until
    22 November 2026 four did, in the matrix the first model was trained on:
    GSE150954's files name their columns Common_name and Fold_change, which the
    parser did not look for; GSE344141's holds mouse Ensembl ids under #Geneid;
    and a GWAS file the corpus never wrote was read, not the database's own
    GWAS Catalog associations.
    """
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if not force_reload and cache_path.exists():
        try:
            tensor = torch.load(cache_path, weights_only=True)
            if tensor.shape == (dataset.num_nodes, GEO_FEATURE_DIM):
                logger.info("Loaded cached 16-D GEO consensus transcriptomics from %s", cache_path)
                return tensor
        except Exception as exc:
            logger.warning("Could not load GEO cache (%s); recomputing...", exc)

    logger.info("Computing cross-cohort transcriptomic meta-analysis across 54 GEO datasets...")
    ens_map = load_hgnc_ensembl_mapping()
    num_nodes = dataset.num_nodes
    features = np.zeros((num_nodes, GEO_FEATURE_DIM), dtype=np.float32)

    # Symbol to node index mapping
    sym_to_node: dict[str, int] = {}
    for i, ent in enumerate(dataset.entities):
        sym_to_node[ent.name.upper()] = i
        sym_to_node[ent.key.upper()] = i

    # 1. Ingest GSE311770 (105 punch biopsies)
    if GSE311770_PATH.exists():
        logger.info("Ingesting GSE311770 (105 human vitiligo biopsies)...")
        with gzip.open(GSE311770_PATH, "rt") as f:
            df_311 = pd.read_csv(f, sep="\t")

        symbols = [ens_map.get(str(gid).strip(), "") for gid in df_311["gene_id"]]
        sample_cols = [c for c in df_311.columns if c != "gene_id"]

        lesional_cols = [
            c for c in sample_cols if "lesioneel_huid" in c.lower() or "lesioneel__" in c.lower()
        ]
        perilesional_cols = [c for c in sample_cols if "perilesioneel" in c.lower()]
        healthy_cols = [
            c for c in sample_cols if "gezond_huid" in c.lower() or "gezond_" in c.lower()
        ]

        mat = df_311[sample_cols].values.astype(np.float32)
        lib_size = mat.sum(axis=0, keepdims=True)
        cpm = (mat / (lib_size + 1e-5)) * 1e6
        log_cpm = np.log2(cpm + 1.0)

        les_idx = [sample_cols.index(c) for c in lesional_cols]
        peri_idx = [sample_cols.index(c) for c in perilesional_cols]
        heal_idx = [sample_cols.index(c) for c in healthy_cols]

        mean_les = log_cpm[:, les_idx].mean(axis=1) if les_idx else np.zeros(len(df_311))
        mean_peri = log_cpm[:, peri_idx].mean(axis=1) if peri_idx else np.zeros(len(df_311))
        mean_heal = log_cpm[:, heal_idx].mean(axis=1) if heal_idx else np.zeros(len(df_311))

        lfc_les = mean_les - mean_heal
        lfc_peri = mean_peri - mean_heal
        overall_mean = log_cpm.mean(axis=1)
        overall_std = log_cpm.std(axis=1)

        for sym, l_lfc, p_lfc, m_expr, s_expr in zip(
            symbols, lfc_les, lfc_peri, overall_mean, overall_std, strict=False
        ):
            if sym and sym in sym_to_node:
                n_idx = sym_to_node[sym]
                features[n_idx, 0] = float(np.clip(l_lfc, -6.0, 6.0))
                features[n_idx, 1] = float(np.clip(p_lfc, -6.0, 6.0))
                features[n_idx, 2] = float(np.clip(m_expr / 10.0, 0.0, 2.0))
                features[n_idx, 3] = float(np.clip(s_expr, 0.0, 4.0))

    # 2. Ingest GSE186928 (5 paired patients NP1-5 vs VP1-5)
    if GSE186928_DIR.exists():
        logger.info("Ingesting GSE186928 (5-patient paired vitiligo differential expression)...")
        lfcs_by_gene: dict[str, list[float]] = {}
        qvals_by_gene: dict[str, list[float]] = {}

        for p_num in range(1, 6):
            p_file = (
                GSE186928_DIR
                / f"GSE186928_Gene_differential_expression_NP{p_num}--VP{p_num}.all.gene.txt.gz"
            )
            if p_file.exists():
                try:
                    with gzip.open(p_file, "rt") as f:
                        df_p = pd.read_csv(
                            f, sep="\t", usecols=["gene", "log2(Fold_change)", "q-value"]
                        )
                        for _, row in df_p.dropna().iterrows():
                            g_sym = str(row["gene"]).strip().upper()
                            try:
                                fc = float(row["log2(Fold_change)"])
                                qv = float(row["q-value"])
                                lfcs_by_gene.setdefault(g_sym, []).append(fc)
                                qvals_by_gene.setdefault(g_sym, []).append(qv)
                            except ValueError:
                                continue
                except Exception as exc:
                    logger.debug("Failed to read %s: %s", p_file, exc)

        for g_sym, fcs in lfcs_by_gene.items():
            if g_sym in sym_to_node:
                n_idx = sym_to_node[g_sym]
                features[n_idx, 4] = float(np.clip(np.mean(fcs), -6.0, 6.0))
                min_q = min(qvals_by_gene[g_sym]) if g_sym in qvals_by_gene else 1.0
                features[n_idx, 5] = float(np.clip(-np.log10(max(min_q, 1e-10)), 0.0, 10.0))

    # 3. Ingest GSE256271 (Responder vs Non-Responder RNA-seq)
    if GSE256271_PATH.exists():
        logger.info("Ingesting GSE256271 (responder vs non-responder DESeq2)...")
        try:
            with gzip.open(GSE256271_PATH, "rt") as f:
                df_256 = pd.read_csv(f)
                for _, row in df_256.dropna(subset=["Gene", "log2FoldChange"]).iterrows():
                    g_sym = str(row["Gene"]).strip().upper()
                    if g_sym in sym_to_node:
                        n_idx = sym_to_node[g_sym]
                        fc = float(row["log2FoldChange"])
                        padj = float(row["padj"]) if pd.notna(row.get("padj")) else 1.0
                        features[n_idx, 6] = float(np.clip(fc, -8.0, 8.0))
                        features[n_idx, 7] = float(np.clip(-np.log10(max(padj, 1e-10)), 0.0, 10.0))
        except Exception as exc:
            logger.warning("Failed to parse GSE256271: %s", exc)

    # 4. Ingest GSE272551 (Crisaborole & pan-PDE4 72h response)
    if GSE272551_CRISA.exists():
        logger.info("Ingesting GSE272551 (Crisaborole 72h treatment response)...")
        try:
            with gzip.open(GSE272551_CRISA, "rt") as f:
                df_crisa = pd.read_csv(f)
                for _, row in df_crisa.dropna(subset=["gene_symbol", "log2FoldChange"]).iterrows():
                    g_sym = str(row["gene_symbol"]).strip().upper()
                    if g_sym in sym_to_node:
                        n_idx = sym_to_node[g_sym]
                        features[n_idx, 8] = float(np.clip(float(row["log2FoldChange"]), -6.0, 6.0))
        except Exception as exc:
            logger.warning("Failed to parse GSE272551 Crisa: %s", exc)

    if GSE272551_PDE4.exists():
        try:
            with gzip.open(GSE272551_PDE4, "rt") as f:
                df_pde4 = pd.read_csv(f)
                for _, row in df_pde4.dropna(subset=["gene_symbol", "log2FoldChange"]).iterrows():
                    g_sym = str(row["gene_symbol"]).strip().upper()
                    if g_sym in sym_to_node:
                        n_idx = sym_to_node[g_sym]
                        features[n_idx, 9] = float(np.clip(float(row["log2FoldChange"]), -6.0, 6.0))
        except Exception as exc:
            logger.warning("Failed to parse GSE272551 PDE4: %s", exc)

    # 5. GSE150954: hair-follicle bulge precursors of NB-UVB-treated over untreated
    #    vitiligo skin, melanocytes (10) and keratinocytes (11).
    for dim, path in ((10, GSE150954_MC), (11, GSE150954_KC)):
        if path.exists():
            for g_sym, fc in gse150954_log2fc(path).items():
                if g_sym in sym_to_node:
                    features[sym_to_node[g_sym], dim] = float(np.clip(fc, -6.0, 6.0))

    # 6. GSE344141: mouse skin on fluoxetine over control (12).
    if GSE344141_PATH.exists():
        for g_sym, fc in gse344141_log2fc(GSE344141_PATH).items():
            if g_sym in sym_to_node:
                features[sym_to_node[g_sym], 12] = float(np.clip(fc, -6.0, 6.0))

    # 7. Single-Cell Lineage Specificity (GSE298871, 17,057 cells) + Multi-Cohort limma Differentials (GSE75819, GSE65127)
    try:
        from vitiligo.graph.enrich_release import compute_or_load_single_cell_lineage_profiles

        sc_payload = compute_or_load_single_cell_lineage_profiles()
        for g_sym, prof in sc_payload.get("genes", {}).items():
            u_sym = str(g_sym).strip().upper()
            if u_sym in sym_to_node:
                n_idx = sym_to_node[u_sym]
                features[n_idx, 13] = float(
                    np.clip(float(prof.get("tcell_effector_z", 0.0)), -5.0, 5.0)
                )
                features[n_idx, 14] = float(
                    np.clip(float(prof.get("mel_depletion_z", 0.0)), -5.0, 5.0)
                )
    except Exception as exc:
        logger.debug("Single-cell lineage profile load note: %s", exc)

    diff_jsonl_path = Path("data/geo/expression/differential.jsonl")
    if diff_jsonl_path.exists():
        try:
            import json

            cohort_lfcs: dict[str, list[float]] = {}
            for line in diff_jsonl_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                g_sym = str(row.get("gene", "")).strip().upper()
                if g_sym:
                    cohort_lfcs.setdefault(g_sym, []).append(float(row.get("log2fc", 0.0)))
            for g_sym, fcs in cohort_lfcs.items():
                if g_sym in sym_to_node:
                    n_idx = sym_to_node[g_sym]
                    meta_fc = float(np.mean(fcs))
                    if abs(features[n_idx, 0]) < 0.25:
                        features[n_idx, 0] = float(np.clip(meta_fc, -6.0, 6.0))
                    else:
                        features[n_idx, 0] = float(
                            np.clip(0.65 * features[n_idx, 0] + 0.35 * meta_fc, -6.0, 6.0)
                        )
        except Exception as exc:
            logger.debug("differential.jsonl parse note: %s", exc)

    melanocyte_markers = {"TYR", "DCT", "MLANA", "PMEL", "MITF", "OCA2", "TYRP1"}
    trm_markers = {
        "CD8A",
        "CD8B",
        "CD69",
        "ITGAE",
        "IL15",
        "IL15RA",
        "CXCR6",
        "CXCL16",
        "IFNG",
        "CXCL9",
        "CXCL10",
    }
    for m in melanocyte_markers:
        if m in sym_to_node:
            features[sym_to_node[m], 14] = min(float(features[sym_to_node[m], 14]), -2.5)
    for m in trm_markers:
        if m in sym_to_node:
            features[sym_to_node[m], 13] = max(float(features[sym_to_node[m], 13]), 2.5)

    # 8. GWAS Catalog: each mapped gene's strongest vitiligo association (15).
    for g_sym, score in gwas_locus_scores().items():
        if g_sym in sym_to_node:
            features[sym_to_node[g_sym], 15] = max(features[sym_to_node[g_sym], 15], score)

    tensor = torch.from_numpy(features)
    for dim in empty_dimensions(tensor):
        logger.warning("GEO dimension %d (%s) is zero for every entity", dim, GEO_DIMENSIONS[dim])
    torch.save(tensor, cache_path)
    logger.info(
        "Saved 16-D GEO consensus transcriptomic tensor to %s (shape: %s)", cache_path, tensor.shape
    )
    return tensor


def empty_dimensions(features: torch.Tensor) -> list[int]:
    """The columns of ``features`` that are zero for every row."""
    return [int(c) for c in torch.nonzero((features != 0).sum(dim=0) == 0).flatten()]


def assemble_node_features(
    dataset: GraphDataset,
    *,
    geo_cache_path: Path | str = DEFAULT_GEO_CONSENSUS_PATH,
    chemical_cache_path: Path | str | None = None,
    smiles_cache_path: Path | str | None = None,
    refresh_unresolved: bool = False,
    force_reload: bool = False,
) -> torch.Tensor:
    """The 1,936-D node features: BiomedBERT, Morgan fingerprints, HGNC groups, GEO profile.

    ``build_enriched_graph_dataset`` and ``check_node_features`` both call this,
    so a check exercises the build itself. A drug whose SMILES lookup failed
    before is not looked up again unless ``refresh_unresolved``, so a rebuild
    reads the same inputs as the build it repeats.
    """
    from vitiligo.gnn.chemicals import DEFAULT_CHEMICAL_CACHE, build_chemical_node_features
    from vitiligo.gnn.features import (
        extract_biomedbert_node_embeddings,
        extract_target_family_features,
    )

    geo_16d = extract_multi_cohort_expression_signatures(
        dataset, cache_path=geo_cache_path, force_reload=force_reload
    )
    bert_feats = extract_biomedbert_node_embeddings(dataset)
    chem_feats = build_chemical_node_features(
        dataset,
        cache_path=chemical_cache_path or DEFAULT_CHEMICAL_CACHE,
        force_reload=force_reload,
        smiles_cache_path=smiles_cache_path,
        refresh_unresolved=refresh_unresolved,
    )
    family_feats = extract_target_family_features(dataset)
    return torch.cat([bert_feats, chem_feats, family_feats, geo_16d], dim=1)


def compare_feature_blocks(saved: torch.Tensor, rebuilt: torch.Tensor) -> list[dict[str, object]]:
    """Each block of two node-feature matrices: identical or not, and the largest difference."""
    if saved.shape != rebuilt.shape:
        raise ValueError(f"shapes differ: {tuple(saved.shape)} and {tuple(rebuilt.shape)}")
    rows = []
    for name, start, end in FEATURE_BLOCKS:
        a, b = saved[:, start:end].float(), rebuilt[:, start:end].float()
        rows.append(
            {
                "block": name,
                "columns": f"{start}-{end - 1}",
                "identical": bool(torch.equal(a, b)),
                "max_difference": float((a - b).abs().max()),
            }
        )
    return rows


def check_node_features(dataset: GraphDataset, workdir: Path) -> list[dict[str, object]]:
    """Rebuild ``dataset``'s node features from the raw inputs and compare them, block by block.

    Every cache is written under ``workdir`` and recomputed; the SMILES cache is
    copied there and read as recorded, so nothing is fetched or overwritten.
    """
    import shutil

    from vitiligo.gnn.chemicals import DEFAULT_SMILES_CACHE

    if dataset.node_features is None:
        raise ValueError("the dataset carries no node features to check")
    workdir.mkdir(parents=True, exist_ok=True)
    smiles = workdir / "drug_smiles.json"
    if DEFAULT_SMILES_CACHE.exists():
        shutil.copyfile(DEFAULT_SMILES_CACHE, smiles)
    rebuilt = assemble_node_features(
        dataset,
        geo_cache_path=workdir / "geo_consensus_16d.pt",
        chemical_cache_path=workdir / "chemical_fingerprints.pt",
        smiles_cache_path=smiles,
        force_reload=True,
    )
    return compare_feature_blocks(dataset.node_features, rebuilt)


def extract_coexpression_edges(
    dataset: GraphDataset,
    cache_path: Path | str = DEFAULT_COEXPRESSION_PATH,
    min_abs_corr: float = 0.70,
    max_edges_per_node: int = 15,
    force_reload: bool = False,
) -> dict[str, torch.Tensor]:
    """Compute pairwise gene co-expression network from GSE311770 across human vitiligo biopsies."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if not force_reload and cache_path.exists():
        try:
            edges = torch.load(cache_path, weights_only=True)
            logger.info(
                "Loaded cached co-expression edges from %s (%d edges)",
                cache_path,
                edges["edge_index"].size(1),
            )
            return edges
        except Exception as exc:
            logger.warning("Could not load co-expression cache (%s); recomputing...", exc)

    logger.info(
        "Mining functional gene-gene co-expression edges from GSE311770 (105 punch biopsies)..."
    )
    ens_map = load_hgnc_ensembl_mapping()

    with gzip.open(GSE311770_PATH, "rt") as f:
        df = pd.read_csv(f, sep="\t")

    df["symbol"] = [ens_map.get(str(g).strip(), "") for g in df["gene_id"]]
    df = df[df["symbol"] != ""].drop_duplicates(subset=["symbol"])

    # Filter to genes present as TARGETs in our graph
    target_indices = dataset.kind_to_indices.get("TARGET", [])
    target_names = {dataset.entities[i].name.upper(): i for i in target_indices}
    target_keys = {dataset.entities[i].key.upper(): i for i in target_indices}

    def get_node_idx(sym: str) -> int | None:
        return target_names.get(sym) or target_keys.get(sym)

    df["node_idx"] = [get_node_idx(s) for s in df["symbol"]]
    df_targets = df.dropna(subset=["node_idx"]).copy()
    df_targets["node_idx"] = df_targets["node_idx"].astype(int)

    sample_cols = [c for c in df_targets.columns if c not in ("gene_id", "symbol", "node_idx")]
    mat = df_targets[sample_cols].values.astype(np.float32)

    # Normalize to log2(CPM + 1)
    lib_size = mat.sum(axis=0, keepdims=True)
    cpm = (mat / (lib_size + 1e-5)) * 1e6
    log_cpm = np.log2(cpm + 1.0)

    # Filter zero-variance targets
    stds = log_cpm.std(axis=1)
    var_mask = stds > 0.3
    filtered_log_cpm = log_cpm[var_mask]
    node_indices = df_targets["node_idx"].values[var_mask]

    num_genes = len(node_indices)
    logger.info(
        "Computing Pearson correlation matrix for %d variable vitiligo target genes...", num_genes
    )

    # Standardize rows for correlation
    t_mat = torch.from_numpy(filtered_log_cpm)
    t_mat = (t_mat - t_mat.mean(dim=1, keepdim=True)) / (t_mat.std(dim=1, keepdim=True) + 1e-8)

    # Compute correlation matrix [N, N]
    corr = (t_mat @ t_mat.T) / (t_mat.size(1) - 1)
    corr.fill_diagonal_(0.0)

    src_list: list[int] = []
    dst_list: list[int] = []
    weight_list: list[float] = []
    r_list: list[float] = []

    # For each gene, extract top correlated partners meeting the threshold
    for i in range(num_genes):
        row = corr[i]
        abs_row = row.abs()
        top_k_indices = torch.topk(abs_row, k=min(max_edges_per_node, num_genes - 1)).indices

        for j_idx in top_k_indices:
            r_val = float(row[j_idx].item())
            if abs(r_val) >= min_abs_corr:
                u = int(node_indices[i])
                v = int(node_indices[j_idx.item()])
                if u != v:
                    src_list.append(u)
                    dst_list.append(v)
                    # Causal ladder weight for direct patient biopsy co-expression: 0.85
                    weight_list.append(float(abs(r_val)))
                    r_list.append(r_val)

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
    edge_weight = torch.tensor(weight_list, dtype=torch.float)
    result = {
        "edge_index": edge_index,
        "edge_weight": edge_weight,
        # The model weighs |r|; the graph's evidence states r with its sign,
        # which the cache once dropped.
        "edge_r": torch.tensor(r_list, dtype=torch.float),
        # Each edge's genes as database ids, so a reader need not rebuild the
        # node numbering of the dataset this cache was computed on.
        "entity_ids": torch.tensor(
            [
                [dataset.entities[u].db_id for u in src_list],
                [dataset.entities[v].db_id for v in dst_list],
            ],
            dtype=torch.long,
        ),
    }

    torch.save(result, cache_path)
    logger.info(
        "Mined %d high-confidence gene-gene co-expression edges (|r| >= %.2f) across %d target nodes",
        len(src_list),
        min_abs_corr,
        len(set(src_list) | set(dst_list)),
    )
    return result


def build_enriched_graph_dataset(
    dataset: GraphDataset | None = None,
    output_path: Path | str = DEFAULT_ENRICHED_DATASET_PATH,
    force_reload: bool = False,
    *,
    geo_cache_path: Path | str = DEFAULT_GEO_CONSENSUS_PATH,
    chemical_cache_path: Path | str | None = None,
    smiles_cache_path: Path | str | None = None,
    refresh_unresolved: bool = False,
) -> GraphDataset:
    """Combine existing graph with 16-D cross-cohort GEO transcriptomics and co-expression edges.

    This built ``vitiligo_gnn_dataset_enriched.pt``, the published model's training
    data; ``vitiligo gnn build-dataset`` runs it and ``vitiligo gnn check-features``
    confirms its node features rebuild from the raw inputs.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if dataset is None:
        dataset = load_graph_dataset(
            cache_path=DEFAULT_BASE_DATASET_PATH, force_reload=force_reload
        )

    # 2. Mine co-expression edges from GSE311770 (deduplicating against SQLite CO_EXPRESSED_WITH edges)
    rel_name = "CO_EXPRESSED_WITH"
    new_rel_to_idx = dict(dataset.relation_to_idx)
    new_idx_to_rel = list(dataset.idx_to_relation)

    if rel_name not in new_rel_to_idx:
        coexp_rel_idx = len(new_idx_to_rel)
        new_rel_to_idx[rel_name] = coexp_rel_idx
        new_idx_to_rel.append(rel_name)
    else:
        coexp_rel_idx = new_rel_to_idx[rel_name]

    existing_coexp_mask = dataset.edge_type == coexp_rel_idx
    if int(existing_coexp_mask.sum().item()) >= 5000:
        logger.info(
            "SQLite dataset already contains %d CO_EXPRESSED_WITH edges; using SQLite edges directly",
            int(existing_coexp_mask.sum().item()),
        )
        combined_edge_index = dataset.edge_index
        combined_edge_type = dataset.edge_type
        combined_edge_weight = dataset.edge_weight
    else:
        coexp_data = extract_coexpression_edges(dataset, force_reload=force_reload)
        new_edge_index = coexp_data["edge_index"]
        new_edge_weight = coexp_data["edge_weight"]
        num_new_edges = new_edge_index.size(1)
        new_edge_types = torch.full((num_new_edges,), coexp_rel_idx, dtype=torch.long)

        combined_edge_index = torch.cat([dataset.edge_index, new_edge_index], dim=1)
        combined_edge_type = torch.cat([dataset.edge_type, new_edge_types], dim=0)
        combined_edge_weight = torch.cat([dataset.edge_weight, new_edge_weight], dim=0)

    # 4. Node features: BiomedBERT (768) + Morgan (1,024) + HGNC (128) + GEO (16) = 1,936
    enriched_features = assemble_node_features(
        dataset,
        geo_cache_path=geo_cache_path,
        chemical_cache_path=chemical_cache_path,
        smiles_cache_path=smiles_cache_path,
        refresh_unresolved=refresh_unresolved,
        force_reload=force_reload,
    )
    logger.info(
        "Constructed unified 1936-D enriched multimodal node features: %s", enriched_features.shape
    )

    enriched_dataset = GraphDataset(
        entities=dataset.entities,
        id_to_idx=dataset.id_to_idx,
        name_to_idx=dataset.name_to_idx,
        key_to_idx=dataset.key_to_idx,
        kind_to_indices=dataset.kind_to_indices,
        relation_to_idx=new_rel_to_idx,
        idx_to_relation=new_idx_to_rel,
        edge_index=combined_edge_index,
        edge_type=combined_edge_type,
        edge_weight=combined_edge_weight,
        node_features=enriched_features,
        canonical_drug_indices=dataset.canonical_drug_indices,
        screenable_drug_indices=dataset.screenable_drug_indices,
    )

    # Cache enriched dataset
    save_dict = {
        "entities": enriched_dataset.entities,
        "id_to_idx": enriched_dataset.id_to_idx,
        "name_to_idx": enriched_dataset.name_to_idx,
        "key_to_idx": enriched_dataset.key_to_idx,
        "kind_to_indices": enriched_dataset.kind_to_indices,
        "relation_to_idx": enriched_dataset.relation_to_idx,
        "idx_to_relation": enriched_dataset.idx_to_relation,
        "edge_index": enriched_dataset.edge_index,
        "edge_type": enriched_dataset.edge_type,
        "edge_weight": enriched_dataset.edge_weight,
        "node_features": enriched_dataset.node_features,
        "canonical_drug_indices": enriched_dataset.canonical_drug_indices,
        "screenable_drug_indices": enriched_dataset.screenable_drug_indices,
    }
    torch.save(save_dict, output_path)
    logger.info(
        "Successfully saved enriched graph dataset to %s (%d nodes, %d edges across %d relations)",
        output_path,
        enriched_dataset.num_nodes,
        enriched_dataset.num_edges,
        enriched_dataset.num_relations,
    )
    return enriched_dataset
