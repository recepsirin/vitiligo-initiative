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
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from vitiligo import __version__
from vitiligo.corpus_stats import get_corpus_stats
from vitiligo.embed import semantic_search
from vitiligo.embed.search import SearchHit
from vitiligo.graph.query import GraphEdgeView, get_neighbors, search_entities
from vitiligo.priors import clinical_stage_rank, list_drug_priors
from vitiligo.storage import Document, Prior, SourceKind, Trial
from vitiligo.trials import TrialFilter, list_trials, retrieve_relevant_trials

# Shipped as package data so non-editable installs (Docker, wheels) find it.
DEFAULT_INTENTS_RESOURCE = "candidate-intents.json"

# Stage labels use the Open Targets prior format (PHASE_3, EARLY_PHASE_1).
# Registry phases (CT.gov "PHASE3", "EARLY_PHASE1") go through
# ``normalize_stage`` before any lookup here.
_STAGE_ORDER = (
    "APPROVAL",
    "PHASE_4",
    "PHASE_3",
    "PHASE_2_3",
    "PHASE_2",
    "PHASE_1_2",
    "PHASE_1",
    "EARLY_PHASE_1",
    "UNKNOWN",
)
_STAGE_POINTS: dict[str, int] = {
    "APPROVAL": 40,
    "PHASE_4": 35,
    "PHASE_3": 30,
    "PHASE_2_3": 25,  # midpoint of PHASE_2 and PHASE_3
    "PHASE_2": 20,
    "PHASE_1_2": 8,  # credited as PHASE_1 (conservative)
    "PHASE_1": 8,
    "EARLY_PHASE_1": 5,
    "UNKNOWN": 0,
}
_LITERATURE_TOP_K = 25

_REGISTRY_PHASE_RE = re.compile(r"^PHASE(\d)$")


def normalize_stage(label: str) -> str:
    """Map registry phase labels (``PHASE3``, ``EARLY_PHASE1``) to prior format."""
    upper = label.strip().upper()
    if upper == "EARLY_PHASE1":
        return "EARLY_PHASE_1"
    match = _REGISTRY_PHASE_RE.match(upper)
    return f"PHASE_{match.group(1)}" if match else upper


def trial_stage(phases: list[str]) -> str | None:
    """Collapse one trial's registry phase list into a single stage label.

    CT.gov encodes a Phase 2/3 trial as ``["PHASE2", "PHASE3"]``; that maps
    to ``PHASE_2_3`` rather than being credited as a full Phase 3.
    """
    stages = {normalize_stage(p) for p in phases if p}
    if stages == {"PHASE_2", "PHASE_3"}:
        return "PHASE_2_3"
    if stages == {"PHASE_1", "PHASE_2"}:
        return "PHASE_1_2"
    return _best_stage(list(stages))


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
    """Load research intents from ``path``, or the packaged defaults."""
    if path is not None:
        text = path.read_text(encoding="utf-8")
    else:
        text = (
            resources.files("vitiligo.reports")
            .joinpath(DEFAULT_INTENTS_RESOURCE)
            .read_text(encoding="utf-8")
        )
    raw = json.loads(text)
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
    return _STAGE_POINTS.get(normalize_stage(stage), 0)


def _best_stage_from_trials(trials: list[Trial]) -> str | None:
    return _best_stage([trial_stage(trial.phases or []) for trial in trials])


def _best_stage(stages: Sequence[str | None]) -> str | None:
    present = {normalize_stage(s) for s in stages if s}
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
                    (iv.get("name") or "")
                    for iv in (trial.interventions or [])
                    if isinstance(iv, dict)
                ),
            ],
        )
    ).lower()
    return token in haystack


def _graph_points(edges: list[GraphEdgeView]) -> int:
    """Score graph edges that add evidence beyond the prior and trial components.

    Structured edges are seeded from the same priors and trials those components
    already score (``graph.seed``), so only edges extracted from papers count.
    """
    points = 0
    seen: set[int] = set()
    for edge in edges:
        if edge.extraction_method == "structured" or edge.id in seen:
            continue
        seen.add(edge.id)
        pred = edge.predicate.lower()
        if pred == "treats":
            points += int(25 * edge.confidence)
        elif pred == "investigates":
            points += int(15 * edge.confidence)
        elif pred in {"tested_in", "inhibits", "targets"}:
            points += int(8 * edge.confidence)
    return min(points, 40)


_ACTIVE_TRIAL_STATUSES = frozenset({"RECRUITING", "ACTIVE_NOT_RECRUITING", "AUTHORISED"})


