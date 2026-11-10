"""Tissue-Resident Memory T cell (T_RM) Relapse Signature derivation and scoring.

Derived from single-cell RNA-sequencing of matched lesional (LS) and non-lesional (NL)
vitiligo skin (GSE203262) and mouse melanoma-associated vitiligo T_RM reference (GSE169238).

Addresses Roadmap Item 3.6 and Mechanistic Hypothesis `trm-il15-relapse`:
- In skin that has repigmented following JAKi/phototherapy treatment, measures the
  transcriptional burden of persisting pathogenic CD8+ CD103+ CD69+ T_RM cells anchored
  at the dermal-epidermal junction by keratinocyte-derived IL-15.
- Prospective Falsifiable Test: In repigmented skin sampled at treatment withdrawal
  (e.g., in stop-vs-step-down maintenance regimens), a higher T_RM signature score
  predicts shorter time to loss of response (hazard ratio per SD > 1.0).
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from scipy.io import mmread
except ImportError:
    mmread = None  # type: ignore[assignment]

from vitiligo.logging import get_logger

logger = get_logger(__name__)

# Core gene panels defining the human/mouse conserved skin T_RM survival and effector axis
TRM_CORE_GENES: tuple[str, ...] = (
    "CD8A",  # Cytotoxic T cell lineage alpha chain
    "CD8B",  # Cytotoxic T cell lineage beta chain
    "ITGAE",  # CD103 alpha-E integrin, anchors to E-cadherin on basal keratinocytes
    "CD69",  # S1PR1 functional antagonist, blocks epidermal egress
    "CXCR6",  # Chemokine receptor for epidermal CXCL16
    "IL2RB",  # CD122, beta chain of the IL-15/IL-2 receptor (therapeutic antibody target)
    "IL15RA",  # IL-15 receptor alpha, required for IL-15 trans-presentation by keratinocytes
    "GZMB",  # Granzyme B cytolytic serine protease
    "PRF1",  # Perforin membrane pore-forming protein
    "CXCL9",  # IFN-gamma inducible T-cell recruiting chemokine
    "CXCL10",  # IFN-gamma inducible CXCR3 ligand
)

CIRCULATING_EGRESS_GENES: tuple[str, ...] = (
    "CCR7",  # CC-chemokine receptor 7, directs homing to lymph node T zones
    "SELL",  # CD62L / L-selectin, peripheral lymph node homing receptor
    "S1PR1",  # Sphingosine-1-phosphate receptor 1, required for tissue egress
)

HOUSEKEEPING_GENES: tuple[str, ...] = (
    "ACTB",  # Beta-actin
    "GAPDH",  # Glyceraldehyde-3-phosphate dehydrogenase
    "RPLP0",  # Ribosomal protein lateral stalk subunit P0
)


@dataclass(frozen=True)
class TRMScoreResult:
    """Quantitative evaluation of a skin biopsy or pseudobulk sample."""

    sample_id: str
    trm_core_mean: float
    circulating_mean: float
    housekeeping_mean: float
    raw_score: float
    normalized_score: float
    detected_core_genes: int
    total_core_genes: int


def compute_trm_score(
    expression: dict[str, float],
    epsilon: float = 1e-6,
) -> TRMScoreResult:
    """Compute the T_RM Relapse Index for a given gene expression dictionary.

    Args:
        expression: Mapping of gene symbol (case-insensitive) to normalized expression
                    (e.g., TPM, FPKM, or CPM).
        epsilon: Small numerical offset to avoid division by zero.

    Returns:
        TRMScoreResult with raw and normalized score values.
    """
    expr_upper = {k.upper(): float(v) for k, v in expression.items()}

    trm_vals = [expr_upper[g] for g in TRM_CORE_GENES if g in expr_upper]
    circ_vals = [expr_upper[g] for g in CIRCULATING_EGRESS_GENES if g in expr_upper]
    hk_vals = [expr_upper[g] for g in HOUSEKEEPING_GENES if g in expr_upper]

    trm_mean = float(np.mean(trm_vals)) if trm_vals else 0.0
    circ_mean = float(np.mean(circ_vals)) if circ_vals else 0.0
    hk_mean = float(np.mean(hk_vals)) if hk_vals else 1.0

    # Log2-transformed ratio relative to housekeeping normalizers
    log_trm = np.log2(1.0 + trm_mean)
    log_circ = np.log2(1.0 + circ_mean)
    log_hk = np.log2(1.0 + hk_mean) if hk_mean > 0 else 1.0

    raw_score = float(log_trm - log_circ)
    normalized_score = float(raw_score / max(log_hk, epsilon))

    return TRMScoreResult(
        sample_id=str(expression.get("SAMPLE_ID", "sample")),
        trm_core_mean=trm_mean,
        circulating_mean=circ_mean,
        housekeeping_mean=hk_mean,
        raw_score=raw_score,
        normalized_score=normalized_score,
        detected_core_genes=len(trm_vals),
        total_core_genes=len(TRM_CORE_GENES),
    )


def resolve_gse203262_barcodes(tar_path: Path) -> dict[str, str]:
    """Resolve cell barcodes in GSE203262 patient tar archive to tissue phenotype.

    As documented in the series matrix !Sample_description and verified via
    expression of CXCL9/10, CD69, and keratinocyte stress panels:
    - Suffix '-1' corresponds to Non-lesional (NL) tissue.
    - Suffix '-2' corresponds to Lesional (LS) tissue.

    Returns:
        Mapping of cell barcode to 'nonlesional' or 'lesional'.
    """
    labels: dict[str, str] = {}
    with tarfile.open(tar_path, "r:gz") as tar:
        bc_members = [m for m in tar.getmembers() if "barcodes.tsv" in m.name]
        if not bc_members:
            raise FileNotFoundError(f"barcodes.tsv not found in {tar_path}")

        bc_file = tar.extractfile(bc_members[0])
        if bc_file is None:
            raise ValueError(f"Could not extract barcodes from {tar_path}")

        lines = bc_file.read().decode("utf-8").strip().split("\n")
        for line in lines:
            bc = line.strip()
            if bc.endswith("-1"):
                labels[bc] = "nonlesional"
            elif bc.endswith("-2"):
                labels[bc] = "lesional"
            else:
                labels[bc] = "unknown"
    return labels


def score_patient_archive(tar_path: Path) -> dict[str, Any]:
    """Score paired lesional vs non-lesional pseudobulk samples from a patient archive."""
    with tarfile.open(tar_path, "r:gz") as tar:
        bc_mem = next(m for m in tar.getmembers() if "barcodes.tsv" in m.name)
        gn_mem = next(m for m in tar.getmembers() if "genes.tsv" in m.name)
        mtx_mem = next(m for m in tar.getmembers() if "matrix.mtx" in m.name)

        bcs = tar.extractfile(bc_mem).read().decode("utf-8").strip().split("\n")  # type: ignore[union-attr]
        genes = [
            line.split("\t")
            for line in tar.extractfile(gn_mem).read().decode("utf-8").strip().split("\n")
        ]  # type: ignore[union-attr]
        gene_symbols = [g[1] if len(g) > 1 else g[0] for g in genes]
        sym_to_idx = {s.upper(): i for i, s in enumerate(gene_symbols)}

        is_nl = np.array([bc.endswith("-1") for bc in bcs])
        is_ls = np.array([bc.endswith("-2") for bc in bcs])

        if mmread is None:
            raise ImportError(
                "scipy is required for reading matrix market archives. Install with `pip install scipy`."
            )

        mtx = mmread(tar.extractfile(mtx_mem)).tocsr()  # type: ignore[union-attr]
        if mtx.shape[0] != len(gene_symbols):
            mtx = mtx.T

        def _pseudobulk(mask: np.ndarray) -> dict[str, float]:
            res: dict[str, float] = {}
            for g in TRM_CORE_GENES + CIRCULATING_EGRESS_GENES + HOUSEKEEPING_GENES:
                if g in sym_to_idx:
                    row = mtx[sym_to_idx[g], :].toarray().flatten()
                    res[g] = float(row[mask].mean()) if mask.sum() > 0 else 0.0
            return res

        expr_nl = _pseudobulk(is_nl)
        expr_ls = _pseudobulk(is_ls)

        res_nl = compute_trm_score(expr_nl)
        res_ls = compute_trm_score(expr_ls)

        return {
            "patient_file": tar_path.name,
            "nl_cells": int(is_nl.sum()),
            "ls_cells": int(is_ls.sum()),
            "nl_score": res_nl.normalized_score,
            "ls_score": res_ls.normalized_score,
            "delta_score": res_ls.normalized_score - res_nl.normalized_score,
            "direction": "LS > NL"
            if res_ls.normalized_score > res_nl.normalized_score
            else "NL > LS",
        }
