"""Which genes vitiligo skin expresses differently, series by series.

Each comparison is one a depositor's own labels define: lesional skin against
the same patients' unaffected skin, or against healthy donors. Genes are
tested with limma's moderated t (Smyth 2004), which borrows each gene's
variance from all genes, as the series' own papers did; a pair from one
patient is tested as a pair. A gene passes at a false discovery rate of 5%
and a twofold change.

A comparison is used only if it sees what any lesional biopsy must show:
melanocytes are gone, so their pigment genes are lower. One that cannot see
that cannot be trusted to see anything subtler, and is reported but not used.

Two things this cannot say. Genes of the missing melanocytes are lower
because the cells are missing, so most of the strongest results are a
consequence of the disease, not a cause of it. And a difference measured in
skin is an association: the graph records it as one.

Blood series were tested too (GSE90880, 8 against 6; GSE80009, 8 against 4)
and nothing in either passed, so neither is listed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo.sources.geo_expression import (
    Expression,
    annotation_path,
    array_by_gene,
    counts_by_gene,
    hgnc_path,
    series_matrix_path,
)
from vitiligo.sources.geo_files import DEFAULT_CACHE

FDR = 0.05
LOG2_CHANGE = 1.0
METHOD = "moderated t (limma eBayes)"
# Lost with the melanocytes: lower in any lesion a comparison can see.
MELANOCYTE = ("TYR", "TYRP1", "DCT", "PMEL", "MLANA")


@dataclass(frozen=True)
class Contrast:
    """A comparison a series' own sample labels define."""

    series: str
    label: str
    case: str  # pattern on a sample's name in the series
    control: str
    pair: str | None = None  # its first group names the patient both samples came from
    platform: str | None = None  # an array's platform; None for a counts table
    counts: str | None = None  # the counts table, under the series' folder
    linear: bool = False  # values as measured, not yet logged


CONTRASTS = (
    Contrast(
        "GSE65127",
        "lesional vs non-lesional skin, same patients",
        r"^Lesional",
        r"^Non Lesional",
        pair=r"\[(\d+)_",
        platform="GPL570",
    ),
    Contrast(
        "GSE65127",
        "lesional skin vs healthy volunteers",
        r"^Lesional",
        r"^Healthy",
        platform="GPL570",
    ),
    Contrast(
        "GSE75819",
        "lesional vs non-lesional skin, same patients",
        r"V$",
        r"N$",
        pair=r"^(VD\d+)",
        platform="GPL6884",
        linear=True,
    ),
    # GPL14951 is Illumina HT-12 v4, whose probe ids are GPL10558's.
    Contrast(
        "GSE53146",
        "lesional skin vs healthy donors",
        r"^Vitiligo",
        r"^Control",
        platform="GPL10558",
        linear=True,
    ),
    # Dutch labels: lesioneel, gezond (the patient's unaffected skin). Patient
    # VP-008 was sampled twice, so a pair is one visit's.
    Contrast(
        "GSE311770",
        "lesional vs unaffected skin, same patients",
        r"_lesioneel",
        r"_gezond",
        pair=r"(VP_\d+_\d+(?:_X)?)",
        counts="GSE311770_all_samples_rsem_gene_counts.tsv.gz",
    ),
    Contrast(
        "GSE311770",
        "lesional skin vs healthy donors",
        r"_lesioneel",
        r"ontrol",
        counts="GSE311770_all_samples_rsem_gene_counts.tsv.gz",
    ),
)


@dataclass(frozen=True)
class Result:
    """One comparison: every gene tested, and whether the comparison can be used."""

    contrast: Contrast
    genes: list[str]
    log2fc: np.ndarray
    p: np.ndarray
    fdr: np.ndarray
    n_case: int
    n_control: int

    @property
    def sees_melanocyte_loss(self) -> bool:
        """Every pigment gene measured is lower, and most of them significantly."""
        index = {g: i for i, g in enumerate(self.genes)}
        held = [index[g] for g in MELANOCYTE if g in index]
        lower = all(self.log2fc[i] < 0 for i in held)
        return bool(held) and lower and sum(self.fdr[i] < FDR for i in held) * 2 > len(held)

    def passing(self) -> list[int]:
        return [
            i
            for i in range(len(self.genes))
            if self.fdr[i] < FDR and abs(self.log2fc[i]) >= LOG2_CHANGE
        ]


def _trigamma_inverse(x: float) -> float:
    from scipy import special

    y = 0.5 + 1 / x
    for _ in range(50):
        tri = special.polygamma(1, y)
        step = tri * (1 - tri / x) / special.polygamma(2, y)
        y += step
        if -step / y < 1e-8:
            break
    return float(y)


