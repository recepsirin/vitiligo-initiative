"""Hypothesis generation: literature-grounded candidate proposals.

Given a research intent (e.g. "stop spread in active non-segmental
vitiligo" or "drive repigmentation on acral skin"), this module:

1. Retrieves the top-K most relevant papers from the embedded corpus.
2. Asks the LLM to extract candidate interventions (drugs, combinations,
   mechanisms, biomarkers) mentioned across those papers.
3. Asks the LLM to score each candidate on plausibility and evidence
   strength, with explicit citation back to the source papers.

Output is structured JSON so downstream tools (UI, reports, knowledge
graph) can consume it directly. This is a v0 — it operates over
literature only. Once Open Targets / DrugBank / ClinicalTrials.gov are
ingested, structured priors will be added to the prompt.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from vitiligo.embed import semantic_search
from vitiligo.embed.search import SearchHit
from vitiligo.logging import get_logger
from vitiligo.reasoning.llm import LLMClient
from vitiligo.reasoning.rag import Citation, _hit_to_citation

logger = get_logger(__name__)


@dataclass
class Candidate:
    """A single proposed intervention with its rationale and evidence."""

    name: str
    kind: str  # e.g. "drug", "combination", "mechanism", "biomarker"
    mechanism: str
    rationale: str
    evidence_strength: str  # "strong" | "moderate" | "weak" | "speculative"
    risks_or_caveats: str
    citation_indices: list[int]


@dataclass
class HypothesisReport:
    intent: str
    candidates: list[Candidate]
    citations: list[Citation]
    notes: str
    model: str


_SYSTEM_PROMPT = """You are a careful biomedical research strategist for the Vitiligo Initiative.

Your task: from a set of retrieved papers, propose ranked therapeutic candidates that could plausibly contribute to the user's research intent (e.g. stopping vitiligo spread, driving repigmentation, identifying novel targets).

STRICT RULES:
1. Only propose candidates that are explicitly supported by the retrieved papers. Do not invent drugs, targets, or mechanisms. Every candidate's `citation_indices` must reference papers in the provided list.
2. For each candidate, fill in mechanism (1-2 sentences), rationale (why this fits the intent — 2-3 sentences), evidence_strength ("strong" if backed by RCT/meta-analysis, "moderate" if cohort/translational, "weak" if mouse model only, "speculative" if hypothesis-only), and risks_or_caveats (safety, off-target, prior failures, regulatory hurdles).
3. Prefer candidates with mechanistic novelty or strong repurposing potential. Deduplicate: if two papers cite the same drug, output one candidate with multiple citation_indices.
4. Output ONLY valid JSON. No prose before or after. Schema:

{
  "candidates": [
    {
      "name": "string",
      "kind": "drug" | "combination" | "mechanism" | "biomarker" | "target",
      "mechanism": "string",
      "rationale": "string",
      "evidence_strength": "strong" | "moderate" | "weak" | "speculative",
      "risks_or_caveats": "string",
      "citation_indices": [int, int, ...]
    }
  ],
  "notes": "string — caveats, gaps in literature, what's missing to validate further"
}

5. Aim for 5-12 candidates ranked roughly by combined plausibility + cure-relevance.
6. Never use marketing language. Stay scientific.
"""


def generate_hypotheses(
    intent: str,
    top_k: int = 25,
    llm: LLMClient | None = None,
) -> HypothesisReport:
    """Retrieve over the corpus and ask the LLM to extract ranked candidates."""
    hits = semantic_search(query=intent, top_k=top_k)
    if not hits:
        raise RuntimeError(
            "No embeddings stored yet. Run `vitiligo embed run` to index the corpus first."
        )

    citations = [_hit_to_citation(idx + 1, hit) for idx, hit in enumerate(hits)]
    user_prompt = _build_user_prompt(intent, hits)

    client = llm or LLMClient()
    response = client.complete(
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=4000,
        temperature=0.3,
    )

    payload = _parse_json(response.text)
    raw_candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
    candidates = [_coerce_candidate(c) for c in raw_candidates if isinstance(c, dict)]
    notes = str(payload.get("notes", "")) if isinstance(payload, dict) else ""

    return HypothesisReport(
        intent=intent,
        candidates=candidates,
        citations=citations,
        notes=notes,
        model=response.model,
    )


def _build_user_prompt(intent: str, hits: list[SearchHit]) -> str:
    lines: list[str] = [f"RESEARCH INTENT: {intent}", "", "RETRIEVED PAPERS:", ""]
    for idx, hit in enumerate(hits, start=1):
        doc = hit.document
        meta_bits: list[str] = []
        if doc.journal:
            meta_bits.append(doc.journal)
        if doc.year is not None:
            meta_bits.append(str(doc.year))
        if doc.publication_types:
            meta_bits.append(", ".join(doc.publication_types[:2]))
        meta = " | ".join(meta_bits) if meta_bits else ""

        lines.append(f"[{idx}] {doc.title or '(no title)'}")
        if meta:
            lines.append(f"    {meta}")
        if doc.abstract:
            abstract = doc.abstract.strip()
            if len(abstract) > 1200:
                abstract = abstract[:1200] + " ..."
            lines.append(f"    ABSTRACT: {abstract}")
        lines.append("")

    lines.append("---")
    lines.append(
        "Produce a ranked list of therapeutic candidates relevant to the research intent. "
        "Output JSON only, matching the schema in the system prompt."
    )
    return "\n".join(lines)


def _coerce_candidate(data: dict[str, object]) -> Candidate:
    citation_raw = data.get("citation_indices") or []
    citation_indices: list[int] = []
    if isinstance(citation_raw, list):
        for c in citation_raw:
            if isinstance(c, int):
                citation_indices.append(c)
            elif isinstance(c, str) and c.strip().lstrip("[").rstrip("]").isdigit():
                citation_indices.append(int(c.strip().lstrip("[").rstrip("]")))
    return Candidate(
        name=str(data.get("name", "")).strip() or "(unnamed)",
        kind=str(data.get("kind", "")).strip() or "unspecified",
        mechanism=str(data.get("mechanism", "")).strip(),
        rationale=str(data.get("rationale", "")).strip(),
        evidence_strength=str(data.get("evidence_strength", "speculative")).strip().lower(),
        risks_or_caveats=str(data.get("risks_or_caveats", "")).strip(),
        citation_indices=citation_indices,
    )


def _parse_json(text: str) -> object:
    """Robust-ish JSON parsing that tolerates fenced code blocks."""
    cleaned = text.strip()
    # Strip ``` fences if present
    if cleaned.startswith("```"):
        # Drop first fence line and final fence line
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse JSON from LLM output: %s", exc)
        return {}


def report_to_dict(report: HypothesisReport) -> dict[str, object]:
    return {
        "intent": report.intent,
        "model": report.model,
        "notes": report.notes,
        "candidates": [asdict(c) for c in report.candidates],
        "citations": [asdict(c) for c in report.citations],
    }
