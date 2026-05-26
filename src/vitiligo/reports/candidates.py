"""Evidence-first therapeutic candidate reports.

Rankings are computed deterministically from Open Targets priors, registered
trials, knowledge-graph edges, and semantic literature retrieval. Every score
component is exposed in the output for accountability.

Optional LLM synthesis (``include_llm=True``) adds narrative rationale via
``generate_hypotheses`` when ``ANTHROPIC_API_KEY`` is configured.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vitiligo import __version__
from vitiligo.corpus_stats import get_corpus_stats
from vitiligo.embed import semantic_search
from vitiligo.graph.query import GraphEdgeView, get_neighbors, search_entities
from vitiligo.priors import list_drug_priors
from vitiligo.storage import Prior, Trial
from vitiligo.trials import TrialFilter, list_trials, retrieve_relevant_trials

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INTENTS_PATH = _PROJECT_ROOT / "docs" / "candidate-intents.json"

_STAGE_ORDER = (
    "APPROVAL",
    "PHASE_4",
    "PHASE_3",
    "PHASE_2_3",
    "PHASE_2",
    "PHASE_1",
    "EARLY_PHASE1",
    "UNKNOWN",
)
_STAGE_POINTS: dict[str, int] = {
    "APPROVAL": 40,
    "PHASE_4": 35,
    "PHASE_3": 30,
    "PHASE_2_3": 25,
    "PHASE_2": 20,
    "PHASE_1": 8,
    "EARLY_PHASE1": 5,
    "UNKNOWN": 0,
}
_HIGH_SIGNAL_PHASES = frozenset({"PHASE_2", "PHASE_2_3", "PHASE_3", "PHASE_4"})


@dataclass(frozen=True)
class IntentSpec:
    id: str
    title: str
    query: str
    goal: str


@dataclass
class LiteratureRef:
    rank: int
    source: str
    source_id: str
    title: str | None
    year: int | None
    evidence_level: str
    score: float


@dataclass
class TrialRef:
    source: str
    source_id: str
    title: str | None
    status: str | None
    phases: list[str]
    has_results: bool


@dataclass
class GraphRef:
    predicate: str
    subject_name: str
    object_name: str
    confidence: float
    extraction_method: str


@dataclass
class ScoreBreakdown:
    prior_stage: int
    graph: int
    trials: int
    literature: int

    @property
    def total(self) -> int:
        return self.prior_stage + self.graph + self.trials + self.literature


@dataclass
class RankedCandidate:
    rank: int
    name: str
    canonical_token: str
    clinical_stage: str | None
    evidence_strength: str
    score: ScoreBreakdown
    mechanisms: list[str]
    prior_source_id: str | None
    graph_refs: list[GraphRef]
    trial_refs: list[TrialRef]
    literature_refs: list[LiteratureRef]
    caveats: list[str]
    llm_rationale: str | None = None


@dataclass
class IntentReport:
    intent: IntentSpec
    candidates: list[RankedCandidate]


@dataclass
class CandidateReport:
    generated_at: str
    engine_version: str
    methodology: str
    corpus: dict[str, Any]
    intents: list[IntentReport]
    global_top: list[RankedCandidate]
    notes: list[str] = field(default_factory=list)


def load_intents(path: Path | None = None) -> list[IntentSpec]:
    spec_path = path or DEFAULT_INTENTS_PATH
    raw = json.loads(spec_path.read_text())
    return [
        IntentSpec(
            id=item["id"],
            title=item["title"],
            query=item["query"],
            goal=item.get("goal", "general"),
        )
        for item in raw["intents"]
    ]


def normalize_drug_token(name: str) -> str:
    """Map display names to a deduplication token (lowercase stem)."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    words = [w for w in cleaned.split() if len(w) >= 4 and w not in _STOPWORDS]
    if not words:
        words = [w for w in cleaned.split() if w and w not in _STOPWORDS]
    return words[0] if words else cleaned.strip() or name.lower()


_STOPWORDS = frozenset(
    {
        "placebo",
        "cream",
        "topical",
        "oral",
        "phosphate",
        "tablet",
        "capsule",
        "anhydrous",
        "propionate",
        "cream bid",
        "vitiligo",
    }
)