def prior(s2: np.ndarray, df: int) -> tuple[float, float]:
    """limma's fitFDist: the prior degrees of freedom and variance genes share."""
    from scipy import special

    s2 = s2[s2 > 0]
    e = np.log(s2) - special.digamma(df / 2) + np.log(df / 2)
    mean = float(e.mean())
    spread = float(((e - mean) ** 2).sum() / (len(e) - 1) - special.polygamma(1, df / 2))
    if spread <= 0:
        return float("inf"), float(np.exp(mean))
    d0 = 2 * _trigamma_inverse(spread)
    return d0, float(np.exp(mean + special.digamma(d0 / 2) - np.log(d0 / 2)))


def moderated_t(
    coef: np.ndarray, s2: np.ndarray, df: int, unscaled: float
) -> tuple[np.ndarray, np.ndarray]:
    """Moderated t statistics and their two-sided p-values."""
    from scipy import stats

    d0, s02 = prior(s2, df)
    if np.isinf(d0):
        posterior, total = np.full_like(s2, s02), np.inf
    else:
        posterior, total = (d0 * s02 + df * s2) / (d0 + df), df + d0
    t = coef / (np.sqrt(posterior) * unscaled)
    p = 2 * (stats.norm.sf(np.abs(t)) if np.isinf(total) else stats.t.sf(np.abs(t), total))
    return t, p


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1)
    out = np.empty_like(adjusted)
    out[order] = adjusted
    return out


def quantile_normalise(values: np.ndarray) -> np.ndarray:
    ranks = values.argsort(axis=0).argsort(axis=0)
    reference = np.sort(values, axis=0).mean(axis=1)
    normalised: np.ndarray = reference[ranks]
    return normalised


def _samples(contrast: Contrast, names: list[str]) -> tuple[list[int], list[int]]:
    """Columns of the case and control samples, in matched order when paired."""
    case = [i for i, n in enumerate(names) if re.search(contrast.case, n)]
    control = [i for i, n in enumerate(names) if re.search(contrast.control, n)]
    if contrast.pair is None:
        return case, control

    def key(i: int) -> str | None:
        match = re.search(str(contrast.pair), names[i])
        return match.group(1) if match else None

    controls = {key(i): i for i in control}
    pairs = [(i, controls[key(i)]) for i in case if key(i) in controls]
    return [a for a, _ in pairs], [b for _, b in pairs]


def compare(contrast: Contrast, data: Expression) -> Result:
    case, control = _samples(contrast, data.samples)
    values = data.values[:, case + control]
    genes = np.array(data.genes)
    if contrast.counts:
        # Counts per million, kept where a quarter of the samples express the gene.
        cpm = values / values.sum(axis=0) * 1e6
        keep = (cpm >= 1).sum(axis=1) >= values.shape[1] // 4
        values, genes = np.log2(cpm[keep] + 0.5), genes[keep]
    elif contrast.linear:
        values = quantile_normalise(np.log2(values.clip(min=1)))
    x, y = values[:, : len(case)], values[:, len(case) :]
    if contrast.pair:
        diff = x - y
        coef, s2 = diff.mean(axis=1), diff.var(axis=1, ddof=1)
        df, unscaled = len(case) - 1, 1 / np.sqrt(len(case))
    else:
        coef = x.mean(axis=1) - y.mean(axis=1)
        pooled = x.var(axis=1, ddof=1) * (len(case) - 1) + y.var(axis=1, ddof=1) * (
            len(control) - 1
        )
        df = len(case) + len(control) - 2
        s2, unscaled = pooled / df, float(np.sqrt(1 / len(case) + 1 / len(control)))
    _, p = moderated_t(coef, s2, df, unscaled)
    return Result(contrast, list(genes), coef, p, benjamini_hochberg(p), len(case), len(control))


def load(contrast: Contrast, cache: Path = DEFAULT_CACHE) -> Expression:
    if contrast.counts:
        return counts_by_gene(cache / contrast.series / contrast.counts, hgnc_path(cache))
    return array_by_gene(
        series_matrix_path(contrast.series, cache), annotation_path(str(contrast.platform), cache)
    )


def results_path(cache: Path = DEFAULT_CACHE) -> Path:
    return cache / "expression" / "differential.jsonl"


def write_results(results: list[Result], cache: Path = DEFAULT_CACHE) -> Path:
    """Every passing gene of every usable comparison, one JSON line each."""
    path = results_path(cache)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        for result in results:
            if not result.sees_melanocyte_loss:
                continue
            for i in result.passing():
                row: dict[str, Any] = {
                    "series": result.contrast.series,
                    "contrast": result.contrast.label,
                    "gene": result.genes[i],
                    "log2fc": round(float(result.log2fc[i]), 3),
                    "p": float(f"{result.p[i]:.3g}"),
                    "fdr": float(f"{result.fdr[i]:.3g}"),
                    "n_case": result.n_case,
                    "n_control": result.n_control,
                    "paired": result.contrast.pair is not None,
                }
                out.write(json.dumps(row) + "\n")
    return path


def read_results(cache: Path = DEFAULT_CACHE) -> list[dict[str, Any]]:
    path = results_path(cache)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
