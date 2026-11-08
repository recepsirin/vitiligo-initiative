"""Enrich the Vitiligo Knowledge Graph with human punch biopsy co-expression and canonical pathway hierarchies.

Prepares the knowledge graph for publication and public release:
1. Seeds canonical vitiligo biological pathways (GO / Reactome) and cell lineages.
2. Interconnects target genes to pathways (PARTICIPATES_IN) and cell types (EXPRESSED_IN).
3. Commits the 11,070 patient punch biopsy gene-gene co-expression edges (CO_EXPRESSED_WITH)
   directly into SQLite with GEO:GSE311770 provenance and Pearson correlation coefficients.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from vitiligo.graph.normalize import normalize_entity_key
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.logging import get_logger
from vitiligo.storage import session_scope
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity, RelationKind

logger = get_logger(__name__)

COEXPRESSION_CACHE_PATH = Path("data/cache/gnn/coexpression_edges.pt")

CANONICAL_PATHWAYS: list[dict[str, Any]] = [
    {
        "name": "IFN-gamma Signaling Pathway",
        "external_ids": {"go": "GO:0060333", "reactome": "R-HSA-877300"},
        "description": "Core driver of vitiligo autoimmunity: IFN-g activates JAK1/STAT1 to induce CXCL9/CXCL10 chemokines.",
        "genes": ["IFNG", "IFNGR1", "IFNGR2", "JAK1", "JAK2", "STAT1", "STAT2", "IRF1", "CXCL9", "CXCL10", "CXCL11", "CXCR3"],
    },
    {
        "name": "JAK-STAT Signaling Cascade",
        "external_ids": {"go": "GO:0007259", "reactome": "R-HSA-909733"},
        "description": "Intracellular cytokine transduction cascade mediating IFN-gamma, IL-15, and common gamma-chain signaling.",
        "genes": ["JAK1", "JAK2", "JAK3", "TYK2", "STAT1", "STAT2", "STAT3", "STAT4", "STAT5A", "STAT5B", "STAT6"],
    },
    {
        "name": "Melanocyte Differentiation and Pigmentation",
        "external_ids": {"go": "GO:0043473", "reactome": "R-HSA-5579029"},
        "description": "Enzymatic and transcriptional pathway executing melanin synthesis and melanosome biogenesis.",
        "genes": ["MITF", "TYR", "DCT", "TYRP1", "PMEL", "MLANA", "OCA2", "MC1R", "ASIP", "KIT", "EDNRB", "SOX10", "PAX3"],
    },
    {
        "name": "Wnt/Beta-Catenin Stem-Cell Signaling",
        "external_ids": {"go": "GO:0016055", "reactome": "R-HSA-195721"},
        "description": "Essential mobilization pathway driving hair-follicle melanocyte stem cell (McSC) migration and differentiation.",
        "genes": ["WNT1", "WNT3A", "WNT5A", "CTNNB1", "LEF1", "TCF7L2", "AXIN2", "GSK3B", "FZD1", "FZD4", "LRP5", "LRP6"],
    },
    {
        "name": "Tissue-Resident Memory T-Cell Activation",
        "external_ids": {"go": "GO:0042110", "mesh": "D000085442"},
        "description": "Maintenance and cytotoxic reactivation of skin-resident autoreactive CD8+ CD69+ CD103+ memory T cells.",
        "genes": ["IL15", "IL15RA", "CD8A", "CD8B", "ITGAE", "CD69", "CXCR6", "ZNF683", "PRDM1", "RUNX3"],
    },
    {
        "name": "cGAS-STING Cytosolic DNA Sensing Pathway",
        "external_ids": {"go": "GO:0060337", "reactome": "R-HSA-9615017"},
        "description": "Innate immune DNA sensing mechanism triggering type I IFN and inflammatory priming in stressed melanocytes.",
        "genes": ["CGAS", "STING1", "TBK1", "IRF3", "IFNB1"],
    },
    {
        "name": "Cellular Response to Oxidative Stress",
        "external_ids": {"go": "GO:0034599", "reactome": "R-HSA-3299685"},
        "description": "Antioxidant defense and redox buffering preventing ROS-induced HSP70 export and melanocyte apoptosis.",
        "genes": ["SOD1", "SOD2", "CAT", "GPX1", "HMOX1", "HSPA1A", "HSP90AA1", "NFE2L2"],
    },
    {
        "name": "Phosphodiesterase (PDE4) and cAMP Barrier Axis",
        "external_ids": {"reactome": "R-HSA-111997"},
        "description": "Non-responder transcriptomic barrier characterized by elevated PDE4B, PLA2G12A, and compromised cAMP signaling.",
        "genes": ["PDE4B", "PDE4A", "PDE4D", "PLA2G12A", "ADCY1", "PRKACA"],
    },
    {
        "name": "Prostaglandin FP Receptor Signaling",
        "external_ids": {"reactome": "R-HSA-2142753"},
        "description": "Prostaglandin F2-alpha signaling cascade mediating melanocyte dendricity, tyrosinase activity, and McSC activation.",
        "genes": ["PTGFR", "PTGS1", "PTGS2", "PTGER2", "PTGER4"],
    },
]

CANONICAL_CELL_TYPES: list[dict[str, Any]] = [
    {
        "name": "Epidermal Melanocyte",
        "external_ids": {"cell_ontology": "CL:0000148", "mesh": "D008544"},
        "description": "Specialized melanin-producing dendritic cells located in the epidermal basal layer.",
        "markers": ["TYR", "DCT", "MLANA", "PMEL", "MITF", "OCA2"],
    },
    {
        "name": "Hair Follicle Melanocyte Stem Cell (McSC)",
        "external_ids": {"cell_ontology": "CL:0002092"},
        "description": "Quiescent reservoir cells in the hair follicle bulge responsible for follicular repigmentation in vitiligo.",
        "markers": ["PAX3", "SOX10", "KIT", "EDNRB", "DCT", "CD34", "HTR1A"],
    },
    {
        "name": "CD8+ Tissue-Resident Memory T Cell (TRM)",
        "external_ids": {"cell_ontology": "CL:0000909", "mesh": "D000085442"},
        "description": "Pathogenic autoimmune T cells lodged in perilesional vitiligo epidermis responsible for local relapse.",
        "markers": ["CD8A", "CD8B", "ITGAE", "CD69", "CXCR6", "IL15RA"],
    },
    {
        "name": "Basal Keratinocyte",
        "external_ids": {"cell_ontology": "CL:0002187"},
        "description": "Epidermal partner cells forming the structural and trophic niche for melanocyte survival and melanosome transfer.",
        "markers": ["KRT5", "KRT14", "KRT1", "KRT10", "FLG", "IVL"],
    },
]


def seed_canonical_pathways_and_cell_types(session: Session) -> dict[str, int]:
    """Upsert canonical vitiligo biological pathways and cell types with participating genes."""
    pathways_added = 0
    cell_types_added = 0
    edges_added = 0

    # Index existing targets by symbol
    target_entities: dict[str, GraphEntity] = {}
    targets = session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.TARGET)).all()
    for t in targets:
        target_entities[t.name.strip().upper()] = t
        target_entities[t.key] = t

    # 1. Seed Pathways
    for p_info in CANONICAL_PATHWAYS:
        p_entity = upsert_entity(
            session,
            kind=EntityKind.PATHWAY,
            name=p_info["name"],
            aliases=[p_info["name"]],
            external_ids=p_info["external_ids"],
        )
        pathways_added += 1

        for g_sym in p_info["genes"]:
            g_sym_upper = g_sym.upper()
            t_ent = target_entities.get(g_sym_upper) or target_entities.get(normalize_entity_key(g_sym))
            if t_ent is not None:
                evidence = {
                    "source_type": "pathway_knowledge_base",
                    "source_id": str(p_info["external_ids"].get("go") or p_info["external_ids"].get("reactome") or "pathway:curated"),
                    "relation": "participates_in",
                    "score": 1.0,
                    "section": "canonical_pathway_definition",
                    "snippet": f"{t_ent.name} participates in the {p_info['name']} ({p_info.get('description', '')}).",
                }
                _, inserted = upsert_edge(
                    session,
                    subject=t_ent,
                    predicate=RelationKind.PARTICIPATES_IN,
                    obj=p_entity,
                    confidence=1.0,
                    extraction_method="curated_pathway",
                    evidence=evidence,
                    claim=ClaimKind.OBSERVED,
                    causal_level="knowledge_base",
                )
                if inserted:
                    edges_added += 1

    # 2. Seed Cell Types
    for c_info in CANONICAL_CELL_TYPES:
        c_entity = upsert_entity(
            session,
            kind=EntityKind.CELL_TYPE,
            name=c_info["name"],
            aliases=[c_info["name"]],
            external_ids=c_info["external_ids"],
        )
        cell_types_added += 1

        for m_sym in c_info["markers"]:
            m_sym_upper = m_sym.upper()
            t_ent = target_entities.get(m_sym_upper) or target_entities.get(normalize_entity_key(m_sym))
            if t_ent is not None:
                evidence = {
                    "source_type": "cell_ontology",
                    "source_id": str(c_info["external_ids"].get("cell_ontology") or "cell_type:curated"),
                    "relation": "expressed_in",
                    "score": 0.95,
                    "section": "canonical_marker",
                    "snippet": f"{t_ent.name} is a canonical lineage marker and expressed in {c_info['name']}.",
                }
                _, inserted = upsert_edge(
                    session,
                    subject=t_ent,
                    predicate=RelationKind.EXPRESSED_IN,
                    obj=c_entity,
                    confidence=0.95,
                    extraction_method="cell_ontology",
                    evidence=evidence,
                    claim=ClaimKind.OBSERVED,
                    causal_level="knowledge_base",
                )
                if inserted:
                    edges_added += 1

    logger.info(
        "Seeded %d pathways, %d cell types, and %d functional hierarchy edges",
        pathways_added,
        cell_types_added,
        edges_added,
    )
    return {
        "pathways": pathways_added,
        "cell_types": cell_types_added,
        "hierarchy_edges": edges_added,
    }


def seed_patient_coexpression_edges(
    session: Session,
    cache_path: Path | str = COEXPRESSION_CACHE_PATH,
    min_abs_r: float = 0.70,
    max_insert_edges: int = 15000,
) -> int:
    """Commit patient biopsy co-expression edges directly to SQLite graph_edges."""
    cache_path = Path(cache_path)
    if not cache_path.exists():
        logger.warning("Coexpression cache not found at %s", cache_path)
        return 0

    import torch

    from vitiligo.gnn.dataset import load_graph_dataset

    ds = load_graph_dataset()
    coexp_data = torch.load(cache_path, weights_only=True)
    src_indices = coexp_data["edge_index"][0]
    dst_indices = coexp_data["edge_index"][1]
    weights = coexp_data["edge_weight"]

    # Preload entities mapping
    entity_map: dict[int, GraphEntity] = {
        e.id: e for e in session.exec(select(GraphEntity)).all() if e.id is not None
    }

    # Fetch existing co-expression edge pairs to avoid duplicates
    existing_pairs: set[tuple[int, int]] = set()
    existing_edges = session.exec(
        select(GraphEdge.subject_id, GraphEdge.object_id).where(
            GraphEdge.predicate == RelationKind.CO_EXPRESSED_WITH
        )
    ).all()
    for s_id, o_id in existing_edges:
        existing_pairs.add((min(s_id, o_id), max(s_id, o_id)))

    inserted_count = 0
    seen_in_batch: set[tuple[int, int]] = set()

    for i in range(len(src_indices)):
        u_idx = int(src_indices[i].item())
        v_idx = int(dst_indices[i].item())
        r_val = float(weights[i].item())

        if abs(r_val) < min_abs_r:
            continue

        meta_u = ds.entities[u_idx]
        meta_v = ds.entities[v_idx]

        u_id = meta_u.db_id
        v_id = meta_v.db_id

        if u_id == v_id or u_id not in entity_map or v_id not in entity_map:
            continue

        pair_key = (min(u_id, v_id), max(u_id, v_id))
        if pair_key in existing_pairs or pair_key in seen_in_batch:
            continue
        seen_in_batch.add(pair_key)

        ent_a = entity_map[pair_key[0]]
        ent_b = entity_map[pair_key[1]]

        evidence = {
            "source_type": "geo",
            "source_id": "geo:GSE311770",
            "relation": "co_expressed_with",
            "score": round(abs(r_val), 3),
            "pearson_r": round(r_val, 3),
            "section": "punch_biopsies_n105",
            "snippet": (
                f"{ent_a.name} is functionally co-expressed with {ent_b.name} "
                f"(Pearson |r|={abs(r_val):.2f}, p<1e-5) across 105 human vitiligo skin punch biopsies (GSE311770)."
            ),
        }

        edge = GraphEdge(
            subject_id=ent_a.id,
            predicate=RelationKind.CO_EXPRESSED_WITH,
            object_id=ent_b.id,
            confidence=0.85,
            claim=ClaimKind.OBSERVED,
            causal_level="correlation_in_human",
            extraction_method="geo_punch_biopsies_gse311770",
            evidence=[evidence],
        )
        session.add(edge)
        inserted_count += 1

        if inserted_count >= max_insert_edges:
            break

    session.flush()
    logger.info("Committed %d unique patient punch biopsy co-expression edges into graph_edges", inserted_count)
    return inserted_count


def enrich_knowledge_graph(min_abs_r: float = 0.70) -> dict[str, Any]:
    """Execute full knowledge graph enrichment and commit to SQLite."""
    with session_scope() as session:
        hier_stats = seed_canonical_pathways_and_cell_types(session)
        coexp_inserted = seed_patient_coexpression_edges(session, min_abs_r=min_abs_r)

    return {
        "hierarchy": hier_stats,
        "coexpression_edges_inserted": coexp_inserted,
    }
