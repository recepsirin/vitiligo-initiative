"""GWAS Catalog: inherited variants associated with vitiligo.

The corpus had no human genetics. That matters for weighing a mechanistic
claim, because an inherited variant cannot have been caused by the disease:
genotype is fixed at conception, so an association runs one way only. It is
the one observational rung of the causal ladder that is not vulnerable to
reverse causation.

The GWAS Catalog's REST API was retired, so this reads the curated
associations file that EBI publishes with each release, keeping the rows
whose trait mentions vitiligo. The file covers every trait and is tens of
megabytes, so it is streamed and filtered rather than stored.

What this is **not**: evidence that a gene causes the disease. A catalogue row
says a variant near a gene associates with the trait in some population. The
mapped gene is the Catalog's annotation of what is nearby, which is not the
same as the gene whose function changes.

Release files: https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from vitiligo.logging import get_logger
from vitiligo.storage.models import GeneticAssociation, GeneticSourceKind

logger = get_logger(__name__)

RELEASE_BASE = "https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest"
ASSOCIATIONS_FILE = "gwas-catalog-associations_ontology-annotated-full.zip"
DEFAULT_TRAIT_QUERY = "vitiligo"

# Columns the Catalog has published for years; a release that renames one
# should fail loudly rather than silently import blanks.
REQUIRED_COLUMNS = (
    "DISEASE/TRAIT",
    "SNPS",
    "P-VALUE",
    "PUBMEDID",
    "STUDY ACCESSION",
)


def associations_url(file_name: str = ASSOCIATIONS_FILE) -> str:
    return f"{RELEASE_BASE}/{file_name}"


def _as_float(value: str | None) -> float | None:
    """The Catalog writes p-values as '4E-294' and leaves many fields blank."""
    if not value or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def parse_associations(
    raw: bytes, trait_query: str = DEFAULT_TRAIT_QUERY
) -> Iterator[dict[str, str]]:
    """Rows of the zipped TSV whose trait mentions ``trait_query`` (case-insensitive)."""
    needle = trait_query.lower()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [n for n in archive.namelist() if n.endswith(".tsv")]
        if not names:
            raise ValueError("no .tsv inside the GWAS Catalog archive")
        with archive.open(names[0]) as handle:
            header_line = handle.readline().decode("utf-8", "replace").rstrip("\r\n")
            header = header_line.split("\t")
            missing = [c for c in REQUIRED_COLUMNS if c not in header]
            if missing:
                raise ValueError(f"GWAS Catalog release is missing columns: {missing}")
            for line in handle:
                values = line.decode("utf-8", "replace").rstrip("\r\n").split("\t")
                row = dict(zip(header, values, strict=False))
                trait = f"{row.get('DISEASE/TRAIT', '')} {row.get('MAPPED_TRAIT', '')}".lower()
                if needle in trait:
                    yield row


def to_association(row: dict[str, str]) -> GeneticAssociation | None:
    """One catalogue row as a stored record, or ``None`` if it has no identity."""
    accession = (row.get("STUDY ACCESSION") or "").strip()
    variant = (row.get("SNPS") or "").strip()
    if not accession or not variant:
        return None
    return GeneticAssociation(
        source=GeneticSourceKind.GWAS_CATALOG,
        source_id=f"{accession}:{variant}",
        trait=(row.get("DISEASE/TRAIT") or "").strip(),
        mapped_trait=(row.get("MAPPED_TRAIT") or "").strip() or None,
        variant=variant,
        mapped_gene=(row.get("MAPPED_GENE") or "").strip() or None,
        reported_genes=(row.get("REPORTED GENE(S)") or "").strip() or None,
        risk_allele=(row.get("STRONGEST SNP-RISK ALLELE") or "").strip() or None,
        p_value=_as_float(row.get("P-VALUE")),
        p_value_text=(row.get("P-VALUE") or "").strip() or None,
        odds_ratio_or_beta=_as_float(row.get("OR or BETA")),
        confidence_interval=(row.get("95% CI (TEXT)") or "").strip() or None,
        study_accession=accession,
        pubmed_id=(row.get("PUBMEDID") or "").strip() or None,
        initial_sample=(row.get("INITIAL SAMPLE SIZE") or "").strip() or None,
        raw_metadata=dict(row),
        retrieved_at=datetime.now(UTC),
    )


def fetch_associations(
    client: httpx.Client,
    file_name: str = ASSOCIATIONS_FILE,
) -> bytes:
    """Download one release file. It is tens of megabytes, so give it room."""
    url = associations_url(file_name)
    logger.info("GWAS Catalog: downloading %s", url)
    response = client.get(url)
    response.raise_for_status()
    return bytes(response.content)


def filtered_payload(
    raw: bytes, trait_query: str, file_name: str, release_url: str
) -> dict[str, Any]:
    """The matching rows plus a fingerprint of the release they came from.

    Caching the whole release would mean keeping every trait's associations —
    tens of megabytes — to preserve the handful that become data. The rows we
    used are kept instead, with the release's own hash, so the ingest can be
    re-run offline and any row traced to the file it came from.
    """
    rows = list(parse_associations(raw, trait_query))
    return {
        "release_file": file_name,
        "release_url": release_url,
        "release_sha256": hashlib.sha256(raw).hexdigest(),
        "release_bytes": len(raw),
        "trait_query": trait_query,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "rows": rows,
    }


def rows_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Rows out of a cached payload, as ``filtered_payload`` wrote them."""
    return [r for r in payload.get("rows", []) if isinstance(r, dict)]


def records_from_rows(rows: list[dict[str, str]]) -> list[GeneticAssociation]:
    """Rows to stored records, de-duplicated by (study, variant)."""
    seen: set[str] = set()
    records: list[GeneticAssociation] = []
    for row in rows:
        record = to_association(row)
        if record is None or record.source_id in seen:
            continue
        seen.add(record.source_id)
        records.append(record)
    return records


def iter_records(
    raw: bytes, trait_query: str = DEFAULT_TRAIT_QUERY
) -> tuple[list[GeneticAssociation], dict[str, Any]]:
    """Parse a release file into records, de-duplicated by (study, variant)."""
    rows = list(parse_associations(raw, trait_query))
    return records_from_rows(rows), {"rows_matched": len(rows)}
