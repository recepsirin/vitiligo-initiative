"""Unit tests for the reasoning / RAG layer (no HTTP, no full corpus)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from vitiligo.embed.search import SearchHit
from vitiligo.reasoning.exceptions import CorpusUnavailable, LLMUnavailable
from vitiligo.reasoning.llm import LLMResponse
from vitiligo.reasoning.rag import ask_with_citations
from vitiligo.storage import Document, SourceKind


@dataclass
class _FakeLLM:
    last_user: str | None = None

    def complete(self, *, system: str, user: str, max_tokens: int = 2048, temperature: float = 0.2) -> LLMResponse:
        self.last_user = user
        return LLMResponse(text="Grounded answer.", model="fake", input_tokens=1, output_tokens=2)


def test_ask_with_citations_uses_retrieved_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = Document(
        source=SourceKind.PUBMED,
        source_id="123",
        title="Vitiligo and JAK inhibitors",
        abstract="Topical ruxolitinib showed repigmentation.",
    )
    hits = [SearchHit(document=doc, score=0.92)]
    fake_llm = _FakeLLM()

    monkeypatch.setattr("vitiligo.reasoning.rag.semantic_search", lambda **_: hits)

    answer = ask_with_citations("What helps vitiligo?", top_k=1, llm=fake_llm)

    assert answer.answer == "Grounded answer."
    assert answer.model == "fake"
    assert len(answer.citations) == 1
    assert answer.citations[0].source_id == "123"
    assert fake_llm.last_user is not None
    assert "Vitiligo and JAK inhibitors" in fake_llm.last_user


def test_ask_with_citations_raises_when_corpus_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vitiligo.reasoning.rag.semantic_search", lambda **_: [])

    with pytest.raises(CorpusUnavailable, match="embed"):
        ask_with_citations("What is vitiligo?", top_k=3, llm=_FakeLLM())


def test_llm_client_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import vitiligo.config as cfg

    cfg._settings = None

    from vitiligo.reasoning.llm import LLMClient

    with pytest.raises(LLMUnavailable, match="ANTHROPIC"):
        LLMClient()
