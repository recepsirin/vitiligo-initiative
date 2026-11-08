"""The expression values of a GEO series, by gene.

``geo_matrix.py`` reads a series matrix's header and stops at the table,
because the labels are all a survey needs. An analysis needs the table, and
two more files to make it about genes: an array reports probes, so its
platform's annotation names the gene each probe measures, and a sequencing
series reports Ensembl ids, which HGNC's approved set turns into symbols, the
names the knowledge graph already uses for genes.

Values are returned as the depositor processed them. Whether they need a log
or a normalisation is the analysis's decision, since it depends on what the
depositor wrote they did.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

from vitiligo.logging import get_logger
from vitiligo.sources.geo_files import DEFAULT_CACHE
from vitiligo.sources.geo_matrix import TABLE_MARKER, USER_AGENT, series_matrix_url

logger = get_logger(__name__)

PLATFORMS = "https://ftp.ncbi.nlm.nih.gov/geo/platforms"
HGNC = "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt"


@dataclass(frozen=True)
class Expression:
    """Genes by samples, each sample named as its series names it."""

    genes: list[str]
    samples: list[str]
    values: np.ndarray


def series_matrix_path(accession: str, cache: Path = DEFAULT_CACHE) -> Path:
    return cache / accession / f"{accession}_series_matrix.txt.gz"


def annotation_path(platform: str, cache: Path = DEFAULT_CACHE) -> Path:
    return cache / "platforms" / f"{platform}.annot.gz"


def hgnc_path(cache: Path = DEFAULT_CACHE) -> Path:
    return cache / "hgnc_complete_set.txt"


def annotation_url(platform: str) -> str:
    group = re.sub(r"\d{1,3}$", "nnn", platform)
    return f"{PLATFORMS}/{group}/{platform}/annot/{platform}.annot.gz"


def fetch(url: str, path: Path, client: httpx.Client) -> Path:
    """Download ``url`` to ``path`` unless it is already there."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with partial.open("wb") as out:
            for chunk in response.iter_bytes():
                out.write(chunk)
    partial.replace(path)
    logger.info("Fetched %s (%d bytes)", path, path.stat().st_size)
    return path


def fetch_inputs(series: list[str], platforms: list[str], cache: Path = DEFAULT_CACHE) -> None:
    """Every series matrix, platform annotation and the HGNC set an analysis reads."""
    with httpx.Client(
        timeout=300.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        for accession in series:
            fetch(series_matrix_url(accession), series_matrix_path(accession, cache), client)
        for platform in platforms:
            fetch(annotation_url(platform), annotation_path(platform, cache), client)
        fetch(HGNC, hgnc_path(cache), client)


def _cells(line: str) -> list[str]:
    return [cell.strip().strip('"') for cell in line.rstrip("\n").split("\t")]


def read_series_matrix(path: Path) -> tuple[list[str], list[str], np.ndarray]:
    """Sample titles, probe ids and values (probes by samples) of a series matrix."""
    titles: list[str] = []
    probes: list[str] = []
    rows: list[list[float]] = []
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("!Sample_title"):
                titles = _cells(line)[1:]
            if line.startswith(TABLE_MARKER):
                break
        next(handle)  # ID_REF and the sample accessions
        for line in handle:
            if line.startswith("!series_matrix_table_end"):
                break
            cells = _cells(line)
            probes.append(cells[0])
            rows.append([_number(c) for c in cells[1:]])
    return titles, probes, np.array(rows, dtype=float)


def _number(cell: str) -> float:
    try:
        return float(cell)
    except ValueError:
        return float("nan")


def read_annotation(path: Path) -> dict[str, str]:
    """Probe id -> the one gene it measures. A probe for several genes measures none."""
    found: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        column = -1
        for line in handle:
            cells = _cells(line)
            if column < 0:
                if cells[0] == "ID" and "Gene symbol" in cells:
                    column = cells.index("Gene symbol")
                continue
            if line.startswith("!platform_table_end"):
                break
            symbol = cells[column] if column < len(cells) else ""
            if symbol and "///" not in symbol:
                found[cells[0]] = symbol
    return found


def read_hgnc(path: Path) -> dict[str, str]:
    """Ensembl gene id -> approved HGNC symbol."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    symbol, ensembl = header.index("symbol"), header.index("ensembl_gene_id")
    found: dict[str, str] = {}
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) > ensembl and cells[ensembl]:
            found.setdefault(cells[ensembl], cells[symbol])
    return found


def array_by_gene(matrix: Path, annotation: Path) -> Expression:
    """An array series by gene: of a gene's probes, the one with the highest mean."""
    titles, probes, values = read_series_matrix(matrix)
    symbols = read_annotation(annotation)
    best: dict[str, int] = {}
    means = np.nanmean(values, axis=1)
    for row, probe in enumerate(probes):
        gene = symbols.get(probe)
        if gene is None or np.isnan(values[row]).any():
            continue
        if gene not in best or means[row] > means[best[gene]]:
            best[gene] = row
    genes = sorted(best)
    return Expression(genes, titles, values[[best[g] for g in genes]])


def counts_by_gene(table: Path, hgnc: Path) -> Expression:
    """A sequencing counts table by gene: Ensembl ids summed under their symbol."""
    symbols = read_hgnc(hgnc)
    summed: dict[str, np.ndarray] = {}
    with gzip.open(table, "rt", encoding="utf-8") as handle:
        samples = _cells(next(handle))[1:]
        for line in handle:
            cells = _cells(line)
            gene = symbols.get(cells[0].split(".")[0])
            if gene is None:
                continue
            row = np.array([float(c) for c in cells[1:]])
            summed[gene] = summed[gene] + row if gene in summed else row
    genes = sorted(summed)
    return Expression(genes, samples, np.array([summed[g] for g in genes]))