def _stage_points(stage: str | None) -> int:
    if not stage:
        return 0
    return _STAGE_POINTS.get(stage.upper(), 0)


def _best_stage_from_trials(trials: list[Trial]) -> str | None:
    phases: list[str] = []
    for trial in trials:
        phases.extend(trial.phases or [])
    return _best_stage(phases) if phases else None


def _best_stage(stages: list[str | None]) -> str | None:
    present = {s.upper() for s in stages if s}
    for stage in _STAGE_ORDER:
        if stage in present:
            return stage
    return None


def _evidence_strength(score: int) -> str:
    if score >= 70:
        return "strong"
    if score >= 45:
        return "moderate"
    if score >= 25:
        return "weak"
    return "speculative"


def _trial_matches_drug(trial: Trial, token: str) -> bool:
    haystack = " ".join(
        filter(
            None,
            [
                trial.brief_title or "",
                trial.official_title or "",
                trial.summary or "",
                " ".join(
                    (iv.get("name") or "") for iv in (trial.interventions or []) if isinstance(iv, dict)
                ),
            ],
        )
    ).lower()
    return token in haystack


def _graph_points(edges: list[GraphEdgeView]) -> int:
    points = 0
    for edge in edges:
        pred = edge.predicate.lower()
        if pred == "treats":
            points += int(25 * edge.confidence)
        elif pred == "investigates":
            points += int(15 * edge.confidence)
        elif pred in {"tested_in", "inhibits", "targets"}:
            points += int(8 * edge.confidence)
    return min(points, 40)


def _trial_points(trials: list[Trial]) -> int:
    points = 0
    for trial in trials:
        if any(p in _HIGH_SIGNAL_PHASES for p in (trial.phases or [])):
            points += 15
        if trial.has_results:
            points += 8
        if (trial.status or "").upper() in {"RECRUITING", "ACTIVE_NOT_RECRUITING", "AUTHORISED"}:
            points += 5
    return min(points, 35)


def _literature_points(refs: list[LiteratureRef]) -> int:
    return min(len(refs) * 4, 20)


@dataclass
class _DrugBundle:
    display_name: str
    token: str
    prior: Prior | None = None
    graph_edges: list[GraphEdgeView] = field(default_factory=list)
    trials: list[Trial] = field(default_factory=list)
    mechanisms: list[str] = field(default_factory=list)

    def merge(self, other: _DrugBundle) -> None:
        if self.prior is None:
            self.prior = other.prior
        self.graph_edges.extend(other.graph_edges)
        self.trials.extend(other.trials)
        for mech in other.mechanisms:
            if mech not in self.mechanisms:
                self.mechanisms.append(mech)
        if len(other.display_name) < len(self.display_name) and other.display_name:
            self.display_name = other.display_name.title()


