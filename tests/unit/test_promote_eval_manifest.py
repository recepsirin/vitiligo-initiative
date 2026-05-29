"""Unit tests for advisor eval → manifest promotion."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_PROMOTE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "review" / "promote-eval-to-manifest.py"


def _promote_module():
    spec = importlib.util.spec_from_file_location("promote_eval_to_manifest", _PROMOTE_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_merge_cases_adds_new_rows_only_by_default() -> None:
    mod = _promote_module()
    manifest: dict[str, Any] = {
        "retrieval": [{"id": "existing", "query": "old", "must_include_source_ids": ["1"]}]
    }
    proposals = [
        {"id": "existing", "query": "new", "must_include_source_ids": ["2"]},
        {"id": "fresh", "query": "q", "must_include_source_ids": ["3"]},
    ]

    _, added, updated = mod._merge_cases(manifest, proposals, update=False)

    assert added == ["fresh"]
    assert updated == []
    assert len(manifest["retrieval"]) == 2
    assert manifest["retrieval"][0]["query"] == "old"


def test_merge_cases_update_refreshes_existing_rows() -> None:
    mod = _promote_module()
    manifest: dict[str, Any] = {
        "retrieval": [
            {
                "id": "treat_jak_oral",
                "category": "treatment",
                "query": "old query",
                "must_include_source_ids": ["111"],
                "min_top_score": 0.8,
            }
        ]
    }
    proposals = [
        {
            "id": "treat_jak_oral",
            "query": "oral JAK inhibitor repigmentation vitiligo clinical trial",
            "must_include_source_ids": ["222", "333"],
            "min_top_score": 0.86,
            "expected_top_source_id": "222",
        }
    ]

    _, added, updated = mod._merge_cases(manifest, proposals, update=True)

    assert added == []
    assert updated == ["treat_jak_oral"]
    row = manifest["retrieval"][0]
    assert row["category"] == "treatment"
    assert row["query"] == proposals[0]["query"]
    assert row["must_include_source_ids"] == ["222", "333"]
    assert row["min_top_score"] == 0.86
    assert row["expected_top_source_id"] == "222"
