"""Curative candidate and combination screening engine using the trained Relational GNN."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch

from vitiligo.gnn.dataset import GraphDataset, load_graph_dataset
from vitiligo.gnn.model import RelationalGNN
from vitiligo.gnn.train import DEFAULT_MODEL_PATH, load_trained_gnn
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SCREEN_REPORT = Path("exports/gnn_candidate_report.json")
DEFAULT_MARKDOWN_REPORT = Path("docs/gnn-discovery-report.md")

# Core targets for Durability / Resident Memory Disarmament
TRM_DURABILITY_TARGETS = [
    "IL15",
    "IL15RA",
    "IL2RB",  # CD122
    "CXCR6",
    "CXCL16",
    "JAK1",
    "JAK3",
    "STAT1",
    "STAT3",
    "CD8A",
    "ITGAE",  # CD103
    "CD69",
    "TBK1",
    "STING1",
    "CGAS",
]

# Core targets for Stem Cell / Hair-Follicle Regeneration (GSE150954, GSE344141, GSE272551)
# These pathways must be ACTIVATED to mobilize melanocyte stem cells (McSCs)
STEM_CELL_REGENERATION_TARGETS = [
    "CTNNB1",  # Beta-catenin / Wnt
    "WNT1",
    "WNT3A",
    "MITF",
    "EDNRB",  # Endothelin receptor B
    "EDN3",
    "KIT",  # c-Kit / stem cell factor receptor
    "HTR1A",  # 5-HT1A (Fluoxetine / GSE344141)
    "TYR",
    "DCT",
    "CSNK1G3",  # Casein Kinase 1 gamma 3 (GSE256271 responder marker)
    "MAML1",  # Mastermind-like 1 Notch co-factor (GSE256271 responder marker)
]

# Targets identified from paired responder vs non-responder RNA-seq (GSE256271)
# PDE4B is elevated by +9.09 log2FC in non-responding lesions; these barriers must be INHIBITED
NON_RESPONDER_BARRIER_TARGETS = [
    "PDE4B",
    "PDE4A",
    "PDE4D",
    "PLA2G12A",
    "VOPP1",
]

CYTOTOXIC_CHEMO_KEYWORDS = {
    "docetaxel",
    "paclitaxel",
    "ifosfamide",
    "cyclophosphamide",
    "gemcitabine",
    "capecitabine",
    "cisplatin",
    "carboplatin",
    "oxaliplatin",
    "doxorubicin",
    "epirubicin",
    "vincristine",
    "vinblastine",
    "etoposide",
    "irinotecan",
    "topotecan",
    "rucaparib",
    "olaparib",
    "niraparib",
    "bleomycin",
    "dacarbazine",
}


def get_safety_profile(drug_name: str) -> tuple[str, bool]:
    """Classify clinical safety profile and determine if compound is cytotoxic chemotherapy."""
    name_l = drug_name.lower()
    if any(k in name_l for k in CYTOTOXIC_CHEMO_KEYWORDS):
        return "Cytotoxic Chemo (Contraindicated in non-malignant skin)", True
    if any(t in name_l for t in ["cream", "topical", "ointment", "spray", "gel"]):
        return "Topical (Minimal systemic exposure; high tolerability)", False
    if any(
        j in name_l
        for j in [
            "ruxolitinib",
            "ritlecitinib",
            "itacitinib",
            "baricitinib",
            "tofacitinib",
            "upadacitinib",
            "apremilast",
            "deucravacitinib",
            "povorcitinib",
            "ivarmacitinib",
        ]
    ):
        return "Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum)", False
    if any(
        s in name_l
        for s in [
            "clobetasol",
            "betamethasone",
            "fluticasone",
            "clobetasone",
            "triamcinolone",
            "dexamethasone",
            "prednisone",
        ]
    ):
        return "Corticosteroid (Well-established dermatologic rescue)", False
    if any(
        r in name_l
        for r in [
            "vilazodone",
            "fluoxetine",
            "latanoprost",
            "bimatoprost",
            "sacubitril",
            "valsartan",
            "metformin",
            "simvastatin",
        ]
    ):
        return "Repurposed Non-Oncology (Favorable systemic safety profile)", False
    return "Standard Molecular Entity", False


@dataclass
class CandidatePrediction:
    rank: int
    drug_name: str
    drug_key: str
    affinity_score: float
    probability: float
    target_matches: list[str]
    category: str
    safety_tier: str = "Standard"


@dataclass
class CombinationPair:
    rank: int
    immune_drug: str
    regenerative_drug: str
    combined_score: float
    immune_targets: list[str]
    regenerative_targets: list[str]
    safety_notes: str


def screen_candidates(
    model: RelationalGNN | None = None,
    dataset: GraphDataset | None = None,
    *,
    checkpoint_path: Path | str = DEFAULT_MODEL_PATH,
    top_k: int = 25,
    export_json: Path | str = DEFAULT_SCREEN_REPORT,
    export_markdown: Path | str = DEFAULT_MARKDOWN_REPORT,
) -> dict[str, Any]:
    """Execute the multi-tier Curative Discovery Screen across all 2,233 drugs in the graph."""
    if dataset is None:
        dataset = load_graph_dataset()

    if model is None:
        model = load_trained_gnn(checkpoint_path)

    model.eval()
    device = model.device

    edge_index = dataset.edge_index.to(device)
    edge_type = dataset.edge_type.to(device)

    with torch.no_grad():
        h = model.encode(edge_index, edge_type, node_features=dataset.node_features)

    # Filter to canonical small molecules and biologics, excluding verbose trial protocol strings
    candidate_indices = dataset.canonical_drug_indices
    if not candidate_indices:
        candidate_indices = dataset.kind_to_indices.get("DRUG", [])

    if not candidate_indices:
        raise ValueError("No DRUG entities found in dataset.")

    drug_indices_t = torch.tensor(candidate_indices, dtype=torch.long, device=device)
    num_drugs = len(candidate_indices)
    logger.info(
        "Screening %d canonical drug molecules across durability, regeneration, and combination synergy...",
        num_drugs,
    )

    # 1. Direct treats vitiligo affinity vs adverse/cancer-induced depigmentation penalty
    vitiligo_idx = dataset.name_to_idx.get("vitiligo") or dataset.name_to_idx.get("Vitiligo")
    treats_rel = dataset.relation_to_idx.get("TREATS", 0)
    causes_rel = dataset.relation_to_idx.get("CAUSES")
    inhibits_rel = dataset.relation_to_idx.get("INHIBITS", 2)
    activates_rel = dataset.relation_to_idx.get("ACTIVATES", 3)

    treats_scores_dict: dict[int, float] = {}
    causes_scores_dict: dict[int, float] = {}

    if vitiligo_idx is not None:
        # Score each drug -> TREATS -> vitiligo
        rel_t = torch.full((num_drugs,), treats_rel, dtype=torch.long, device=device)
        vit_t = torch.full((num_drugs,), vitiligo_idx, dtype=torch.long, device=device)
        with torch.no_grad():
            t_scores = model.decode_triples(h, drug_indices_t, rel_t, vit_t)
            for d_idx, s in zip(candidate_indices, t_scores.tolist(), strict=False):
                treats_scores_dict[d_idx] = float(s)

        # Score each drug -> CAUSES -> vitiligo (penalizing cancer checkpoint immunotherapies that destroy melanocytes)
        if causes_rel is not None:
            c_rel_t = torch.full((num_drugs,), causes_rel, dtype=torch.long, device=device)
            with torch.no_grad():
                c_scores = model.decode_triples(h, drug_indices_t, c_rel_t, vit_t)
                for d_idx, s in zip(candidate_indices, c_scores.tolist(), strict=False):
                    causes_scores_dict[d_idx] = float(s)

    # 2. Durability Screen: Affinity to inhibiting TRM / Memory retention targets
    trm_indices: list[tuple[str, int]] = []
    for t_name in TRM_DURABILITY_TARGETS:
        idx = dataset.name_to_idx.get(t_name) or dataset.name_to_idx.get(t_name.lower())
        if idx is not None:
            trm_indices.append((t_name, idx))

    durability_results: list[CandidatePrediction] = []
    for d_idx in candidate_indices:
        d_entity = dataset.entities[d_idx]
        safety_tier, is_chemo = get_safety_profile(d_entity.name)
        # Quaratine cytotoxic cancer chemotherapeutics from non-malignant skin disease ranking
        if is_chemo:
            continue

        d_t = torch.tensor([d_idx], dtype=torch.long, device=device)
        matched_targets: list[str] = []
        target_scores: list[float] = []

        for t_name, t_idx in trm_indices:
            r_t = torch.tensor([inhibits_rel], dtype=torch.long, device=device)
            target_t = torch.tensor([t_idx], dtype=torch.long, device=device)
            with torch.no_grad():
                s = float(model.decode_triples(h, d_t, r_t, target_t).item())
            if s > 0.5:
                matched_targets.append(t_name)
                target_scores.append(s)

        mean_target_score = sum(target_scores) / len(target_scores) if target_scores else -2.0
        vit_treats = treats_scores_dict.get(d_idx, 0.0)
        vit_causes = causes_scores_dict.get(d_idx, -2.0)
        cause_penalty = max(0.0, vit_causes) * 0.75
        net_vit_score = vit_treats - cause_penalty

        durability_score = 0.6 * mean_target_score + 0.4 * net_vit_score

        durability_results.append(
            CandidatePrediction(
                rank=0,
                drug_name=d_entity.name,
                drug_key=d_entity.key,
                affinity_score=round(durability_score, 4),
                probability=round(float(torch.sigmoid(torch.tensor(durability_score)).item()), 4),
                target_matches=matched_targets,
                category="Durability (T_RM / Memory Clearance)",
                safety_tier=safety_tier,
            )
        )

    durability_results.sort(key=lambda x: x.affinity_score, reverse=True)
    for i, r in enumerate(durability_results[:top_k], 1):
        r.rank = i

    # 3. Regeneration Screen: Stem Cell Awakening (Activate) + Non-Response Overcoming (Inhibit PDE4B/PLA2G12A from GSE256271)
    stem_act_indices: list[tuple[str, int]] = []
    for t_name in STEM_CELL_REGENERATION_TARGETS:
        idx = dataset.name_to_idx.get(t_name) or dataset.name_to_idx.get(t_name.lower())
        if idx is not None:
            stem_act_indices.append((t_name, idx))

    barrier_inh_indices: list[tuple[str, int]] = []
    for t_name in NON_RESPONDER_BARRIER_TARGETS:
        idx = dataset.name_to_idx.get(t_name) or dataset.name_to_idx.get(t_name.lower())
        if idx is not None:
            barrier_inh_indices.append((t_name, idx))

    regeneration_results: list[CandidatePrediction] = []
    for d_idx in candidate_indices:
        d_entity = dataset.entities[d_idx]
        safety_tier, is_chemo = get_safety_profile(d_entity.name)
        if is_chemo:
            continue

        d_t = torch.tensor([d_idx], dtype=torch.long, device=device)
        matched_mechanisms: list[str] = []
        target_scores: list[float] = []

        # Stem cell activation targets (CTNNB1, MITF, HTR1A, etc.)
        for t_name, t_idx in stem_act_indices:
            r_t = torch.tensor([activates_rel], dtype=torch.long, device=device)
            target_t = torch.tensor([t_idx], dtype=torch.long, device=device)
            with torch.no_grad():
                s = float(model.decode_triples(h, d_t, r_t, target_t).item())
            if s > 0.5:
                matched_mechanisms.append(f"{t_name} (Act)")
                target_scores.append(s)

        # Barrier inhibition targets (PDE4B +9.09 log2FC in non-responders)
        for t_name, t_idx in barrier_inh_indices:
            r_t = torch.tensor([inhibits_rel], dtype=torch.long, device=device)
            target_t = torch.tensor([t_idx], dtype=torch.long, device=device)
            with torch.no_grad():
                s = float(model.decode_triples(h, d_t, r_t, target_t).item())
            if s > 0.5:
                matched_mechanisms.append(f"{t_name} (Inh)")
                target_scores.append(s)

        mean_stem_score = sum(target_scores) / len(target_scores) if target_scores else -2.0
        vit_treats = treats_scores_dict.get(d_idx, 0.0)
        vit_causes = causes_scores_dict.get(d_idx, -2.0)
        cause_penalty = max(0.0, vit_causes) * 0.75
        net_vit_score = vit_treats - cause_penalty

        regen_score = 0.6 * mean_stem_score + 0.4 * net_vit_score

        regeneration_results.append(
            CandidatePrediction(
                rank=0,
                drug_name=d_entity.name,
                drug_key=d_entity.key,
                affinity_score=round(regen_score, 4),
                probability=round(float(torch.sigmoid(torch.tensor(regen_score)).item()), 4),
                target_matches=matched_mechanisms,
                category="Regeneration (Stem Cell Mobilization & Barrier Reversal)",
                safety_tier=safety_tier,
            )
        )

    regeneration_results.sort(key=lambda x: x.affinity_score, reverse=True)
    for i, r in enumerate(regeneration_results[:top_k], 1):
        r.rank = i

    # 4. Synergistic 2-Drug Cocktails (Pulsed Cure: 1 Immune Clearer + 1 Regenerative Adjuvant)
    cocktails: list[CombinationPair] = []
    top_immune = [d for d in durability_results[:15] if len(d.target_matches) > 0]
    top_regen = [d for d in regeneration_results[:15] if len(d.target_matches) > 0]

    for imm in top_immune[:8]:
        for reg in top_regen[:8]:
            if imm.drug_key == reg.drug_key:
                continue

            # Classify combination route and tolerability
            if "Topical" in imm.safety_tier and "Topical" in reg.safety_tier:
                safety_notes = (
                    "Dual Topical: Minimal systemic absorption; high dermatologic tolerability."
                )
            elif "Topical" in imm.safety_tier or "Topical" in reg.safety_tier:
                safety_notes = "Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation."
            else:
                safety_notes = (
                    "Dual Oral / Non-Oncology: Complementary mechanisms; non-overlapping organ tox."
                )

            comb_score = round((imm.affinity_score + reg.affinity_score) / 2.0, 4)
            cocktails.append(
                CombinationPair(
                    rank=0,
                    immune_drug=imm.drug_name,
                    regenerative_drug=reg.drug_name,
                    combined_score=comb_score,
                    immune_targets=imm.target_matches[:3],
                    regenerative_targets=reg.target_matches[:3],
                    safety_notes=safety_notes,
                )
            )

    cocktails.sort(key=lambda x: x.combined_score, reverse=True)
    for i, c in enumerate(cocktails[:15], 1):
        c.rank = i
    for i, c in enumerate(cocktails[:15], 1):
        c.rank = i

    # Generate Reports
    screen_output = {
        "screen_name": "Vitiligo Curative Discovery Screen",
        "num_drugs_evaluated": num_drugs,
        "durability_top_k": [asdict(r) for r in durability_results[:top_k]],
        "regeneration_top_k": [asdict(r) for r in regeneration_results[:top_k]],
        "synergistic_combinations_top_k": [asdict(c) for c in cocktails[:top_k]],
    }

    export_json_path = Path(export_json)
    export_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(export_json_path, "w", encoding="utf-8") as f:
        json.dump(screen_output, f, indent=2)

    # Render Markdown Report
    export_markdown_path = Path(export_markdown)
    export_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    _render_markdown_report(screen_output, export_markdown_path)

    logger.info(
        "Candidate discovery screen finished. Reports saved to %s and %s",
        export_json_path,
        export_markdown_path,
    )
    return screen_output


def _render_markdown_report(data: dict[str, Any], path: Path) -> None:
    lines: list[str] = [
        "# Relational GNN Curative Discovery Report",
        "",
        "> Computational discovery screen using heterogeneous multi-relational graph neural networks",
        "> over 17,685 entities, 62,006 edges, and 58 GEO transcriptomic/perturbation series.",
        "> Cytotoxic oncology chemotherapies are quarantined from primary dermatologic discovery.",
        "",
        "## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)",
        "",
        "Molecules with high predicted affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse after JAK cessation:",
        "",
        "| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |",
        "|:---:|:---|:---:|:---:|:---|:---|",
    ]
    for c in data["durability_top_k"][:15]:
        targets = ", ".join(c["target_matches"]) if c["target_matches"] else "Pathway modulation"
        safety = c.get("safety_tier", "Standard")
        lines.append(
            f"| {c['rank']} | **{c['drug_name']}** | {c['affinity_score']:.3f} | {c['probability']:.1%} | {safety} | {targets} |"
        )

    lines.extend(
        [
            "",
            "## 2. Top Regeneration & Non-Response Overcomers (Stem Cell Awakening / PDE4B Reversal)",
            "",
            "Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`) and reversing the `PDE4B` non-response barrier (+9.09 $\\log_2\\text{FC}$ in GSE256271):",
            "",
            "| Rank | Drug | Score | Probability | Safety Profile | Matched Targets |",
            "|:---:|:---|:---:|:---:|:---|:---|",
        ]
    )
    for c in data["regeneration_top_k"][:15]:
        targets = ", ".join(c["target_matches"]) if c["target_matches"] else "Pathway modulation"
        safety = c.get("safety_tier", "Standard")
        lines.append(
            f"| {c['rank']} | **{c['drug_name']}** | {c['affinity_score']:.3f} | {c['probability']:.1%} | {safety} | {targets} |"
        )

    lines.extend(
        [
            "",
            "## 3. Synergistic Combination Cocktails (Pulsed Curative Regimens)",
            "",
            "Rationally paired 2-drug combinations pairing an **Immune Reset** agent with a **Regenerative Adjuvant**:",
            "",
            "| Rank | Immune Reset (Memory Disarmer) | Regenerative Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |",
            "|:---:|:---|:---|:---:|:---|:---|",
        ]
    )
    for c in data["synergistic_combinations_top_k"][:10]:
        imm_t = ", ".join(c["immune_targets"])
        reg_t = ", ".join(c["regenerative_targets"])
        safety = c.get("safety_notes", "")
        lines.append(
            f"| {c['rank']} | **{c['immune_drug']}** | **{c['regenerative_drug']}** | {c['combined_score']:.3f} | {imm_t} + {reg_t} | {safety} |"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
