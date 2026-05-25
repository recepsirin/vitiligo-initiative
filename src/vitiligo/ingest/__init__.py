"""Ingestion pipelines that orchestrate sources -> storage."""

from vitiligo.ingest.pipeline import (
    IngestionStats,
    run_ctgov_ingestion,
    run_euctr_ingestion,
    run_pmc_ingestion,
    run_pubmed_ingestion,
)

__all__ = [
    "IngestionStats",
    "run_ctgov_ingestion",
    "run_euctr_ingestion",
    "run_pmc_ingestion",
    "run_pubmed_ingestion",
]
