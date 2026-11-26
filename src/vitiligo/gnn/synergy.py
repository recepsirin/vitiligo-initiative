"""Pairwise in-silico drug combination hypothesis screening across vitiligo axes.

Scores candidate pairs from Stage-2 single-agent predictions using two explicit
graph-derived components (no experimental dose-response or Bliss/Chou-Talalay claims):
1. Target Space Orthogonality: Jaccard distance (1 - Jaccard similarity) between matched target sets.
2. Pathway Complementarity: Cross-axis pairing of immune/TRM scores with regeneration or PDE4B barrier scores.
3. Composite Pair Score: Weighted combination of complementarity, orthogonality, and their product.
4. Dermatologic Route & Safety Heuristic: Topical vs. systemic pairing summary.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo.gnn.dataset import GraphDataset
from vitiligo.gnn.model import RelationalGNN
from vitiligo.gnn.rerank import (
    CORE_BARRIER_GENES,
    CORE_REGEN_GENES,
    CORE_TRM_GENES,
    DEFAULT_RERANK_REPORT_JSON,
)
from vitiligo.gnn.screen import (
    canonicalize_drug_name,
    get_mechanism_class,
)
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SYNERGY_REPORT_JSON = Path("exports/gnn_pairwise_synergy_matrix.json")
DEFAULT_SYNERGY_REPORT_MD = Path("exports/pairwise-synergy-matrix.md")

_TRM_GENE_SET = {g.upper() for g in CORE_TRM_GENES}
_REGEN_GENE_SET = {g.upper() for g in CORE_REGEN_GENES}
_BARRIER_GENE_SET = {g.upper() for g in CORE_BARRIER_GENES}


@dataclass
class SynergyPairResult:
    rank: int
    drug_a: str
    drug_b: str
    drug_a_pillar: str
    drug_b_pillar: str
    synergy_score: float
    pathway_complementarity: float
    target_orthogonality: float
    route_compatibility: str
    safety_tier: str
    drug_a_targets: list[str]
    drug_b_targets: list[str]
    mechanistic_rationale: str


def compute_tanimoto(fp_a: np.ndarray, fp_b: np.ndarray) -> float:
    """Tanimoto similarity between binary Morgan fingerprint vectors."""
    a = np.asarray(fp_a, dtype=bool)
    b = np.asarray(fp_b, dtype=bool)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 0.0
    return float(inter / union)


def compute_target_orthogonality(targets_a: list[str], targets_b: list[str]) -> float:
    """Jaccard distance (1 - Jaccard similarity) between target sets."""
    set_a = {t.split()[0].upper() for t in targets_a}
    set_b = {t.split()[0].upper() for t in targets_b}
    if not set_a and not set_b:
        return 1.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 1.0
    return float(1.0 - (inter / union))


def _targets_for_axis(targets: list[str], gene_set: set[str]) -> tuple[list[str], list[str]]:
    """Split matched targets belonging to an axis into KG-verified (*) and model-predicted genes."""
    verified: list[str] = []
    predicted: list[str] = []
    for raw in targets:
        gene = raw.split()[0].upper()
        if gene not in gene_set:
            continue
        if "*" in raw:
            verified.append(gene)
        else:
            predicted.append(gene)
    return verified, predicted


def _has_pillar(pillar_text: str, tokens: tuple[str, ...]) -> bool:
    low = pillar_text.lower()
    return any(tok in low for tok in tokens)


def _format_axis_evidence(verified: list[str], predicted: list[str]) -> str:
    if verified:
        shown = ", ".join(verified[:4])
        return f"KG: {shown}"
    if predicted:
        shown = ", ".join(predicted[:3])
        return f"model-predicted: {shown}"
    return "model-predicted"


def _describe_drug_axes(pillar: str, targets: list[str]) -> str:
    """Summarize one drug's assigned axes with KG-verified vs. model-predicted target support."""
    axes: list[str] = []
    for label, tokens, gene_set in (
        ("Immune/TRM", ("pillar 1", "trm", "immune"), _TRM_GENE_SET),
        ("Regeneration", ("pillar 2", "stem-cell", "regen"), _REGEN_GENE_SET),
        ("PDE4B barrier", ("pillar 3", "pde4", "barrier"), _BARRIER_GENE_SET),
    ):
        if not _has_pillar(pillar, tokens):
            continue
        ver, pred = _targets_for_axis(targets, gene_set)
        axes.append(f"{label} ({_format_axis_evidence(ver, pred)})")
    return ", ".join(axes) if axes else "multi-target score"


