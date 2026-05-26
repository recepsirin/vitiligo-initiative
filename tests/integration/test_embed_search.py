"""Unit tests for semantic search over the local embedding store."""

from __future__ import annotations

import pytest

from vitiligo.embed.search import semantic_search


@pytest.mark.integration
def test_semantic_search_returns_empty_without_embeddings(test_db_path) -> None:
    assert semantic_search(query="vitiligo JAK", top_k=5) == []
