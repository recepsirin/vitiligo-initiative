"""Unit tests for hypothesis generation orchestration (stubbed retrieval + LLM)."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from vitiligo.embed.search import SearchHit
from vitiligo.reasoning.exceptions import CorpusUnavailable
from vitiligo.reasoning.hypothesize import generate_hypotheses
from vitiligo.reasoning.llm import LLMResponse
from vitiligo.storage import Document, SourceKind


@dataclass
class _FakeLLM:
    def complete(
        self, *, system: str, user: str, max_tokens: int = 2048, temperature: float = 0.2
    ) -> LLMResponse:
        payload = {
            "candidates": [
                {
                    "name": "Ruxolitinib",
                    "kind": "drug",
                    "mechanism": "JAK1/JAK2 inhibition",
                    "rationale": "Supported by retrieved paper [1].",
                    "evidence_strength": "moderate",
                    "risks_or_caveats": "Long-term safety unknown.",
                    "citation_indices": [1],
                    "trial_citation_indices": [],
                    "prior_citation_indices": [],
                    "graph_citation_indices": [],
                }
            ],
            "notes": "Stubbed test output.",
        }
        return LLMResponse(
            text=json.dumps(payload),
            model="fake",
            input_tokens=10,
            output_tokens=20,
        )


def _sample_hit() -> SearchHit:
    doc = Document(
        source=SourceKind.PUBMED,
        source_id="999",
        title="Topical ruxolitinib for vitiligo",
        abstract="Randomized trial of ruxolitinib cream.",
    )
    return SearchHit(document=doc, score=0.88)


def test_generate_hypotheses_with_stubbed_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vitiligo.reasoning.hypothesize.semantic_search",
        lambda **_: [_sample_hit()],
    )
    monkeypatch.setattr(
        "vitiligo.reasoning.hypothesize.retrieve_relevant_trials",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "vitiligo.reasoning.hypothesize.retrieve_priors_for_hypothesize",
        lambda: [],
    )
    monkeypatch.setattr(
        "vitiligo.reasoning.hypothesize.retrieve_graph_for_hypothesize",
        lambda *args, **kwargs: [],
    )

    report = generate_hypotheses("stop spread vitiligo", top_k=1, llm=_FakeLLM())

    assert report.intent == "stop spread vitiligo"
    assert report.model == "fake"
    assert len(report.citations) == 1
    assert report.candidates[0].name == "Ruxolitinib"
    assert report.candidates[0].citation_indices == [1]
    assert report.notes == "Stubbed test output."


def test_generate_hypotheses_raises_when_corpus_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vitiligo.reasoning.hypothesize.semantic_search", lambda **_: [])

    with pytest.raises(CorpusUnavailable, match="embed"):
        generate_hypotheses("stop spread vitiligo", top_k=5, llm=_FakeLLM())