def _build_pair_rationale(
    *,
    name_a: str,
    pillar_a: str,
    targets_a: list[str],
    name_b: str,
    pillar_b: str,
    targets_b: list[str],
) -> str:
    """Build a transparent per-drug rationale distinguishing KG-verified vs. predicted targets."""
    desc_a = _describe_drug_axes(pillar_a, targets_a)
    desc_b = _describe_drug_axes(pillar_b, targets_b)
    return f"{name_a}: {desc_a}; {name_b}: {desc_b}"


def screen_pairwise_synergy(
    dataset: GraphDataset | None = None,
    gnn_model: RelationalGNN | None = None,
    top_candidates_path: Path = DEFAULT_RERANK_REPORT_JSON,
    top_n_candidates: int = 30,
    top_k_pairs: int = 25,
    out_json: Path = DEFAULT_SYNERGY_REPORT_JSON,
    out_md: Path = DEFAULT_SYNERGY_REPORT_MD,
) -> list[SynergyPairResult]:
    """Screen pairwise in-silico combination hypotheses across top Stage-2 candidates."""
    logger.info("Starting pairwise in-silico combination screening...")

    if not top_candidates_path.is_file():
        raise FileNotFoundError(f"Top candidates file not found at {top_candidates_path}")

    with open(top_candidates_path, encoding="utf-8") as f:
        cand_data = json.load(f)

    candidates = cand_data.get("candidates", [])[:top_n_candidates]
    if not candidates:
        raise ValueError("No candidates found in candidates JSON file.")

    pairs: list[tuple[float, dict[str, Any]]] = []

    for i in range(len(candidates)):
        cand_a = candidates[i]
        name_a = cand_a.get("drug_name", "")
        canon_a = canonicalize_drug_name(name_a)
        mech_a = get_mechanism_class(name_a)
        trm_a = float(cand_a.get("trm_disarmament_score", 0.0))
        sc_a = float(cand_a.get("stem_cell_regen_score", 0.0))
        bar_a = float(cand_a.get("barrier_suppression_score", 0.0))
        targets_a = cand_a.get("matched_targets", [])
        pillar_a = cand_a.get("curative_triad_alignment", "Pillar 1")

        for j in range(i + 1, len(candidates)):
            cand_b = candidates[j]
            name_b = cand_b.get("drug_name", "")
            canon_b = canonicalize_drug_name(name_b)
            if canon_a == canon_b:
                continue

            mech_b = get_mechanism_class(name_b)
            trm_b = float(cand_b.get("trm_disarmament_score", 0.0))
            sc_b = float(cand_b.get("stem_cell_regen_score", 0.0))
            bar_b = float(cand_b.get("barrier_suppression_score", 0.0))
            targets_b = cand_b.get("matched_targets", [])
            pillar_b = cand_b.get("curative_triad_alignment", "Pillar 2/3")

            # Exclude same-class redundancy (e.g. 2 JAK inhibitors or 2 steroids)
            if mech_a == mech_b and mech_a in ("JAK_STAT_INHIBITOR", "CORTICOSTEROID"):
                continue

            # 1. Target Orthogonality (Jaccard distance: 1.0 = no shared matched targets)
            ortho = compute_target_orthogonality(targets_a, targets_b)

            # 2. Pathway Complementarity:
            # Cross-axis pairing of immune/TRM score with regeneration or barrier score
            comp_ab = (trm_a * max(sc_b, bar_b)) + (trm_b * max(sc_a, bar_a))
            comp_score = float(np.tanh(comp_ab / 3.0))

            # 3. Composite In-Silico Pair Score (heuristic graph ranking; not a measured interaction)
            pair_score = float(2.0 * comp_score + 1.5 * ortho + 0.7 * comp_score * ortho)

            # Route & Safety Compatibility
            tier_a = cand_a.get("safety_tier", "")
            tier_b = cand_b.get("safety_tier", "")
            if tier_a.startswith("Topical") and tier_b.startswith("Topical"):
                route = "Dual Topical (Minimal systemic load)"
            elif tier_a.startswith("Topical") or tier_b.startswith("Topical"):
                route = "Systemic + Topical Adjuvant (Systemic control + localized targeting)"
            else:
                route = "Systemic / Oral Combination (Clinical safety monitoring required)"

            rationale = _build_pair_rationale(
                name_a=name_a,
                pillar_a=pillar_a,
                targets_a=targets_a,
                name_b=name_b,
                pillar_b=pillar_b,
                targets_b=targets_b,
            )

            pairs.append(
                (
                    pair_score,
                    {
                        "drug_a": name_a,
                        "drug_b": name_b,
                        "drug_a_pillar": pillar_a,
                        "drug_b_pillar": pillar_b,
                        "synergy_score": round(pair_score, 4),
                        "pathway_complementarity": round(comp_score, 4),
                        "target_orthogonality": round(ortho, 3),
                        "route_compatibility": route,
                        "safety_tier": f"{tier_a} + {tier_b}",
                        "drug_a_targets": targets_a[:4],
                        "drug_b_targets": targets_b[:4],
                        "mechanistic_rationale": rationale,
                    },
                )
            )

    pairs.sort(key=lambda x: x[0], reverse=True)

    # Diversity cap: no drug appears in more than 3 listed pairs
    results: list[SynergyPairResult] = []
    drug_counts: dict[str, int] = {}

    for _, p in pairs:
        c_a = canonicalize_drug_name(p["drug_a"])
        c_b = canonicalize_drug_name(p["drug_b"])
        if drug_counts.get(c_a, 0) >= 3 or drug_counts.get(c_b, 0) >= 3:
            continue
        drug_counts[c_a] = drug_counts.get(c_a, 0) + 1
        drug_counts[c_b] = drug_counts.get(c_b, 0) + 1

        res = SynergyPairResult(
            rank=len(results) + 1,
            drug_a=p["drug_a"],
            drug_b=p["drug_b"],
            drug_a_pillar=p["drug_a_pillar"],
            drug_b_pillar=p["drug_b_pillar"],
            synergy_score=p["synergy_score"],
            pathway_complementarity=p["pathway_complementarity"],
            target_orthogonality=p["target_orthogonality"],
            route_compatibility=p["route_compatibility"],
            safety_tier=p["safety_tier"],
            drug_a_targets=p["drug_a_targets"],
            drug_b_targets=p["drug_b_targets"],
            mechanistic_rationale=p["mechanistic_rationale"],
        )
        results.append(res)
        if len(results) >= top_k_pairs:
            break

    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": "In-Silico Pairwise Combination Hypothesis Screening",
        "scoring_note": (
            "Heuristic graph-based pair ranking combining pathway complementarity "
            "(tanh of cross-axis single-agent scores) and target orthogonality "
            "(Jaccard distance of matched targets). Not derived from experimental "
            "dose-response curves or empirical synergy assays."
        ),
        "evaluated_single_agents": len(candidates),
        "total_screened_pairs": len(pairs),
        "top_synergistic_pairs": [asdict(r) for r in results],
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logger.info("Saved pairwise hypothesis JSON to %s", out_json)

    _render_synergy_markdown(results, out_md)
    logger.info("Saved pairwise hypothesis report to %s", out_md)

    return results


