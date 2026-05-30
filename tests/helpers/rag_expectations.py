"""Shared assertions for Ask / RAG citation output."""

from __future__ import annotations

import re
from typing import Any

_BRACKET_CITE = re.compile(r"\[([^\]]+)\]")


def bracket_citation_indices(answer: str) -> set[int]:
    """Parse numeric indices from bracket citations like ``[1]`` or ``[1, 3]``."""
    indices: set[int] = set()
    for group in _BRACKET_CITE.findall(answer):
        for token in re.split(r"[\s,]+", group.strip()):
            token = token.strip()
            if token.isdigit():
                indices.add(int(token))
    return indices


def assert_answer_cites_only_retrieved(answer: str, citation_count: int) -> None:
    """Every ``[n]`` in the model answer must refer to a retrieved citation index."""
    cited = bracket_citation_indices(answer)
    assert cited, "answer contains no bracket citation indices"
    invalid = {index for index in cited if index < 1 or index > citation_count}
    assert not invalid, (
        f"answer cites out-of-range indices {sorted(invalid)} "
        f"(valid 1..{citation_count}): {answer!r}"
    )


def assert_hypothesize_candidate_citations(
    candidates: list[dict[str, Any]],
    *,
    paper_count: int,
    trial_count: int = 0,
    prior_count: int = 0,
    graph_count: int = 0,
) -> None:
    """Candidate JSON must only reference retrieved paper/trial/prior/graph indices."""
    import re

    for cand in candidates:
        name = cand.get("name", "(unnamed)")
        for key, limit, label in (
            ("citation_indices", paper_count, "paper"),
            ("trial_citation_indices", trial_count, "trial"),
            ("prior_citation_indices", prior_count, "prior"),
            ("graph_citation_indices", graph_count, "graph"),
        ):
            indices = cand.get(key) or []
            if not indices:
                continue
            invalid = {index for index in indices if index < 1 or index > limit}
            assert not invalid, (
                f"{name}: {key} out of range {sorted(invalid)} (valid 1..{limit} {label})"
            )
        rationale = str(cand.get("rationale", ""))
        for token in re.findall(r"\[(T?\d+)\]", rationale):
            if token.startswith("T"):
                idx = int(token[1:])
                assert 1 <= idx <= trial_count, f"{name}: rationale cites missing trial {token}"
            else:
                idx = int(token)
                assert 1 <= idx <= paper_count, f"{name}: rationale cites missing paper [{idx}]"
