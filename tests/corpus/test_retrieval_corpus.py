"""Full-corpus semantic search checks (local data/vitiligo.db only)."""

from __future__ import annotations

import pytest

from vitiligo.embed import semantic_search

pytestmark = pytest.mark.corpus


def test_omics_melanocyte_query_excludes_mouse_decoy_from_top3(require_local_corpus) -> None:
    """Mouse oxidative-stress decoy must not dominate melanocyte omics on full corpus."""
    hits = semantic_search(
        query="melanocyte stress oxidative vitiligo biomarker",
        top_k=5,
    )
    top3_ids = {hit.document.source_id for hit in hits[:3]}
    assert "42100987" not in top3_ids, (
        f"mouse decoy PMID 42100987 in top-3: "
        f"{[(h.document.source_id, (h.document.title or '')[:50]) for h in hits[:3]]}"
    )