def _render_synergy_markdown(results: list[SynergyPairResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pairwise In-Silico Combination Hypotheses (3-Pillar Framework)",
        "",
        "**The Vitiligo Initiative | Computational Pharmacology & Multi-Target Hypotheses**  ",
        "**Model Basis:** Heterogeneous `RGAT-4H + ComplEx` GNN + Stage-2 Cross-Encoder reranker.  ",
        "",
        "---",
        "",
        "## Summary",
        "",
        "Pairs of the reranker's top single agents, ranked by a composite in-silico pair score "
        "combining pathway complementarity (cross-axis immune vs. regeneration/barrier scores) "
        "and target orthogonality (Jaccard distance across matched targets). These are "
        "graph-derived hypotheses to test in preclinical assays, not measured drug interactions "
        "or dose-response synergy indices.",
        "",
        "| Rank | Combination Hypothesis | Pair Score | Complementarity | Orthogonality | Route & Safety | Mechanistic Rationale |",
        "|---|---|---:|---:|---:|---|---|",
    ]

    for r in results:
        pair_str = f"**{r.drug_a.capitalize()}** + **{r.drug_b.capitalize()}**"
        lines.append(
            f"| {r.rank} | {pair_str} | {r.synergy_score:.2f} | "
            f"{r.pathway_complementarity:.2f} | {r.target_orthogonality:.2f} | "
            f"{r.route_compatibility.split('(')[0].strip()} | {r.mechanistic_rationale} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Detailed Top Pair Profiles",
            "",
        ]
    )

    for r in results[:5]:
        lines.extend(
            [
                f"### #{r.rank}. {r.drug_a.capitalize()} + {r.drug_b.capitalize()}",
                f"- **In-Silico Pair Score:** `{r.synergy_score:.3f}` · **Pathway Complementarity:** `{r.pathway_complementarity:.3f}` · **Target Orthogonality:** `{r.target_orthogonality:.2f}` (Jaccard distance)",
                f"- **Route Compatibility:** {r.route_compatibility}",
                f"- **{r.drug_a.capitalize()} Targets:** {', '.join(r.drug_a_targets) or 'None matched'}",
                f"- **{r.drug_b.capitalize()} Targets:** {', '.join(r.drug_b_targets) or 'None matched'}",
                f"- **Mechanistic Rationale:** {r.mechanistic_rationale}",
                "",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
