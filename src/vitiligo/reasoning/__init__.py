"""Reasoning layer: LLM-driven RAG and hypothesis generation."""

from vitiligo.reasoning.hypothesize import (
    Candidate,
    HypothesisReport,
    TrialCitation,
    generate_hypotheses,
)
from vitiligo.reasoning.llm import LLMClient, LLMUnavailable
from vitiligo.reasoning.rag import Citation, RagAnswer, ask_with_citations

__all__ = [
    "Candidate",
    "Citation",
    "HypothesisReport",
    "LLMClient",
    "LLMUnavailable",
    "RagAnswer",
    "TrialCitation",
    "ask_with_citations",
    "generate_hypotheses",
]