def _collect_drug_bundles() -> dict[str, _DrugBundle]:
    bundles: dict[str, _DrugBundle] = {}

    def upsert(name: str, **kwargs: Any) -> _DrugBundle:
        token = normalize_drug_token(name)
        if token not in bundles:
            bundles[token] = _DrugBundle(display_name=name.strip(), token=token)
        bundle = bundles[token]
        if "prior" in kwargs and kwargs["prior"] is not None:
            bundle.prior = kwargs["prior"]
            for mech in bundle.prior.mechanisms or []:
                label = mech.get("mechanism") if isinstance(mech, dict) else str(mech)
                if label and label not in bundle.mechanisms:
                    bundle.mechanisms.append(label)
        if "graph_edges" in kwargs:
            bundle.graph_edges.extend(kwargs["graph_edges"])
        if "trials" in kwargs:
            for trial in kwargs["trials"]:
                if trial not in bundle.trials:
                    bundle.trials.append(trial)
        return bundle

    for prior in list_drug_priors(limit=80):
        if _stage_points(prior.clinical_stage) < _STAGE_POINTS["PHASE_2"]:
            continue
        upsert(prior.name, prior=prior)

    for entity in search_entities("vitiligo", limit=5):
        kind = entity.kind.value if hasattr(entity.kind, "value") else str(entity.kind)
        if kind != "disease":
            continue
        for edge in get_neighbors(entity.name, hops=1, limit=200):
            drug_name = None
            if edge.subject_kind == "drug" and edge.object_name.lower() == "vitiligo":
                drug_name = edge.subject_name
            elif edge.object_kind == "drug" and edge.subject_name.lower() == "vitiligo":
                drug_name = edge.object_name
            if drug_name:
                upsert(drug_name, graph_edges=[edge])

    for prior_token in list(bundles):
        for edge in get_neighbors(bundles[prior_token].display_name, hops=1, limit=20):
            if "vitiligo" in (edge.object_name + edge.subject_name).lower():
                bundles[prior_token].graph_edges.append(edge)

    all_trials: list[Trial] = []
    for intent in load_intents():
        all_trials.extend(retrieve_relevant_trials(intent.query, limit=20, require_high_signal=True))
    seen_trial: set[tuple[str, str]] = set()
    unique_trials: list[Trial] = []
    for trial in all_trials:
        key = (str(trial.source), trial.source_id)
        if key not in seen_trial:
            seen_trial.add(key)
            unique_trials.append(trial)

    for token, bundle in bundles.items():
        matched: list[Trial] = []
        seen: set[tuple[str, str]] = set()
        for trial in unique_trials:
            if _trial_matches_drug(trial, token):
                key = (str(trial.source), trial.source_id)
                if key not in seen:
                    seen.add(key)
                    matched.append(trial)
        # Direct registry lookup by intervention name (catches trials missed by intent overlap).
        for trial in list_trials(TrialFilter(query=token, limit=15)):
            key = (str(trial.source), trial.source_id)
            if key not in seen:
                seen.add(key)
                matched.append(trial)
        bundle.trials = matched

    return bundles


def _literature_for_drug(token: str, intent_query: str, top_k: int = 25) -> list[LiteratureRef]:
    hits = semantic_search(query=intent_query, top_k=top_k)
    refs: list[LiteratureRef] = []
    for rank, hit in enumerate(hits, start=1):
        text = f"{hit.document.title or ''} {hit.document.abstract or ''}".lower()
        if token not in text:
            continue
        from vitiligo.evidence import classify_document, evidence_level_label

        level = classify_document(hit.document)
        refs.append(
            LiteratureRef(
                rank=rank,
                source=hit.document.source.value,
                source_id=hit.document.source_id,
                title=hit.document.title,
                year=hit.document.year,
                evidence_level=evidence_level_label(level),
                score=round(hit.score, 4),
            )
        )
    return refs[:5]


def _rank_candidates_for_intent(
    bundles: dict[str, _DrugBundle],
    intent: IntentSpec,
    *,
    top_n: int = 10,
) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []

    for token, bundle in bundles.items():
        stage = bundle.prior.clinical_stage if bundle.prior else _best_stage_from_trials(bundle.trials)

        graph_pts = _graph_points(bundle.graph_edges)
        trial_pts = _trial_points(bundle.trials)
        lit_refs = _literature_for_drug(token, intent.query)
        lit_pts = _literature_points(lit_refs)
        prior_pts = _stage_points(stage)

        if prior_pts + graph_pts + trial_pts + lit_pts < 15:
            continue

        score = ScoreBreakdown(
            prior_stage=prior_pts,
            graph=graph_pts,
            trials=trial_pts,
            literature=lit_pts,
        )

        caveats: list[str] = []
        if not bundle.prior:
            caveats.append("No Open Targets prior — graph/trial evidence only.")
        if not lit_refs:
            caveats.append("No intent-matched papers in top semantic retrieval.")
        if stage in (None, "UNKNOWN"):
            caveats.append("Clinical stage unknown in priors.")

        ranked.append(
            RankedCandidate(
                rank=0,
                name=bundle.display_name,
                canonical_token=token,
                clinical_stage=stage,
                evidence_strength=_evidence_strength(score.total),
                score=score,
                mechanisms=bundle.mechanisms[:5],
                prior_source_id=bundle.prior.source_id if bundle.prior else None,
                graph_refs=[
                    GraphRef(
                        predicate=e.predicate,
                        subject_name=e.subject_name,
                        object_name=e.object_name,
                        confidence=e.confidence,
                        extraction_method=e.extraction_method,
                    )
                    for e in bundle.graph_edges[:6]
                ],
                trial_refs=[
                    TrialRef(
                        source=t.source.value if hasattr(t.source, "value") else str(t.source),
                        source_id=t.source_id,
                        title=t.brief_title,
                        status=t.status,
                        phases=list(t.phases or []),
                        has_results=bool(t.has_results),
                    )
                    for t in bundle.trials[:5]
                ],
                literature_refs=lit_refs,
                caveats=caveats,
            )
        )

    ranked.sort(key=lambda c: (c.score.total, c.score.prior_stage, c.score.trials), reverse=True)
    for idx, cand in enumerate(ranked[:top_n], start=1):
        cand.rank = idx
    return ranked[:top_n]


