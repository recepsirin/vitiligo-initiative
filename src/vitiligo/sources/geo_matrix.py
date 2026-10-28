"""What each sample in a GEO series actually is.

``geo.py`` stores a series' metadata: title, summary, how many samples. That
makes a dataset findable and says nothing about any sample in it.
``geo_files.py`` downloads the supplementary files, which for 23 of our 54
series are ``RAW.tar`` archives — instrument output, with no phenotype
attached.

Between the two sits the file that carries the labels, and nothing here read
it. ``<accession>_series_matrix.txt.gz`` begins with the per-sample metadata
GEO holds — title, source name and a list of ``key: value`` characteristics
for every sample — and then the normalised expression table. The header alone
answers which samples are lesional, which are healthy skin, and in four
series which came from skin that repigmented.

Three things shape this module.

**It reads the header and stops.** The matrix below it is tens of megabytes
of expression values, and the labels are all above
``!series_matrix_table_begin``. Decompression is incremental and ends at that
marker, so surveying every series costs a few hundred kilobytes each rather
than gigabytes.

**A sample's label lives in two places, inconsistently.** Some depositors put
the phenotype in ``Sample_source_name_ch1`` ("Lesional", "Healthy
Volunteer"), others in a characteristics line (``disease state: vitiligo``),
and many in both. Both are returned as they were written; normalising them
into one vocabulary is a decision for the analysis that needs it, not for the
reader.

**Not every series has one.** A matrix is generated for array and some
sequencing series; three of ours answer 404, which is a fact about the
deposit rather than an error.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx

from vitiligo.logging import get_logger

logger = get_logger(__name__)

FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/geo/series"
USER_AGENT = (
    "vitiligo-initiative/0.1 (non-profit vitiligo research; "
    "+https://github.com/recepsirin/vitiligo-initiative)"
)
TABLE_MARKER = "!series_matrix_table_begin"
# The header is small; this only stops a malformed stream running away.
MAX_HEADER_BYTES = 4_000_000

_QUOTED = re.compile(r'"([^"]*)"')
_ACCESSION = re.compile(r"^GSE\d+$")


@dataclass(frozen=True)
class GeoSample:
    """One sample of a series, labelled as its depositor labelled it."""

    accession: str
    title: str | None = None
    source_name: str | None = None
    organism: str | None = None
    characteristics: dict[str, str] = field(default_factory=dict)

    @property
    def labels(self) -> str:
        """Everything the depositor wrote about this sample, as one string."""
        parts = [self.title or "", self.source_name or ""]
        parts += [f"{k}: {v}" for k, v in sorted(self.characteristics.items())]
        return " | ".join(p for p in parts if p)


def series_matrix_url(accession: str) -> str:
    """Where GEO keeps a series' matrix file."""
    if not _ACCESSION.match(accession):
        raise ValueError(f"Not a GEO series accession: {accession!r}")
    group = re.sub(r"\d{1,3}$", "nnn", accession)
    return f"{FTP_BASE}/{group}/{accession}/matrix/{accession}_series_matrix.txt.gz"


def _field_values(header: str, name: str) -> list[str]:
    match = re.search(rf"^!{name}\t(.*)$", header, re.M)
    return _QUOTED.findall(match.group(1)) if match else []


def parse_header(header: str) -> list[GeoSample]:
    """The samples a series matrix header describes, in column order."""
    accessions = _field_values(header, "Sample_geo_accession")
    if not accessions:
        return []
    titles = _field_values(header, "Sample_title")
    sources = _field_values(header, "Sample_source_name_ch1")
    organisms = _field_values(header, "Sample_organism_ch1")

    # Each characteristics line is one key across all samples, so a sample's
    # own characteristics are that column of every such line.
    rows = [
        _QUOTED.findall(line)
        for line in re.findall(r"^!Sample_characteristics_ch1\t(.*)$", header, re.M)
    ]

    samples: list[GeoSample] = []
    for index, accession in enumerate(accessions):
        characteristics: dict[str, str] = {}
        for row in rows:
            if index >= len(row):
                continue
            cell = row[index].strip()
            if ":" not in cell:
                continue
            key, _, value = cell.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key and value:
                characteristics[key] = value
        samples.append(
            GeoSample(
                accession=accession,
                title=titles[index] if index < len(titles) else None,
                source_name=sources[index] if index < len(sources) else None,
                organism=organisms[index] if index < len(organisms) else None,
                characteristics=characteristics,
            )
        )
    return samples


def fetch_header(accession: str, client: httpx.Client) -> str | None:
    """A series matrix's header, without downloading the expression table.

    Returns ``None`` when GEO holds no matrix for the series.
    """
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buffer = ""
    received = 0
    try:
        with client.stream("GET", series_matrix_url(accession)) as response:
            if response.status_code == 404:
                logger.info("GEO has no series matrix for %s", accession)
                return None
            response.raise_for_status()
            for chunk in response.iter_bytes(65536):
                received += len(chunk)
                buffer += decompressor.decompress(chunk).decode("utf-8", errors="replace")
                if TABLE_MARKER in buffer or received > MAX_HEADER_BYTES:
                    break
    except (httpx.HTTPError, zlib.error) as exc:
        logger.warning("GEO series matrix for %s failed: %s", accession, exc)
        return None
    return buffer.split(TABLE_MARKER)[0]


def fetch_samples(accession: str, client: httpx.Client) -> list[GeoSample]:
    """Every labelled sample of one series."""
    header = fetch_header(accession, client)
    return parse_header(header) if header else []


# The characteristics that state what a sample *is*. A free-text field such
# as comorbidities or medication is not one of them: a diabetic retinopathy
# donor with vitiligo in their comorbidity list made that whole series look
# like a vitiligo study.
PHENOTYPE_KEYS: frozenset[str] = frozenset(
    {
        "disease",
        "disease state",
        "disease status",
        "diagnosis",
        "condition",
        "patient group",
        "subject status",
        "group",
        "phenotype",
        "sample group",
        "disease group",
    }
)


def is_about_vitiligo(
    samples: Iterable[GeoSample],
    *,
    title: str | None = None,
    term: str = "vitiligo",
) -> bool:
    """True when the series is about the disease, not merely matched on it.

    ``geo.py`` searches ``vitiligo[All Fields]``, which pulled in three
    diabetic retinopathy series — 316 of the 969 human samples we hold. The
    series title is the reliable signal; a sample counts only where the
    disease is named as that sample's phenotype or source, never from prose
    about a donor's other illnesses.
    """
    needle = term.lower()
    if needle in (title or "").lower():
        return True
    for sample in samples:
        if needle in (sample.source_name or "").lower():
            return True
        if needle in (sample.title or "").lower():
            return True
        for key, value in sample.characteristics.items():
            if key in PHENOTYPE_KEYS and needle in value.lower():
                return True
    return False
