"""Ingestion pipelines that orchestrate sources -> storage."""

from vitiligo.ingest.pipeline import IngestionStats, run_pubmed_ingestion

__all__ = ["IngestionStats", "run_pubmed_ingestion"]
