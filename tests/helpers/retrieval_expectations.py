"""Shared assertions for manifest-driven retrieval confidence cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vitiligo.embed.search import SearchHit


@dataclass(frozen=True)
class RetrievalHitView:
    source_id: str
    title: str | None
    score: float


def hits_from_search(hits: list[SearchHit]) -> list[RetrievalHitView]:
    return [
        RetrievalHitView(
            source_id=hit.document.source_id,
            title=hit.document.title,
            score=hit.score,
        )
        for hit in hits
    ]


def hits_from_api_results(results: list[dict[str, Any]]) -> list[RetrievalHitView]:
    return [
        RetrievalHitView(
            source_id=row["source_id"],
            title=row.get("title"),
            score=float(row["score"]),
        )
        for row in results
    ]


def assert_retrieval_expectations(
    case: dict[str, Any],
    hits: list[RetrievalHitView],
    *,
    label: str = "",
) -> None:
    """Assert a manifest retrieval case against normalized search hits."""
    case_id = case["id"]
    prefix = f"{case_id} ({label})" if label else case_id

    assert hits, f"{prefix}: no results for {case['query']!r}"

    returned_ids = {hit.source_id for hit in hits}
    missing = set(case["must_include_source_ids"]) - returned_ids
    assert not missing, (
        f"{prefix} ({case['scenario']}): missing expected papers {sorted(missing)}. "
        f"Got top-{case['top_k']}: {[(h.source_id, (h.title or '')[:60]) for h in hits[:5]]}"
    )

    top = hits[0]
    title = (top.title or "").lower()
    keywords = [k.lower() for k in case["top_hit_title_must_contain_any"]]
    assert any(kw in title for kw in keywords), (
        f"{prefix}: top hit title {top.title!r} missing any of {case['top_hit_title_must_contain_any']}"
    )

    min_score = float(case["min_top_score"])
    assert top.score >= min_score, (
        f"{prefix}: top score {top.score:.4f} below minimum {min_score} — retrieval quality degraded"
    )

    if expected_top := case.get("expected_top_source_id"):
        assert top.source_id == expected_top, (
            f"{prefix}: top hit {top.source_id} != expected {expected_top} ({top.title!r})"
        )


def assert_retrieval_exclusions(
    case: dict[str, Any],
    hits: list[RetrievalHitView],
    *,
    label: str = "",
) -> None:
    """Assert excluded PMIDs do not appear in the top-N window."""
    excluded = case.get("must_not_include_source_ids")
    if not excluded:
        return

    case_id = case["id"]
    prefix = f"{case_id} ({label})" if label else case_id
    top_n = int(case.get("top_n", 3))
    window = hits[:top_n]
    banned = set(excluded)
    found = banned & {hit.source_id for hit in window}
    assert not found, (
        f"{prefix} ({case['scenario']}): excluded papers in top-{top_n}: {sorted(found)}. "
        f"Window: {[(h.source_id, (h.title or '')[:50]) for h in window]}"
    )
