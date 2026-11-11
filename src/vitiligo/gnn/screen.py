"""Curative candidate and combination screening engine using the trained Relational GNN."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from vitiligo.gnn.chemicals import clean_drug_name
from vitiligo.gnn.dataset import GraphDataset, load_graph_dataset
from vitiligo.gnn.model import RelationalGNN
from vitiligo.gnn.train import DEFAULT_MODEL_PATH, load_trained_gnn
from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SCREEN_REPORT = Path("exports/gnn_candidate_report.json")
DEFAULT_MARKDOWN_REPORT = Path("exports/gnn-discovery-report.md")

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
    "pemetrexed",
    "chlorambucil",
    "melphalan",
    "busulfan",
    "temozolomide",
    "carmustine",
    "lomustine",
    "daunorubicin",
    "idarubicin",
    "mitoxantrone",
    "vinorelbine",
}

BRAND_TO_GENERIC: dict[str, str] = {
    "litfulo": "ritlecitinib",
    "opzelura": "ruxolitinib",
    "olumiant": "baricitinib",
    "xeljanz": "tofacitinib",
    "rinvoq": "upadacitinib",
    "otezla": "apremilast",
    "eucrisa": "crisaborole",
    "protopic": "tacrolimus",
    "elidel": "pimecrolimus",
    "stelara": "ustekinumab",
    "cosentyx": "secukinumab",
    "humira": "adalimumab",
    "enbrel": "etanercept",
}

NON_CURATIVE_COMORBIDITIES: set[str] = {
    "haloperidol",
    "ribavirin",
    "fluconazole",
    "voriconazole",
    "itraconazole",
    "ketoconazole",
    "terbinafine",
    "bicalutamide",
    "insulin glargine",
    "tranexamic acid",
    "omalizumab",
    "amifostine",
    "lidocaine",
    "prilocaine",
    "bupivacaine",
    "furosemide",
    "warfarin",
    "heparin",
    "digoxin",
    "amiodarone",
    "gentamicin",
    "vancomycin",
    "phenytoin",
    "propofol",
    "halothane",
    "chloroquine",
    "hydroxychloroquine",
    "methimazole",
    "propylthiouracil",
    "levothyroxine",
}

JAK_STAT_KEYWORDS = {
    "ruxolitinib",
    "ritlecitinib",
    "tofacitinib",
    "baricitinib",
    "upadacitinib",
    "cerdulatinib",
    "ifidancitinib",
    "brepocitinib",
    "deucravacitinib",
    "peficitinib",
    "delgocitinib",
    "gusacitinib",
    "ivarmacitinib",
    "povorcitinib",
    "itacitinib",
    "momelotinib",
    "fedratinib",
    "pacritinib",
    "filgotinib",
    "abrocitinib",
}

REGENERATIVE_AGONIST_KEYWORDS = {
    "afamelanotide",
    "latanoprost",
    "bimatoprost",
    "travoprost",
    "fluoxetine",
    "vilazodone",
    "minoxidil",
    "tretinoin",
    "calcipotriol",
    "cholecalciferol",
    "ergocalciferol",
    "baicalein",
    "quercetin",
    "resveratrol",
    "curcumin",
    "khellin",
    "psoralen",
    "methoxsalen",
    "bergapten",
}

PDE4_METABOLIC_KEYWORDS = {
    "apremilast",
    "crisaborole",
    "roflumilast",
    "rolipram",
    "simvastatin",
    "atorvastatin",
    "rosuvastatin",
    "pravastatin",
    "metformin",
    "pioglitazone",
    "rosiglitazone",
}


def canonicalize_drug_name(drug_name: str) -> str:
    """Resolve trade/brand and salt synonyms to canonical generic drug names."""
    base = clean_drug_name(drug_name).lower()
    return BRAND_TO_GENERIC.get(base, base)


def get_mechanism_class(drug_name: str) -> str:
    """Classify compound into orthogonal pharmacological mechanism classes."""
    canon = canonicalize_drug_name(drug_name)
    if any(k in canon for k in JAK_STAT_KEYWORDS):
        return "JAK_STAT_INHIBITOR"
    if any(
        k in canon
        for k in ["tacrolimus", "pimecrolimus", "cyclosporine", "sirolimus", "everolimus"]
    ):
        return "CALCINEURIN_MTOR_IMMUNOMODULATOR"
    if any(k in canon for k in ["apremilast", "crisaborole", "roflumilast", "rolipram"]):
        return "PDE4_CAMP_MODULATOR"
    if any(k in canon for k in REGENERATIVE_AGONIST_KEYWORDS):
        return "MELANOCYTE_REGENERATIVE_AGONIST"
    if any(k in canon for k in PDE4_METABOLIC_KEYWORDS):
        return "METABOLIC_REDOX_MODULATOR"
    if any(
        s in canon
        for s in [
            "clobetasol",
            "betamethasone",
            "fluticasone",
            "clobetasone",
            "triamcinolone",
            "dexamethasone",
            "prednisone",
            "prednisolone",
            "hydrocortisone",
            "mometasone",
            "halobetasol",
            "fluocinonide",
            "fluocinolone",
        ]
    ):
        return "CORTICOSTEROID"
    return "OTHER_IMMUNOMODULATOR"


def get_safety_profile(drug_name: str) -> tuple[str, bool]:
    """Classify clinical safety profile and determine if compound is cytotoxic chemotherapy."""
    name_l = drug_name.lower()
    canon = canonicalize_drug_name(drug_name)
    if any(k in name_l for k in CYTOTOXIC_CHEMO_KEYWORDS):
        return "Cytotoxic Chemo (Contraindicated in non-malignant skin)", True
    if any(t in name_l for t in ["cream", "topical", "ointment", "spray", "gel"]) or any(
        t in canon
        for t in [
            "tacrolimus",
            "pimecrolimus",
            "crisaborole",
            "latanoprost",
            "bimatoprost",
            "travoprost",
            "calcipotriol",
            "tretinoin",
            "minoxidil",
        ]
    ):
        return "Topical (Minimal systemic exposure; high tolerability)", False
    if any(
        j in canon
        for j in (
            JAK_STAT_KEYWORDS | {"apremilast", "roflumilast", "rolipram", "abatacept", "sirolimus"}
        )
    ):
        return "Targeted Kinase/PDE4 (Manageable clinical safety; approved in derm/rheum)", False
    if get_mechanism_class(drug_name) == "CORTICOSTEROID":
        return "Corticosteroid (Acute palliative rescue; high post-cessation relapse)", False
    if any(r in canon for r in (REGENERATIVE_AGONIST_KEYWORDS | PDE4_METABOLIC_KEYWORDS)):
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
    """Execute the multi-tier Curative Discovery Screen across all canonical drugs in the graph."""
    if dataset is None:
        dataset = load_graph_dataset()

    if model is None:
        model = load_trained_gnn(checkpoint_path)

    model.eval()
    device = model.device

    edge_index = dataset.edge_index.to(device)
    edge_type = dataset.edge_type.to(device)
    edge_weight = dataset.edge_weight.to(device) if dataset.edge_weight is not None else None
    node_features = dataset.node_features.to(device) if dataset.node_features is not None else None

    with torch.no_grad():
        h = model.encode(
            edge_index, edge_type, node_features=node_features, edge_weight=edge_weight
        )

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

    # Build lookup of verified direct drug-target edges in the knowledge graph
    verified_edges: set[tuple[int, int, int]] = set()
    src_l = dataset.edge_index[0].tolist()
    dst_l = dataset.edge_index[1].tolist()
    rel_l = dataset.edge_type.tolist()
    for u, v, r in zip(src_l, dst_l, rel_l, strict=False):
        if r in (inhibits_rel, activates_rel):
            verified_edges.add((u, r, v))

    treats_scores_dict: dict[int, float] = {}
    causes_scores_dict: dict[int, float] = {}

    if vitiligo_idx is not None:
        rel_t = torch.full((num_drugs,), treats_rel, dtype=torch.long, device=device)
        vit_t = torch.full((num_drugs,), vitiligo_idx, dtype=torch.long, device=device)
        with torch.no_grad():
            t_scores = model.decode_triples(h, drug_indices_t, rel_t, vit_t)
            for d_idx, s in zip(candidate_indices, t_scores.tolist(), strict=False):
                treats_scores_dict[d_idx] = float(s)

        if causes_rel is not None:
            c_rel_t = torch.full((num_drugs,), causes_rel, dtype=torch.long, device=device)
            with torch.no_grad():
                c_scores = model.decode_triples(h, drug_indices_t, c_rel_t, vit_t)
                for d_idx, s in zip(candidate_indices, c_scores.tolist(), strict=False):
                    causes_scores_dict[d_idx] = float(s)

    # Helper to score all candidate drugs against a target list in one vectorized pass
    def _score_target_matrix(
        target_pairs: list[tuple[str, int]], rel_id: int
    ) -> tuple[np.ndarray, np.ndarray]:
        if not target_pairs:
            return np.zeros((num_drugs, 0), dtype=np.float32), np.zeros((0,), dtype=np.float32)
        mat = np.zeros((num_drugs, len(target_pairs)), dtype=np.float32)
        r_vec = torch.full((num_drugs,), rel_id, dtype=torch.long, device=device)
        with torch.no_grad():
            for j, (_, t_idx) in enumerate(target_pairs):
                t_vec = torch.full((num_drugs,), t_idx, dtype=torch.long, device=device)
                mat[:, j] = model.decode_triples(h, drug_indices_t, r_vec, t_vec).cpu().numpy()
        # Per-target 88th percentile calibration so hub targets do not fire indiscriminately
        p88 = np.percentile(mat, 88, axis=0) if num_drugs > 5 else np.full(len(target_pairs), 0.5)
        return mat, p88

    # 2. Durability Screen: Affinity to inhibiting TRM / Memory retention targets
    trm_indices: list[tuple[str, int]] = []
    for t_name in TRM_DURABILITY_TARGETS:
        idx = dataset.name_to_idx.get(t_name) or dataset.name_to_idx.get(t_name.lower())
        if idx is not None:
            trm_indices.append((t_name, idx))

    trm_mat, trm_p88 = _score_target_matrix(trm_indices, inhibits_rel)

    raw_durability: list[CandidatePrediction] = []
    for row_i, d_idx in enumerate(candidate_indices):
        d_entity = dataset.entities[d_idx]
        canon_name = canonicalize_drug_name(d_entity.name)
        if num_drugs > 10 and canon_name in NON_CURATIVE_COMORBIDITIES:
            continue
        safety_tier, is_chemo = get_safety_profile(d_entity.name)
        if is_chemo:
            continue

        matched_scored: list[tuple[float, str]] = []
        verified_count = 0
        for j, (t_name, t_idx) in enumerate(trm_indices):
            s = float(trm_mat[row_i, j])
            is_ver = (d_idx, inhibits_rel, t_idx) in verified_edges
            if is_ver:
                verified_count += 1
                matched_scored.append((s + 2.0, f"{t_name}*"))
            elif s >= max(float(trm_p88[j]), 0.5):
                matched_scored.append((s, t_name))

        matched_scored.sort(key=lambda x: x[0], reverse=True)
        matched_targets = [label for _, label in matched_scored[:5]]

        top3_vals = (
            sorted(trm_mat[row_i].tolist(), reverse=True)[:3] if len(trm_indices) > 0 else [-1.0]
        )
        mean_target_score = float(np.mean(top3_vals)) + 0.35 * min(verified_count, 3)

        vit_treats = treats_scores_dict.get(d_idx, 0.0)
        vit_causes = causes_scores_dict.get(d_idx, -2.0)
        cause_penalty = max(0.0, vit_causes) * 0.75
        net_vit_score = vit_treats - cause_penalty

        mech_class = get_mechanism_class(d_entity.name)
        specificity_adj = 0.0
        if num_drugs > 10:
            if mech_class == "CORTICOSTEROID":
                specificity_adj = -1.25  # Corticosteroids do not clear skin CD8+ TRM cells
            elif mech_class in ("JAK_STAT_INHIBITOR", "CALCINEURIN_MTOR_IMMUNOMODULATOR"):
                specificity_adj = 0.45

        durability_score = 0.6 * mean_target_score + 0.4 * net_vit_score + specificity_adj

        raw_durability.append(
            CandidatePrediction(
                rank=0,
                drug_name=canon_name
                if d_entity.name.lower() in BRAND_TO_GENERIC
                else d_entity.name,
                drug_key=d_entity.key,
                affinity_score=round(durability_score, 4),
                probability=round(float(torch.sigmoid(torch.tensor(durability_score)).item()), 4),
                target_matches=matched_targets,
                category="Durability (T_RM / Memory Clearance)",
                safety_tier=safety_tier,
            )
        )

    raw_durability.sort(key=lambda x: x.affinity_score, reverse=True)
    durability_results: list[CandidatePrediction] = []
    seen_dur: set[str] = set()
    for item in raw_durability:
        canon = canonicalize_drug_name(item.drug_name)
        if canon in seen_dur and num_drugs > 10:
            continue
        seen_dur.add(canon)
        item.rank = len(durability_results) + 1
        durability_results.append(item)

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

    stem_mat, stem_p88 = _score_target_matrix(stem_act_indices, activates_rel)
    bar_mat, bar_p88 = _score_target_matrix(barrier_inh_indices, inhibits_rel)

    raw_regeneration: list[CandidatePrediction] = []
    for row_i, d_idx in enumerate(candidate_indices):
        d_entity = dataset.entities[d_idx]
        canon_name = canonicalize_drug_name(d_entity.name)
        if num_drugs > 10 and canon_name in NON_CURATIVE_COMORBIDITIES:
            continue
        safety_tier, is_chemo = get_safety_profile(d_entity.name)
        if is_chemo:
            continue

        matched_scored = []
        verified_count = 0

        for j, (t_name, t_idx) in enumerate(stem_act_indices):
            s = float(stem_mat[row_i, j])
            is_ver = (d_idx, activates_rel, t_idx) in verified_edges
            if is_ver:
                verified_count += 1
                matched_scored.append((s + 2.0, f"{t_name} (Act*)"))
            elif s >= max(float(stem_p88[j]), 0.5):
                matched_scored.append((s, f"{t_name} (Act)"))

        for j, (t_name, t_idx) in enumerate(barrier_inh_indices):
            s = float(bar_mat[row_i, j])
            is_ver = (d_idx, inhibits_rel, t_idx) in verified_edges
            if is_ver:
                verified_count += 1
                matched_scored.append((s + 2.0, f"{t_name} (Inh*)"))
            elif s >= max(float(bar_p88[j]), 0.5):
                matched_scored.append((s, f"{t_name} (Inh)"))

        matched_scored.sort(key=lambda x: x[0], reverse=True)
        matched_mechanisms = [label for _, label in matched_scored[:5]]

        combined_vals = (stem_mat[row_i].tolist() if len(stem_act_indices) > 0 else []) + (
            bar_mat[row_i].tolist() if len(barrier_inh_indices) > 0 else []
        )
        top3_vals = sorted(combined_vals, reverse=True)[:3] if combined_vals else [-1.0]
        mean_stem_score = float(np.mean(top3_vals)) + 0.45 * min(verified_count, 3)

        vit_treats = treats_scores_dict.get(d_idx, 0.0)
        vit_causes = causes_scores_dict.get(d_idx, -2.0)
        cause_penalty = max(0.0, vit_causes) * 0.75
        net_vit_score = vit_treats - cause_penalty

        mech_class = get_mechanism_class(d_entity.name)
        specificity_adj = 0.0
        if num_drugs > 10:
            if mech_class in (
                "MELANOCYTE_REGENERATIVE_AGONIST",
                "PDE4_CAMP_MODULATOR",
                "METABOLIC_REDOX_MODULATOR",
            ):
                specificity_adj = 0.95
            elif mech_class in ("JAK_STAT_INHIBITOR", "CORTICOSTEROID"):
                # Pure immune/steroid agents belong in Pillar 1, not primary stem-cell regeneration
                specificity_adj = -1.25

        regen_score = 0.6 * mean_stem_score + 0.4 * net_vit_score + specificity_adj

        raw_regeneration.append(
            CandidatePrediction(
                rank=0,
                drug_name=canon_name
                if d_entity.name.lower() in BRAND_TO_GENERIC
                else d_entity.name,
                drug_key=d_entity.key,
                affinity_score=round(regen_score, 4),
                probability=round(float(torch.sigmoid(torch.tensor(regen_score)).item()), 4),
                target_matches=matched_mechanisms,
                category="Regeneration (Stem Cell Mobilization & Barrier Reversal)",
                safety_tier=safety_tier,
            )
        )

    raw_regeneration.sort(key=lambda x: x.affinity_score, reverse=True)
    regeneration_results: list[CandidatePrediction] = []
    seen_reg: set[str] = set()
    for item in raw_regeneration:
        canon = canonicalize_drug_name(item.drug_name)
        if canon in seen_reg and num_drugs > 10:
            continue
        seen_reg.add(canon)
        item.rank = len(regeneration_results) + 1
        regeneration_results.append(item)

    # 4. Synergistic 2-Drug Cocktails (Mechanistically Orthogonal: 1 Immune Reset + 1 Regenerative/Barrier Adjuvant)
    cocktails: list[CombinationPair] = []
    top_immune = [d for d in durability_results[:15] if len(d.target_matches) > 0]
    top_regen = [d for d in regeneration_results[:15] if len(d.target_matches) > 0]

    candidate_pairs: list[tuple[float, CandidatePrediction, CandidatePrediction, str]] = []
    for imm in top_immune[:10]:
        imm_canon = canonicalize_drug_name(imm.drug_name)
        imm_class = get_mechanism_class(imm.drug_name)
        for reg in top_regen[:10]:
            reg_canon = canonicalize_drug_name(reg.drug_name)
            if imm_canon == reg_canon:
                continue
            reg_class = get_mechanism_class(reg.drug_name)
            # Enforce Mechanistic Orthogonality: never pair two JAK inhibitors or same pharmacological class
            if num_drugs > 10 and (
                imm_class == reg_class or reg_class in ("JAK_STAT_INHIBITOR", "CORTICOSTEROID")
            ):
                continue

            if "Topical" in imm.safety_tier and "Topical" in reg.safety_tier:
                safety_notes = (
                    "Dual Topical: Minimal systemic absorption; high dermatologic tolerability."
                )
            elif "Topical" in imm.safety_tier or "Topical" in reg.safety_tier:
                safety_notes = "Targeted Oral + Topical Adjuvant: Potent systemic reset with targeted local niche activation."
            else:
                safety_notes = "Orthogonal Dual Regimen: Complementary immune + regenerative/PDE4B mechanisms; non-overlapping organ toxicity."

            comb_score = round((imm.affinity_score + reg.affinity_score) / 2.0, 4)
            candidate_pairs.append((comb_score, imm, reg, safety_notes))

    candidate_pairs.sort(key=lambda x: x[0], reverse=True)
    drug_pair_counts: dict[str, int] = {}
    for comb_score, imm, reg, safety_notes in candidate_pairs:
        imm_c = canonicalize_drug_name(imm.drug_name)
        reg_c = canonicalize_drug_name(reg.drug_name)
        if num_drugs > 10 and (
            drug_pair_counts.get(imm_c, 0) >= 2 or drug_pair_counts.get(reg_c, 0) >= 2
        ):
            continue
        drug_pair_counts[imm_c] = drug_pair_counts.get(imm_c, 0) + 1
        drug_pair_counts[reg_c] = drug_pair_counts.get(reg_c, 0) + 1
        cocktails.append(
            CombinationPair(
                rank=len(cocktails) + 1,
                immune_drug=imm.drug_name,
                regenerative_drug=reg.drug_name,
                combined_score=comb_score,
                immune_targets=imm.target_matches[:3],
                regenerative_targets=reg.target_matches[:3],
                safety_notes=safety_notes,
            )
        )
        if len(cocktails) >= top_k:
            break

    # Generate Reports
    screen_output = {
        "screen_name": "Vitiligo Curative Discovery Screen",
        "num_drugs_evaluated": num_drugs,
        "num_entities": dataset.num_nodes,
        "num_edges": dataset.num_edges,
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
    num_ent = data.get("num_entities", 18494)
    num_edg = data.get("num_edges", 92361)
    lines: list[str] = [
        "# Relational GNN Curative Discovery Report",
        "",
        "> Computational discovery screen using heterogeneous multi-relational graph neural networks (`RGAT-4H + ComplEx`)",
        f"> over {num_ent:,} entities, {num_edg:,} edges, and 58 GEO transcriptomic/perturbation series.",
        "> Cytotoxic oncology chemotherapies and non-dermatologic comorbidity confounders are quarantined.",
        "> Verified Knowledge Graph mechanisms (ChEMBL / DrugCentral / Literature) are marked with `*`.",
        "",
        "## 1. Top Durability Candidates (Resident Memory $T_{RM}$ / IL-15 Axis Disarmament)",
        "",
        "Molecules with high predicted and verified affinity to disarm skin CD8+ $T_{RM}$ anchoring and prevent relapse:",
        "",
        "| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |",
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
            "Molecules mobilizing melanocyte stem cells (`CTNNB1`, `HTR1A`, `MITF`, `TYR`) and reversing the `PDE4B` non-response barrier (+9.09 $\\log_2\\text{FC}$ in GSE256271):",
            "",
            "| Rank | Drug | Score | Probability | Safety Profile | Matched Targets (`*` = Verified) |",
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
            "## 3. Synergistic Combination Cocktails (Mechanistically Orthogonal Regimens)",
            "",
            "Rationally paired 2-drug combinations pairing an **Immune Reset ($T_{RM}$ Disarmer)** with a **Mechanistically Orthogonal Regenerative / PDE4B Barrier Adjuvant**:",
            "",
            "| Rank | Immune Reset (Memory Disarmer) | Regenerative / Barrier Adjuvant | Score | Mechanism Synergy | Safety & Delivery Rationale |",
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