def build_candidate_report(
    *,
    intents_path: Path | None = None,
    top_n: int = 10,
    include_llm: bool = False,
) -> CandidateReport:
    """Build a reproducible candidate report from structured evidence."""
    intents = load_intents(intents_path)
    bundles = _collect_drug_bundles()
    corpus = get_corpus_stats()

    intent_reports: list[IntentReport] = []
    aggregate_scores: dict[str, tuple[RankedCandidate, int]] = {}

    for intent in intents:
        candidates = _rank_candidates_for_intent(bundles, intent, top_n=top_n)
        if include_llm:
            _attach_llm_rationale(intent, candidates)
        intent_reports.append(IntentReport(intent=intent, candidates=candidates))
        for cand in candidates:
            prev = aggregate_scores.get(cand.canonical_token)
            if prev is None or cand.score.total > prev[1]:
                aggregate_scores[cand.canonical_token] = (cand, cand.score.total)

    global_sorted = sorted(aggregate_scores.values(), key=lambda x: x[1], reverse=True)
    global_top: list[RankedCandidate] = []
    for idx, (cand, _) in enumerate(global_sorted[:top_n], start=1):
        global_top.append(replace(cand, rank=idx))

    notes = [
        "Deterministic ranking — not a clinical recommendation.",
        "Score rubric: prior clinical stage (0-40) + graph edges (0-40) + trials (0-35) + literature (0-20).",
        "Re-run after corpus updates: vitiligo report candidates",
    ]
    if include_llm:
        notes.append("LLM rationale attached where ANTHROPIC_API_KEY is configured.")

    return CandidateReport(
        generated_at=datetime.now(UTC).isoformat(),
        engine_version=__version__,
        methodology=_METHODOLOGY,
        corpus=corpus,
        intents=intent_reports,
        global_top=global_top,
        notes=notes,
    )


def _attach_llm_rationale(intent: IntentSpec, candidates: list[RankedCandidate]) -> None:
    try:
        from vitiligo.reasoning import CorpusUnavailable, LLMUnavailable, generate_hypotheses

        report = generate_hypotheses(intent=intent.query)
    except (LLMUnavailable, CorpusUnavailable):
        return

    by_token = {normalize_drug_token(c.name): c for c in report.candidates}
    for cand in candidates:
        llm = by_token.get(cand.canonical_token)
        if llm:
            cand.llm_rationale = llm.rationale


_METHODOLOGY = (
    "Candidates are aggregated from Open Targets drug priors (Phase 2+), knowledge-graph "
    "edges linking drugs to vitiligo, registered trials whose interventions match the drug "
    "stem, and semantic literature retrieval for each intent query. Scores are transparent "
    "and reproducible from the local corpus snapshot."
)


def _candidate_dict(candidate: RankedCandidate) -> dict[str, Any]:
    data = asdict(candidate)
    data["score"]["total"] = candidate.score.total
    return data


def report_to_dict(report: CandidateReport) -> dict[str, Any]:
    return {
        "generated_at": report.generated_at,
        "engine_version": report.engine_version,
        "methodology": report.methodology,
        "corpus": report.corpus,
        "notes": report.notes,
        "global_top": [_candidate_dict(c) for c in report.global_top],
        "intents": [
            {
                "intent": asdict(ir.intent),
                "candidates": [_candidate_dict(c) for c in ir.candidates],
            }
            for ir in report.intents
        ],
    }


