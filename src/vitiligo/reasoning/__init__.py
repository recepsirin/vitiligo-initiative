"""Reasoning layer: LLM-driven RAG and hypothesis generation."""

from vitiligo.reasoning.exceptions import CorpusUnavailable, LLMUnavailable
from vitiligo.reasoning.hypothesize import (
    Candidate,
    HypothesisReport,
    PriorCitation,
    TrialCitation,
    generate_hypotheses,
)
from vitiligo.reasoning.llm import LLMClient
from vitiligo.reasoning.rag import Citation, RagAnswer, ask_with_citations

__all__ = [
    "Candidate",
    "Citation",
    "CorpusUnavailable",
    "HypothesisReport",
    "LLMClient",
    "LLMUnavailable",
    "PriorCitation",
    "RagAnswer",
    "TrialCitation",
    "ask_with_citations",
    "generate_hypotheses",
]
