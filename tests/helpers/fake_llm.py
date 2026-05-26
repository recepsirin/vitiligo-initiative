"""Fake LLM client for RAG faithfulness tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from vitiligo.reasoning.llm import LLMResponse


@dataclass
class CapturingLLM:
    """Records prompts and returns a deterministic citation-shaped answer."""

    captured_system: str = ""
    captured_user: str = ""
    response_text: str = "Answer grounded in retrieved papers [1, 2]."

    def complete(
        self, *, system: str, user: str, max_tokens: int = 2048, temperature: float = 0.2
    ) -> LLMResponse:
        self.captured_system = system
        self.captured_user = user
        return LLMResponse(
            text=self.response_text,
            model="fake-confidence",
            input_tokens=1,
            output_tokens=1,
        )


@dataclass
class CapturingHypothesizeLLM:
    """Returns valid Hypothesize JSON and records the user prompt."""

    captured_system: str = ""
    captured_user: str = ""
    candidate_names: list[str] = field(default_factory=lambda: ["Ruxolitinib"])

    def complete(
        self, *, system: str, user: str, max_tokens: int = 2048, temperature: float = 0.2
    ) -> LLMResponse:
        self.captured_system = system
        self.captured_user = user
        has_trials = "REGISTERED CLINICAL TRIALS:" in user and "(none retrieved" not in user
        has_priors = "DRUG & TARGET PRIORS" in user and "(none —" not in user
        has_graph = "KNOWLEDGE GRAPH" in user and "(none —" not in user
        candidates: list[dict[str, Any]] = []
        for name in self.candidate_names:
            rationale = "Supported by retrieved paper [1]."
            if has_trials:
                rationale = "Supported by retrieved paper [1] and trial [T1]."
            candidates.append(
                {
                    "name": name,
                    "kind": "drug",
                    "mechanism": "Mechanism grounded in retrieved evidence.",
                    "rationale": rationale,
                    "evidence_strength": "moderate",
                    "risks_or_caveats": "Stubbed confidence output.",
                    "citation_indices": [1],
                    "trial_citation_indices": [1] if has_trials else [],
                    "prior_citation_indices": [1] if has_priors else [],
                    "graph_citation_indices": [1] if has_graph else [],
                }
            )
        payload = {"candidates": candidates, "notes": "Stubbed hypothesize output."}
        return LLMResponse(
            text=json.dumps(payload),
            model="fake-confidence",
            input_tokens=1,
            output_tokens=1,
        )


def install_capturing_llm(monkeypatch: pytest.MonkeyPatch) -> CapturingLLM:
    """Patch ``LLMClient`` so ``ask_with_citations`` uses a capturing fake."""
    llm = CapturingLLM()
    monkeypatch.setattr("vitiligo.reasoning.rag.LLMClient", lambda: llm)
    return llm


def install_capturing_hypothesize_llm(
    monkeypatch: pytest.MonkeyPatch,
    *,
    candidate_names: list[str] | None = None,
) -> CapturingHypothesizeLLM:
    """Patch ``LLMClient`` for ``generate_hypotheses``."""
    llm = CapturingHypothesizeLLM(
        candidate_names=list(candidate_names or ["Ruxolitinib"]),
    )
    monkeypatch.setattr("vitiligo.reasoning.hypothesize.LLMClient", lambda: llm)
    return llm
