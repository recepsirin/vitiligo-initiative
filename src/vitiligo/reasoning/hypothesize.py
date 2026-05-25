"""Hypothesis generation: literature-, trial-, prior-, and graph-grounded candidate proposals.

Given a research intent (e.g. "stop spread in active non-segmental
vitiligo" or "drive repigmentation on acral skin"), this module:

1. Retrieves the top-K most relevant papers from the embedded corpus.
2. Retrieves the most relevant clinical trials from the trials store
   (ClinicalTrials.gov + EU CTR), preferring Phase 2/3 and trials with
   reported results.
3. Retrieves drug and target priors from Open Targets (and DrugBank later)
   for mechanistic and clinical-stage context.
4. Retrieves vitiligo-connected knowledge-graph edges (structured + LLM).
5. Asks the LLM to propose ranked therapeutic candidates supported by
   any of the four evidence streams.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from vitiligo.embed import semantic_search
from vitiligo.embed.search import SearchHit
from vitiligo.evidence import classify_document, classify_trial, evidence_level_label
from vitiligo.graph.query import GraphEdgeView, retrieve_graph_for_hypothesize
from vitiligo.logging import get_logger
from vitiligo.priors import retrieve_priors_for_hypothesize
from vitiligo.reasoning.llm import LLMClient
from vitiligo.reasoning.rag import Citation, _hit_to_citation
from vitiligo.storage import Prior, Trial
from vitiligo.trials import retrieve_relevant_trials

logger = get_logger(__name__)


@dataclass
class TrialCitation:
    """A reference to a clinical trial included in the prompt context."""

    index: int  # 1-based, scoped to the trial list (cited as [T1], [T2], ...)
    source: str  # "ctgov" | "euctr" | "ictrp"
    source_id: str
    title: str | None
    status: str | None
    phases: list[str]
    sponsors: list[str]
    countries: list[str]
    has_results: bool
    evidence_level: str
    evidence_level_label: str


@dataclass
class PriorCitation:
    """A drug or target prior from a curated knowledge base."""

    index: int  # cited as [P1], [P2], ...
    kind: str  # drug | target
    source: str
    source_id: str
    name: str
    clinical_stage: str | None
    score: float | None
    mechanisms: list[str]
    linked_trial_ids: list[str]


@dataclass
class GraphCitation:
    """A knowledge-graph edge included in the Hypothesize prompt context."""

    index: int  # cited as [G1], [G2], ...
    subject_kind: str
    subject_name: str
    predicate: str
    object_kind: str
    object_name: str
    confidence: float
    extraction_method: str
    evidence_count: int


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
    trial_citation_indices: list[int]
    prior_citation_indices: list[int]
    graph_citation_indices: list[int]


@dataclass
class HypothesisReport:
    intent: str
    candidates: list[Candidate]
    citations: list[Citation]
    trial_citations: list[TrialCitation]
    prior_citations: list[PriorCitation]
    graph_citations: list[GraphCitation]
    notes: str
    model: str


_SYSTEM_PROMPT = """You are a careful biomedical research strategist for the Vitiligo Initiative.

Your task: from retrieved papers, registered clinical trials, curated drug/target priors, AND knowledge-graph relations, propose ranked therapeutic candidates that could plausibly contribute to the user's research intent (e.g. stopping vitiligo spread, driving repigmentation, identifying novel targets).

You see four evidence streams:
- PAPERS — peer-reviewed literature, cited as [1], [2], etc.
- TRIALS — registered clinical trials from ClinicalTrials.gov and the EU CTR (CTIS), cited as [T1], [T2], etc.
- PRIORS — Open Targets drug/target associations for vitiligo, cited as [P1], [P2], etc. Drug priors include clinical stage and mechanisms; target priors include association scores.
- GRAPH — persisted entity relations (drug→target, drug→vitiligo, trial links), cited as [G1], [G2], etc. Prefer graph edges with higher confidence and structured extraction when weighing evidence.

STRICT RULES:
1. Only propose candidates explicitly supported by the retrieved evidence. Do not invent drugs, targets, or mechanisms. Every candidate's indices must reference items in the provided lists only.
2. Use TRIALS, PRIORS, and GRAPH together to upgrade evidence strength. A drug in Phase 3 for vitiligo (trial, prior, or graph) is "strong" even if literature is thin. A high-scoring target (e.g. JAK3, PTPN22) with supporting papers is stronger than either alone.
3. For each candidate: mechanism (1-2 sentences), rationale (2-3 sentences referencing all relevant streams), evidence_strength ("strong" | "moderate" | "weak" | "speculative"), risks_or_caveats.
4. Deduplicate: same drug in papers, trials, priors, and graph → ONE candidate with all relevant indices.
5. Output ONLY valid JSON. Schema:

