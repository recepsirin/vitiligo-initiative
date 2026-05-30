"""RAG faithfulness: retrieved evidence must appear in the LLM prompt context."""

from __future__ import annotations

import pytest
from tests.helpers.fake_llm import CapturingLLM

from vitiligo.embed.search import SearchHit
from vitiligo.reasoning.rag import ask_with_citations
from vitiligo.storage import Document, SourceKind


def test_ask_prompt_includes_every_retrieved_title(monkeypatch: pytest.MonkeyPatch) -> None:
    docs = [
        Document(source=SourceKind.PUBMED, source_id="1", title="Paper A on ruxolitinib"),
        Document(source=SourceKind.PUBMED, source_id="2", title="Paper B on NB-UVB"),
    ]
    hits = [SearchHit(document=d, score=0.9 - i * 0.01) for i, d in enumerate(docs)]
    llm = CapturingLLM(response_text="Answer with [1].")

    monkeypatch.setattr("vitiligo.reasoning.rag.semantic_search", lambda **_: hits)

    ask_with_citations("What helps vitiligo?", top_k=2, llm=llm)

    for doc in docs:
        assert doc.title in llm.captured_user
    assert "RETRIEVED PAPERS" in llm.captured_user
    assert "Cite with bracketed numbers like [1]" in llm.captured_user


def test_ask_answer_references_citation_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = Document(
        source=SourceKind.PUBMED,
        source_id="35787401",
        title="Ruxolitinib and NB-UVB combination",
        journal="JAAD",
        year=2022,
    )
    hits = [SearchHit(document=doc, score=0.92)]
    llm = CapturingLLM(response_text="Answer with [1].")
    monkeypatch.setattr("vitiligo.reasoning.rag.semantic_search", lambda **_: hits)

    answer = ask_with_citations("Combination therapy?", top_k=1, llm=llm)

    assert answer.citations[0].source_id == "35787401"
    assert answer.citations[0].title == doc.title
    assert "35787401" not in answer.answer or "[1]" in answer.answer
