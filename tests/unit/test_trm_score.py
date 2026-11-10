"""Unit tests for the T_RM Relapse Signature module."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest
from scipy.io import mmwrite
from scipy.sparse import csc_matrix

from vitiligo.models.trm_score import (
    CIRCULATING_EGRESS_GENES,
    HOUSEKEEPING_GENES,
    TRM_CORE_GENES,
    compute_trm_score,
    resolve_gse203262_barcodes,
    score_patient_archive,
)


def test_compute_trm_score_basic() -> None:
    # High TRM core, low circulating
    expr_high = {
        "CD8A": 10.0,
        "ITGAE": 5.0,
        "CD69": 4.0,
        "GZMB": 6.0,
        "CCR7": 0.0,
        "SELL": 0.0,
        "ACTB": 50.0,
        "GAPDH": 50.0,
    }
    res_high = compute_trm_score(expr_high)
    assert res_high.trm_core_mean > 0
    assert res_high.circulating_mean == 0.0
    assert res_high.raw_score > 0
    assert res_high.normalized_score > 0
    assert res_high.detected_core_genes == 4

    # Low TRM core, high circulating
    expr_low = {
        "CD8A": 0.1,
        "CCR7": 10.0,
        "SELL": 8.0,
        "ACTB": 50.0,
        "GAPDH": 50.0,
    }
    res_low = compute_trm_score(expr_low)
    assert res_low.raw_score < 0
    assert res_low.normalized_score < 0


def test_compute_trm_score_empty() -> None:
    res = compute_trm_score({})
    assert res.trm_core_mean == 0.0
    assert res.circulating_mean == 0.0
    assert res.raw_score == 0.0
    assert res.normalized_score == 0.0
    assert res.detected_core_genes == 0


def _create_synthetic_patient_tar(tar_path: Path) -> None:
    barcodes = ["CELL_A-1\n", "CELL_B-1\n", "CELL_C-2\n", "CELL_D-2\n"]
    genes = ["ENSG01\tCD8A\n", "ENSG02\tCD69\n", "ENSG03\tACTB\n", "ENSG04\tCCR7\n"]

    # 4 genes x 4 cells matrix
    # Cells 0,1 are NL (-1): low CD8A/CD69
    # Cells 2,3 are LS (-2): high CD8A/CD69
    data = csc_matrix([
        [0.0, 0.0, 5.0, 6.0],  # CD8A
        [0.0, 1.0, 4.0, 5.0],  # CD69
        [10.0, 10.0, 10.0, 10.0],  # ACTB
        [1.0, 2.0, 0.0, 0.0],  # CCR7
    ])

    with tarfile.open(tar_path, "w:gz") as tar:
        # barcodes
        bc_bytes = "".join(barcodes).encode("utf-8")
        bc_info = tarfile.TarInfo(name="PtTest_processed/barcodes.tsv")
        bc_info.size = len(bc_bytes)
        tar.addfile(bc_info, io.BytesIO(bc_bytes))

        # genes
        gn_bytes = "".join(genes).encode("utf-8")
        gn_info = tarfile.TarInfo(name="PtTest_processed/genes.tsv")
        gn_info.size = len(gn_bytes)
        tar.addfile(gn_info, io.BytesIO(gn_bytes))

        # matrix
        mtx_buf = io.BytesIO()
        mmwrite(mtx_buf, data)
        mtx_bytes = mtx_buf.getvalue()
        mtx_info = tarfile.TarInfo(name="PtTest_processed/matrix.mtx")
        mtx_info.size = len(mtx_bytes)
        tar.addfile(mtx_info, io.BytesIO(mtx_bytes))


def test_resolve_barcodes_and_patient_archive(tmp_path: Path) -> None:
    tar_path = tmp_path / "GSE203262_PtTest_processed.tar.gz"
    _create_synthetic_patient_tar(tar_path)

    labels = resolve_gse203262_barcodes(tar_path)
    assert len(labels) == 4
    assert labels["CELL_A-1"] == "nonlesional"
    assert labels["CELL_B-1"] == "nonlesional"
    assert labels["CELL_C-2"] == "lesional"
    assert labels["CELL_D-2"] == "lesional"

    res = score_patient_archive(tar_path)
    assert res["nl_cells"] == 2
    assert res["ls_cells"] == 2
    assert res["ls_score"] > res["nl_score"]
    assert res["delta_score"] > 0
    assert res["direction"] == "LS > NL"