def _trial_points(trials: list[Trial]) -> int:
    """Score the strength of a drug's registered-trial portfolio (0-35).

    Rewards the best evidence rather than the number of trials, so a long
    tail of small studies cannot max out the component:
    - most advanced trial phase: Phase 3/4 -> 15, Phase 2 or 2/3 -> 10, earlier -> 3
    - posted results: on a Phase 2+ trial -> 10, otherwise on any trial -> 5
    - at least one recruiting / active / authorised trial -> 5
    - breadth: +1 per additional trial, up to +5
    """
    if not trials:
        return 0
    ranks = [clinical_stage_rank(trial_stage(t.phases or [])) for t in trials]
    best = max(ranks)
    if best >= clinical_stage_rank("PHASE_3"):
        phase_pts = 15
    elif best >= clinical_stage_rank("PHASE_2"):
        phase_pts = 10
    elif best > 0:
        phase_pts = 3
    else:
        phase_pts = 0

    with_results = [rank for t, rank in zip(trials, ranks, strict=True) if t.has_results]
    if any(rank >= clinical_stage_rank("PHASE_2") for rank in with_results):
        results_pts = 10
    elif with_results:
        results_pts = 5
    else:
        results_pts = 0

    active_pts = 5 if any((t.status or "").upper() in _ACTIVE_TRIAL_STATUSES for t in trials) else 0
    breadth_pts = min(len(trials) - 1, 5)
    return phase_pts + results_pts + active_pts + breadth_pts


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
            prior = kwargs["prior"]
            # Salt forms share a stem (RITLECITINIB / RITLECITINIB TOSYLATE);
            # keep whichever record reports the most advanced clinical stage.
            if bundle.prior is None or clinical_stage_rank(
                prior.clinical_stage
            ) > clinical_stage_rank(bundle.prior.clinical_stage):
                bundle.prior = prior
            for mech in prior.mechanisms or []:
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
        all_trials.extend(
            retrieve_relevant_trials(intent.query, limit=20, require_high_signal=True)
        )
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


def _paper_key(document: Document) -> str:
    """One key per paper: a PMC full text resolves to its PubMed ID when it has one."""
    source = SourceKind(document.source)
    if source == SourceKind.PUBMED:
        return document.source_id
    pmid = (document.raw_metadata or {}).get("pmid") if source == SourceKind.PMC else None
    if pmid is not None and str(pmid).isdigit():
        return str(pmid)
    return f"{source.value}:{document.source_id}"


def _literature_for_drug(token: str, hits: list[SearchHit]) -> list[LiteratureRef]:
    """Intent-retrieved papers (``hits``, in rank order) that mention ``token``.

    A paper held as both a PubMed and a PMC record counts once, at its better rank.
    """
    refs: list[LiteratureRef] = []
    seen: set[str] = set()
    for rank, hit in enumerate(hits, start=1):
        text = f"{hit.document.title or ''} {hit.document.abstract or ''}".lower()
        if token not in text:
            continue
        key = _paper_key(hit.document)
        if key in seen:
            continue
        seen.add(key)
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
    # One retrieval per intent; each drug filters the same ranked hits.
    intent_hits = semantic_search(query=intent.query, top_k=_LITERATURE_TOP_K)

    for token, bundle in bundles.items():
        stage = (
            bundle.prior.clinical_stage if bundle.prior else _best_stage_from_trials(bundle.trials)
        )

        graph_pts = _graph_points(bundle.graph_edges)
        trial_pts = _trial_points(bundle.trials)
        lit_refs = _literature_for_drug(token, intent_hits)
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
        "The score measures evidence maturity: how far and how much a drug has been studied in vitiligo. "
        "It is not a ranking of therapeutic potential; a promising but little-studied target scores low.",
        "Each source counts once: graph edges seeded from priors and trials are not scored again "
        "(only edges extracted from papers count), and a paper held in both PubMed and PMC counts once.",
        "Prior stage and top trial phase both reflect clinical development, so they overlap.",
        "Trials score the best evidence (top phase 15, posted Phase 2+ results 10, active trial 5, breadth up to 5), not trial count.",
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
    "and reproducible from the local corpus snapshot. The score ranks evidence maturity, "
    "not therapeutic potential."
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
        "| Knowledge graph | 40 | Edges extracted from papers (seeded edges restate priors and trials) |",
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
        lines.extend(_render_intent_table(ir.candidates))

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


def _render_intent_table(candidates: list[RankedCandidate]) -> list[str]:
    """One row per candidate; full evidence cards appear once, under the global top."""
    lines = [
        "| # | Candidate | Score | Prior | Graph | Trials | Literature | Top paper for this intent |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for cand in candidates:
        s = cand.score
        top = "—"
        if cand.literature_refs:
            ref = cand.literature_refs[0]
            title = (ref.title or "(untitled)").replace("|", "/")
            if len(title) > 90:
                title = title[:87].rstrip() + "..."
            top = f"[{ref.source}:{ref.source_id}] {title} ({ref.year or '?'})"
        lines.append(
            f"| {cand.rank} | {cand.name} | {s.total} | {s.prior_stage} | {s.graph} "
            f"| {s.trials} | {s.literature} | {top} |"
        )
    lines.append("")
    rationales = [c for c in candidates if c.llm_rationale]
    if rationales:
        lines.append("**LLM rationale (advisory):**")
        lines.extend(f"- **#{c.rank} {c.name}:** {c.llm_rationale}" for c in rationales)
        lines.append("")
    return lines


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
