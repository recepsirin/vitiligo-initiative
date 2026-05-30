"""Full-corpus semantic search checks (local data/vitiligo.db only)."""

from __future__ import annotations

import json

import pytest
from tests.helpers.paths import FIXTURES_DIR

from vitiligo.embed import semantic_search

pytestmark = pytest.mark.corpus

_MANIFEST = json.loads((FIXTURES_DIR / "regression_expectations.json").read_text())

# Negative manifest cases that ban the mouse decoy on full corpus (not just regression slice).
_CORPUS_MOUSE_DECOY_CASES = [
    case
    for case in _MANIFEST.get("retrieval_negative", [])
    if case.get("must_not_include_source_ids") and "42100987" in case["must_not_include_source_ids"]
]


@pytest.mark.parametrize("case", _CORPUS_MOUSE_DECOY_CASES, ids=lambda c: c["id"])
def test_full_corpus_excludes_mouse_decoy(require_local_corpus, case: dict) -> None:
    """Clinical queries must not rank the mouse oxidative-stress decoy on full corpus."""
    top_n = int(case.get("top_n", 3))
    top_k = max(int(case["top_k"]), top_n)
    banned = set(case["must_not_include_source_ids"])

    hits = semantic_search(query=case["query"], top_k=top_k)
    window_ids = {hit.document.source_id for hit in hits[:top_n]}
    found = banned & window_ids
    assert not found, (
        f"{case['id']}: banned papers in top-{top_n}: {sorted(found)}. "
        f"Window: {[(h.document.source_id, (h.document.title or '')[:50]) for h in hits[:top_n]]}"
    )
