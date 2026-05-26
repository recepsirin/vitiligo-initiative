"""Shared exceptions for the reasoning layer."""

from __future__ import annotations


class LLMUnavailable(RuntimeError):  # noqa: N818 — name reads better without "Error" suffix
    """Raised when no LLM credentials are configured."""


class CorpusUnavailable(RuntimeError):  # noqa: N818
    """Raised when semantic search has no indexed embeddings to retrieve from."""