{
  "candidates": [
    {
      "name": "string",
      "kind": "drug" | "combination" | "mechanism" | "biomarker" | "target",
      "mechanism": "string",
      "rationale": "string",
      "evidence_strength": "strong" | "moderate" | "weak" | "speculative",
      "risks_or_caveats": "string",
      "citation_indices": [int, ...],
      "trial_citation_indices": [int, ...],
      "prior_citation_indices": [int, ...],
      "graph_citation_indices": [int, ...]
    }
  ],
  "notes": "string"
}

6. Aim for 5-12 candidates ranked by combined plausibility + cure-relevance.
7. Never use marketing language. Stay scientific.
"""


def generate_hypotheses(
    intent: str,
    top_k: int = 25,
    top_trials: int = 12,
    llm: LLMClient | None = None,
) -> HypothesisReport:
    """Retrieve papers, trials, and priors; ask the LLM for ranked candidates."""
    hits = semantic_search(query=intent, top_k=top_k)
    if not hits:
        raise RuntimeError(
            "No embeddings stored yet. Run `vitiligo embed run` to index the corpus first."
        )

    trials = retrieve_relevant_trials(intent, limit=top_trials)
    priors = retrieve_priors_for_hypothesize()
    graph_edges = retrieve_graph_for_hypothesize(intent)

    citations = [_hit_to_citation(idx + 1, hit) for idx, hit in enumerate(hits)]
    trial_citations = [_trial_to_citation(idx + 1, t) for idx, t in enumerate(trials)]
    prior_citations = [_prior_to_citation(idx + 1, p) for idx, p in enumerate(priors)]
    graph_citations = [_graph_to_citation(idx + 1, e) for idx, e in enumerate(graph_edges)]

    user_prompt = _build_user_prompt(intent, hits, trials, priors, graph_edges)

    client = llm or LLMClient()
    response = client.complete(
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=5000,
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
        trial_citations=trial_citations,
        prior_citations=prior_citations,
        graph_citations=graph_citations,
        notes=notes,
        model=response.model,
    )


def _trial_to_citation(idx: int, trial: Trial) -> TrialCitation:
    src_value = trial.source.value if hasattr(trial.source, "value") else str(trial.source)
    sponsor_names = [
        s.get("name") or "" for s in (trial.sponsors or [])[:3] if isinstance(s, dict)
    ]
    sponsor_names = [s for s in sponsor_names if s]
    trial_level = classify_trial(trial)
    return TrialCitation(
        index=idx,
        source=src_value,
        source_id=trial.source_id,
        title=trial.brief_title or trial.official_title,
        status=trial.status,
        phases=list(trial.phases or []),
        sponsors=sponsor_names,
        countries=list(trial.countries or [])[:8],
        has_results=bool(trial.has_results),
        evidence_level=trial_level.value,
        evidence_level_label=evidence_level_label(trial_level),
    )


def _prior_to_citation(idx: int, prior: Prior) -> PriorCitation:
    src = prior.source.value if hasattr(prior.source, "value") else str(prior.source)
    kind = prior.kind.value if hasattr(prior.kind, "value") else str(prior.kind)
    mechs = [
        str(m.get("mechanism") or "")
        for m in (prior.mechanisms or [])
        if m.get("mechanism")
    ][:5]
    return PriorCitation(
        index=idx,
        kind=kind,
        source=src,
        source_id=prior.source_id,
        name=prior.name,
        clinical_stage=prior.clinical_stage,
        score=prior.score,
        mechanisms=mechs,
        linked_trial_ids=list(prior.linked_trial_ids or [])[:8],
    )


def _graph_to_citation(idx: int, edge: GraphEdgeView) -> GraphCitation:
    return GraphCitation(
        index=idx,
        subject_kind=edge.subject_kind,
        subject_name=edge.subject_name,
        predicate=edge.predicate,
        object_kind=edge.object_kind,
        object_name=edge.object_name,
        confidence=edge.confidence,
        extraction_method=edge.extraction_method,
        evidence_count=edge.evidence_count,
    )


def _build_user_prompt(
    intent: str,
    hits: list[SearchHit],
    trials: list[Trial],
    priors: list[Prior],
    graph_edges: list[GraphEdgeView],
) -> str:
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
        level = classify_document(doc)
        meta_bits.append(f"evidence:{evidence_level_label(level)}")
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

    if trials:
        lines.append("REGISTERED CLINICAL TRIALS:")
        lines.append("")
        for idx, trial in enumerate(trials, start=1):
            src_value = (
                trial.source.value if hasattr(trial.source, "value") else str(trial.source)
            )
            phase = ", ".join(trial.phases) if trial.phases else "—"
            sponsors = ", ".join(
                (s.get("name") or "")
                for s in (trial.sponsors or [])[:2]
                if isinstance(s, dict)
            ).strip(", ")
            countries = ", ".join(trial.countries[:6]) if trial.countries else ""
            interventions = ", ".join(
                (iv.get("name") or "?") for iv in (trial.interventions or [])[:5]
            )

            lines.append(
                f"[T{idx}] {src_value}:{trial.source_id} — {trial.brief_title or trial.official_title or '(no title)'}"
            )
            lines.append(
                f"    Status: {trial.status or 'unknown'} | Phase: {phase} | "
                f"Has results: {'yes' if trial.has_results else 'no'} | "
                f"Evidence: {evidence_level_label(classify_trial(trial))}"
            )
            if sponsors:
                lines.append(f"    Sponsors: {sponsors}")
            if countries:
                lines.append(f"    Countries: {countries}")
            if interventions:
                lines.append(f"    Interventions: {interventions}")
            if trial.summary:
                summary = trial.summary.strip()
                if len(summary) > 700:
                    summary = summary[:700] + " ..."
                lines.append(f"    Summary: {summary}")
            lines.append("")
    else:
        lines.append("REGISTERED CLINICAL TRIALS: (none retrieved for this intent)")
        lines.append("")

    if priors:
        lines.append("DRUG & TARGET PRIORS (Open Targets + DrugBank):")
        lines.append("")
        for idx, prior in enumerate(priors, start=1):
            kind = prior.kind.value if hasattr(prior.kind, "value") else str(prior.kind)
            src = prior.source.value if hasattr(prior.source, "value") else str(prior.source)
            lines.append(f"[P{idx}] {kind.upper()} {prior.name} ({src}:{prior.source_id})")
            if kind == "drug":
                stage = prior.clinical_stage or "unknown"
                lines.append(f"    Clinical stage: {stage}")
                if prior.mechanisms:
                    mechs = "; ".join(
                        str(m.get("mechanism") or "") for m in prior.mechanisms[:3]
                    )
                    lines.append(f"    Mechanisms: {mechs}")
                if prior.linked_trial_ids:
                    lines.append(f"    Linked trials: {', '.join(prior.linked_trial_ids[:6])}")
            else:
                score = prior.score if prior.score is not None else "—"
                desc = prior.description or ""
                lines.append(f"    Association score: {score}")
                if desc:
                    lines.append(f"    Gene: {desc}")
            lines.append("")
    else:
        lines.append("DRUG & TARGET PRIORS: (none — run `vitiligo ingest opentargets` or `vitiligo ingest drugbank`)")
        lines.append("")

    if graph_edges:
        lines.append("KNOWLEDGE GRAPH (vitiligo-connected relations):")
        lines.append("")
        for idx, edge in enumerate(graph_edges, start=1):
            lines.append(
                f"[G{idx}] {edge.subject_name} ({edge.subject_kind}) "
                f"—[{edge.predicate}]→ {edge.object_name} ({edge.object_kind})"
            )
            lines.append(
                f"    confidence={edge.confidence:.2f} method={edge.extraction_method} "
                f"evidence_sources={edge.evidence_count}"
            )
            lines.append("")
    else:
        lines.append(
            "KNOWLEDGE GRAPH: (none — run `vitiligo graph seed` to build from priors and trials)"
        )
        lines.append("")

    lines.append("---")
    lines.append(
        "Produce a ranked list of therapeutic candidates relevant to the research intent. "
        "Use papers, trials, priors, AND graph edges as evidence. Output JSON only."
    )
    return "\n".join(lines)


def _coerce_candidate(data: dict[str, object]) -> Candidate:
    citation_indices = _coerce_int_list(data.get("citation_indices"))
    trial_citation_indices = _coerce_int_list(data.get("trial_citation_indices"), prefix="T")
    prior_citation_indices = _coerce_int_list(data.get("prior_citation_indices"), prefix="P")
    graph_citation_indices = _coerce_int_list(data.get("graph_citation_indices"), prefix="G")
    return Candidate(
        name=str(data.get("name", "")).strip() or "(unnamed)",
        kind=str(data.get("kind", "")).strip() or "unspecified",
        mechanism=str(data.get("mechanism", "")).strip(),
        rationale=str(data.get("rationale", "")).strip(),
        evidence_strength=str(data.get("evidence_strength", "speculative")).strip().lower(),
        risks_or_caveats=str(data.get("risks_or_caveats", "")).strip(),
        citation_indices=citation_indices,
        trial_citation_indices=trial_citation_indices,
        prior_citation_indices=prior_citation_indices,
        graph_citation_indices=graph_citation_indices,
    )


def _coerce_int_list(value: object, prefix: str = "") -> list[int]:
    out: list[int] = []
    if not isinstance(value, list):
        return out
    for c in value:
        if isinstance(c, int):
            out.append(c)
        elif isinstance(c, str):
            stripped = c.strip().lstrip("[").rstrip("]")
            if prefix and stripped.upper().startswith(prefix.upper()):
                stripped = stripped[len(prefix) :]
            if stripped.isdigit():
                out.append(int(stripped))
    return out


def _parse_json(text: str) -> object:
    """Robust-ish JSON parsing that tolerates fenced code blocks."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
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
        "trial_citations": [asdict(c) for c in report.trial_citations],
        "prior_citations": [asdict(c) for c in report.prior_citations],
        "graph_citations": [asdict(c) for c in report.graph_citations],
    }