def render_candidate_report_markdown(report: CandidateReport) -> str:
    lines: list[str] = [
        "# Therapeutic Candidate Report v1",
        "",
        f"**Generated:** {report.generated_at}  ",
        f"**Engine:** v{report.engine_version}  ",
        "**Status:** Research hypothesis ranking — not medical advice, not an endorsement.",
        "",
        "## Methodology",
        "",
        report.methodology,
        "",
        "### Score rubric",
        "",
        "| Component | Max points | Source |",
        "|-----------|------------|--------|",
        "| Prior clinical stage | 40 | Open Targets (`EFO_0004208`) |",
        "| Knowledge graph | 40 | `treats` / `investigates` / trial links |",
        "| Registered trials | 35 | CT.gov, EU CTR, ICTRP |",
        "| Literature retrieval | 20 | Semantic search (top-K per intent) |",
        "",
        f"**Corpus snapshot:** {report.corpus.get('documents', 0):,} documents, "
        f"{report.corpus.get('trials', 0)} trials, "
        f"{report.corpus.get('graph_entities', 0)} graph entities.",
        "",
        "## Global top candidates (aggregated across intents)",
        "",
    ]

    for cand in report.global_top:
        lines.extend(_render_candidate_block(cand))

    for ir in report.intents:
        lines.extend(
            [
                f"## Intent: {ir.intent.title}",
                "",
                f"**Query:** `{ir.intent.query}`  ",
                f"**Goal:** {ir.intent.goal}",
                "",
            ]
        )
        if not ir.candidates:
            lines.append("*No candidates met minimum evidence threshold for this intent.*")
            lines.append("")
            continue
        for cand in ir.candidates:
            lines.extend(_render_candidate_block(cand))

    lines.extend(
        [
            "## Accountability notes",
            "",
            *[f"- {note}" for note in report.notes],
            "",
            "Reproduce: `vitiligo report candidates --json exports/candidate-report.json "
            "--markdown docs/candidate-report-v1.md`",
            "",
        ]
    )
    return "\n".join(lines)


def _render_candidate_block(cand: RankedCandidate) -> list[str]:
    s = cand.score
    lines = [
        f"### #{cand.rank} {cand.name}",
        "",
        f"**Evidence strength:** {cand.evidence_strength}  ",
        f"**Score:** {s.total} (prior {s.prior_stage} + graph {s.graph} + trials {s.trials} + literature {s.literature})  ",
        f"**Clinical stage (prior):** {cand.clinical_stage or 'unknown'}  ",
    ]
    if cand.mechanisms:
        lines.append(f"**Mechanisms:** {'; '.join(cand.mechanisms[:3])}  ")
    if cand.prior_source_id:
        lines.append(f"**Open Targets ID:** `{cand.prior_source_id}`  ")
    lines.append("")

    if cand.trial_refs:
        lines.append("**Trials:**")
        for t in cand.trial_refs:
            phases = ", ".join(t.phases) if t.phases else "—"
            results = "results" if t.has_results else "no results yet"
            lines.append(
                f"- [{t.source}:{t.source_id}] {t.title or '(untitled)'} — {t.status}, {phases}, {results}"
            )
        lines.append("")

    if cand.graph_refs:
        lines.append("**Graph:**")
        for g in cand.graph_refs[:4]:
            lines.append(
                f"- {g.subject_name} —[{g.predicate}]→ {g.object_name} "
                f"(conf={g.confidence:.2f}, {g.extraction_method})"
            )
        lines.append("")

    if cand.literature_refs:
        lines.append("**Literature (intent retrieval):**")
        for ref in cand.literature_refs:
            lines.append(
                f"- [{ref.source}:{ref.source_id}] {ref.title or '(untitled)'} "
                f"({ref.year or '?'}) — {ref.evidence_level}, score={ref.score}"
            )
        lines.append("")

    if cand.caveats:
        lines.append("**Caveats:** " + " ".join(cand.caveats))
        lines.append("")

    if cand.llm_rationale:
        lines.append(f"**LLM rationale (advisory):** {cand.llm_rationale}")
        lines.append("")

    return lines
