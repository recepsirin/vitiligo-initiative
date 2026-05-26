"""Corpus-only confidence tests: candidate rankings and graph invariants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session, select

from vitiligo.graph.query import get_neighbors, search_entities, summarize_graph
from vitiligo.reports import build_candidate_report
from vitiligo.storage import get_engine
from vitiligo.storage.models import EntityKind, GraphEntity

MANIFEST = Path(__file__).resolve().parent / "fixtures" / "regression_expectations.json"

pytestmark = pytest.mark.corpus


@pytest.fixture
def expectations(require_local_corpus) -> dict:
    return json.loads(MANIFEST.read_text())


class TestCandidateReportConfidence:
    """Deterministic rankings must surface the JAK pipeline and tacrolimus."""

    def test_global_top_includes_expected_drugs(self, expectations: dict) -> None:
        spec = expectations["candidates"]
        report = build_candidate_report(top_n=int(spec["top_n"]))
        tokens = {c.canonical_token for c in report.global_top}
        missing = set(spec["must_include_tokens"]) - tokens
        assert not missing, (
            f"Candidate report missing expected drugs: {sorted(missing)}. "
            f"Top-{spec['top_n']}: {[(c.rank, c.canonical_token, c.score.total) for c in report.global_top]}"
        )

    def test_rank1_is_ruxolitinib_with_strong_score(self, expectations: dict) -> None:
        spec = expectations["candidates"]
        report = build_candidate_report(top_n=int(spec["top_n"]))
        assert report.global_top, "empty candidate report"
        rank1 = report.global_top[0]
        assert rank1.canonical_token == spec["rank1_token"], (
            f"rank 1 is {rank1.canonical_token!r}, expected {spec['rank1_token']!r}"
        )
        assert rank1.score.total >= int(spec["min_rank1_score"]), (
            f"rank 1 score {rank1.score.total} below minimum {spec['min_rank1_score']}"
        )


class TestGraphConfidence:
    """Knowledge graph seed invariants from graph-spotcheck.sh."""

    def test_vitiligo_anchor_and_neighbor_density(self, require_local_corpus) -> None:
        summary = summarize_graph()
        counts = {r.label: r.count for r in summary["total"]}
        entities = counts.get("entities", 0)
        edges = counts.get("edges", 0)
        assert entities >= 100, f"too few entities ({entities})"
        assert edges >= 100, f"too few edges ({edges})"

        with Session(get_engine(), expire_on_commit=False) as session:
            vitiligo = session.exec(
                select(GraphEntity).where(
                    GraphEntity.kind == EntityKind.DISEASE,
                    GraphEntity.key == "vitiligo",
                )
            ).first()
        assert vitiligo is not None, "missing vitiligo disease anchor node"

        neighbors = get_neighbors("vitiligo", hops=1, limit=50)
        assert len(neighbors) >= 10, f"vitiligo has only {len(neighbors)} neighbor edges"

    def test_core_entities_and_predicates(self, require_local_corpus) -> None:
        assert search_entities("ruxolitinib", limit=5), "no ruxolitinib entity"
        assert search_entities("JAK1", limit=3), "no JAK1 target entity"

        by_predicate = {r.label: r.count for r in summarize_graph().get("by_predicate", [])}
        for predicate, minimum in (("treats", 50), ("associated_with", 50), ("investigates", 50)):
            count = by_predicate.get(predicate, 0)
            assert count >= minimum, f"too few '{predicate}' edges ({count})"
