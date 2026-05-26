"""Full-corpus confidence tests — candidate rankings require priors, graph, and trials."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vitiligo.reports import build_candidate_report

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
