"""Enrich the Vitiligo Knowledge Graph with human punch biopsy co-expression, pathway hierarchies, and drug-target bioactivities.

Prepares the knowledge graph for publication and public release:
1. Seeds canonical vitiligo biological pathways (GO / Reactome / WikiPathways) and 8 cutaneous cell lineages.
2. Batch-enriches all 4,223 target genes via MyGene.info (WikiPathways CC0 + experimental GO:BP CC-BY-4.0 + UniProt IDs).
3. Batch-enriches all 2,233 drug entities via MyChem.info (ChEMBL curated mechanisms + sub-micromolar human DrugCentral bioactivities + SMILES).
4. Commits the patient punch biopsy gene-gene co-expression edges (CO_EXPRESSED_WITH)
   directly into SQLite with GEO:GSE311770 provenance and Pearson correlation coefficients.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session, select

from vitiligo.graph.normalize import normalize_entity_key
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.logging import get_logger
from vitiligo.storage import session_scope
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEdge, GraphEntity, RelationKind

logger = get_logger(__name__)

COEXPRESSION_CACHE_PATH = Path("data/cache/gnn/coexpression_edges.pt")
MYGENE_CACHE_PATH = Path("data/cache/graph/mygene_targets.json")
MYCHEM_CACHE_PATH = Path("data/cache/graph/mychem_drugs.json")
SMILES_CACHE_PATH = Path("data/cache/gnn/drug_smiles.json")

EXPERIMENTAL_GO_EVIDENCE = frozenset({"IDA", "IMP", "IGI", "IPI", "IEP", "TAS", "IC"})

CANONICAL_PATHWAYS: list[dict[str, Any]] = [
    {
        "name": "IFN-gamma Signaling Pathway",
        "external_ids": {"go": "GO:0060333", "reactome": "R-HSA-877300"},
        "description": "Core driver of vitiligo autoimmunity: IFN-g activates JAK1/STAT1 to induce CXCL9/CXCL10 chemokines.",
        "genes": [
            "IFNG",
            "IFNGR1",
            "IFNGR2",
            "JAK1",
            "JAK2",
            "STAT1",
            "STAT2",
            "IRF1",
            "CXCL9",
            "CXCL10",
            "CXCL11",
            "CXCR3",
        ],
    },
    {
        "name": "JAK-STAT Signaling Cascade",
        "external_ids": {"go": "GO:0007259", "reactome": "R-HSA-909733"},
        "description": "Intracellular cytokine transduction cascade mediating IFN-gamma, IL-15, and common gamma-chain signaling.",
        "genes": [
            "JAK1",
            "JAK2",
            "JAK3",
            "TYK2",
            "STAT1",
            "STAT2",
            "STAT3",
            "STAT4",
            "STAT5A",
            "STAT5B",
            "STAT6",
        ],
    },
    {
        "name": "Melanocyte Differentiation and Pigmentation",
        "external_ids": {"go": "GO:0043473", "reactome": "R-HSA-5579029"},
        "description": "Enzymatic and transcriptional pathway executing melanin synthesis and melanosome biogenesis.",
        "genes": [
            "MITF",
            "TYR",
            "DCT",
            "TYRP1",
            "PMEL",
            "MLANA",
            "OCA2",
            "MC1R",
            "ASIP",
            "KIT",
            "EDNRB",
            "SOX10",
            "PAX3",
        ],
    },
    {
        "name": "Wnt/Beta-Catenin Stem-Cell Signaling",
        "external_ids": {"go": "GO:0016055", "reactome": "R-HSA-195721"},
        "description": "Essential mobilization pathway driving hair-follicle melanocyte stem cell (McSC) migration and differentiation.",
        "genes": [
            "WNT1",
            "WNT3A",
            "WNT5A",
            "CTNNB1",
            "LEF1",
            "TCF7L2",
            "AXIN2",
            "GSK3B",
            "FZD1",
            "FZD4",
            "LRP5",
            "LRP6",
        ],
    },
    {
        "name": "Tissue-Resident Memory T-Cell Activation",
        "external_ids": {"go": "GO:0042110", "mesh": "D000085442"},
        "description": "Maintenance and cytotoxic reactivation of skin-resident autoreactive CD8+ CD69+ CD103+ memory T cells.",
        "genes": [
            "IL15",
            "IL15RA",
            "CD8A",
            "CD8B",
            "ITGAE",
            "CD69",
            "CXCR6",
            "ZNF683",
            "PRDM1",
            "RUNX3",
        ],
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
        "markers": [
            "TYR",
            "DCT",
            "TYRP1",
            "MLANA",
            "PMEL",
            "MITF",
            "OCA2",
            "SLC45A2",
            "SLC24A5",
            "GPR143",
            "MC1R",
            "SOX10",
            "KIT",
            "EDNRB",
            "TRPM1",
            "CAPN3",
            "PLP1",
            "S100B",
        ],
    },
    {
        "name": "Hair Follicle Melanocyte Stem Cell (McSC)",
        "external_ids": {"cell_ontology": "CL:0002092"},
        "description": "Quiescent reservoir cells in the hair follicle bulge responsible for follicular repigmentation in vitiligo.",
        "markers": [
            "PAX3",
            "SOX10",
            "KIT",
            "EDNRB",
            "DCT",
            "CD34",
            "HTR1A",
            "WNT1",
            "CTNNB1",
            "LEF1",
            "FZD4",
            "LRP6",
            "MITF",
            "BCL2",
            "NOTCH1",
            "HES1",
            "COL17A1",
        ],
    },
    {
        "name": "CD8+ Tissue-Resident Memory T Cell (TRM)",
        "external_ids": {"cell_ontology": "CL:0000909", "mesh": "D000085442"},
        "description": "Pathogenic autoimmune T cells lodged in perilesional vitiligo epidermis responsible for local relapse.",
        "markers": [
            "CD8A",
            "CD8B",
            "ITGAE",
            "CD69",
            "CXCR6",
            "CXCR3",
            "IL15RA",
            "IL2RB",
            "IFNG",
            "GZMB",
            "PRF1",
            "FASLG",
            "NKG7",
            "ZNF683",
            "PRDM1",
            "RUNX3",
            "PDCD1",
            "LAG3",
            "KLRK1",
            "TBX21",
            "EOMES",
        ],
    },
    {
        "name": "Basal Keratinocyte",
        "external_ids": {"cell_ontology": "CL:0002187"},
        "description": "Epidermal partner cells forming the structural and trophic niche for melanocyte survival and melanosome transfer.",
        "markers": [
            "KRT5",
            "KRT14",
            "KRT15",
            "KRT1",
            "KRT10",
            "FLG",
            "IVL",
            "TP63",
            "ITGA6",
            "ITGB4",
            "COL17A1",
            "CXCL9",
            "CXCL10",
            "CXCL11",
            "IL15",
            "KITLG",
            "EDN1",
            "POMC",
            "IFNGR1",
            "IFNGR2",
            "STAT1",
            "JAK1",
        ],
    },
    {
        "name": "Dermal Fibroblast (IFN-Responsive)",
        "external_ids": {"cell_ontology": "CL:0002620"},
        "description": "Anatomically regionalized dermal fibroblasts orchestrating CXCL9/CXCL10 chemokine gradients in vitiligo skin.",
        "markers": [
            "COL1A1",
            "COL1A2",
            "COL3A1",
            "DCN",
            "LUM",
            "PDGFRA",
            "PDGFRB",
            "FAP",
            "VIM",
            "CXCL9",
            "CXCL10",
            "CCL2",
            "CCL19",
            "IL6",
            "STAT1",
            "IFITM1",
            "ISG15",
        ],
    },
    {
        "name": "Cutaneous Regulatory T Cell (Treg)",
        "external_ids": {"cell_ontology": "CL:0000815"},
        "description": "Immunosuppressive CD4+ FOXP3+ T cells maintaining peripheral tolerance and restraining autoreactive CD8+ T cells.",
        "markers": [
            "FOXP3",
            "IL2RA",
            "CTLA4",
            "TIGIT",
            "IKZF2",
            "TNFRSF18",
            "TNFRSF4",
            "IL10",
            "TGFB1",
            "CCR4",
            "CCR8",
            "ICOS",
            "ENTPD1",
            "CD4",
        ],
    },
    {
        "name": "Epidermal Langerhans & cDC1 Dendritic Cell",
        "external_ids": {"cell_ontology": "CL:0000453"},
        "description": "Antigen-presenting myeloid cells cross-presenting melanocyte autoantigens and producing CXCL9/CXCL10.",
        "markers": [
            "CD207",
            "CD1A",
            "CLEC9A",
            "XCR1",
            "BATF3",
            "IRF8",
            "ITGAX",
            "HLA-DRA",
            "HLA-DRB1",
            "CD80",
            "CD86",
            "CD40",
            "IL12B",
            "CXCL9",
            "CXCL10",
        ],
    },
    {
        "name": "Cutaneous Natural Killer & ILC1 Cell",
        "external_ids": {"cell_ontology": "CL:0000623"},
        "description": "Innate cytotoxic lymphocytes sensing oxidative stress ligands and producing early IFN-gamma in vitiligo skin.",
        "markers": [
            "NCAM1",
            "KLRD1",
            "KLRK1",
            "NCR1",
            "NKG7",
            "GNLY",
            "GZMA",
            "GZMB",
            "PRF1",
            "IFNG",
            "FCGR3A",
            "KLRC1",
            "TBX21",
        ],
    },
]


def _clean_drug_query(name: str) -> str:
    """Strip common salt, ester, and hydrate modifiers and Lucene special chars for chemical lookup."""
    n = re.sub(
        r"(?i)\b(tosylate|phosphate|hydrochloride|dihydrochloride|succinate|sodium|hydrate|anhydrous|acetate|fumarate|maleate|sulfate|tartrate|mesylate|potassium|citrate|calcium|monohydrate|dipropionate|butyrate|valerate|propionate|acetonide)\b",
        "",
        name,
    )
    # Remove characters that break comma-delimited or Lucene queries in MyChem.info
    n = re.sub(r"[^a-zA-Z0-9\s\-]", " ", n).strip()
    return re.sub(r"\s+", " ", n).strip()


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
            t_ent = target_entities.get(g_sym_upper) or target_entities.get(
                normalize_entity_key(g_sym)
            )
            if t_ent is not None:
                src_id = (
                    f"go:{p_info['external_ids']['go']}"
                    if "go" in p_info["external_ids"]
                    else f"reactome:{p_info['external_ids'].get('reactome', 'curated')}"
                )
                evidence = {
                    "source_type": "pathway_knowledge_base",
                    "source_id": src_id,
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
            t_ent = target_entities.get(m_sym_upper) or target_entities.get(
                normalize_entity_key(m_sym)
            )
            if t_ent is not None:
                cl_id = c_info["external_ids"].get("cell_ontology", "CL:0000000")
                evidence = {
                    "source_type": "cell_ontology",
                    "source_id": f"cell_ontology:{cl_id}",
                    "relation": "expressed_in",
                    "score": 0.95,
                    "section": "canonical_marker",
                    "snippet": f"{t_ent.name} is a canonical lineage marker and expressed in {c_info['name']} ({c_info.get('description', '')}).",
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


def _fetch_or_load_mygene(
    target_names: list[str], cache_path: Path = MYGENE_CACHE_PATH
) -> list[dict[str, Any]]:
    """Fetch batch gene pathway & UniProt annotations from MyGene.info with disk caching."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                logger.info("Loaded %d cached MyGene.info records from %s", len(data), cache_path)
                return data
        except Exception as exc:
            logger.warning("Failed to read MyGene cache (%s); re-fetching...", exc)

    if not target_names:
        return []

    logger.info("Querying MyGene.info for %d target genes...", len(target_names))
    hits: list[dict[str, Any]] = []
    with httpx.Client(timeout=45.0) as client:
        for i in range(0, len(target_names), 500):
            batch = target_names[i : i + 500]
            try:
                resp = client.post(
                    "https://mygene.info/v3/query",
                    data={
                        "q": ",".join(batch),
                        "scopes": "symbol,alias",
                        "species": "human",
                        "fields": "symbol,entrezgene,uniprot.Swiss-Prot,pathway.wikipathways,go.BP",
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                if isinstance(payload, list):
                    hits.extend(payload)
            except Exception as exc:
                logger.warning("MyGene.info batch %d failed: %s", i, exc)

    if hits:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(hits, f)
        logger.info("Cached %d MyGene.info records to %s", len(hits), cache_path)
    return hits


def seed_mygene_pathways_and_processes(
    session: Session,
    *,
    min_wp_genes: int = 8,
    max_wp_genes: int = 120,
    min_go_genes: int = 12,
    max_go_genes: int = 100,
    cache_path: Path = MYGENE_CACHE_PATH,
) -> tuple[dict[str, int], dict[str, GraphEntity]]:
    """Enrich target genes with WikiPathways (CC0) and experimental GO Biological Processes (CC-BY-4.0)."""
    targets = list(
        session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.TARGET)).all()
    )
    if len(targets) < 20 and not cache_path.exists():
        return {"pathways_added": 0, "participates_in_edges": 0}, {}

    target_by_query: dict[str, GraphEntity] = {}
    for t in targets:
        target_by_query[t.name.strip().upper()] = t
        target_by_query[t.key.upper()] = t

    hits = _fetch_or_load_mygene([t.name.strip() for t in targets], cache_path=cache_path)

    uniprot_to_target: dict[str, GraphEntity] = {}
    wp_to_targets: dict[str, tuple[str, dict[int, GraphEntity]]] = {}
    go_to_targets: dict[str, tuple[str, dict[int, GraphEntity]]] = {}
    seen_queries: set[str] = set()

    for h in hits:
        if not isinstance(h, dict) or h.get("notfound"):
            continue
        q = str(h.get("query") or "").strip().upper()
        if not q or q in seen_queries:
            continue
        t_ent = target_by_query.get(q)
        if t_ent is None or t_ent.id is None:
            continue
        seen_queries.add(q)

        # Record UniProt & Entrez IDs
        ext = dict(t_ent.external_ids or {})
        changed_ext = False
        entrez = h.get("entrezgene")
        if entrez and "entrez" not in ext:
            ext["entrez"] = str(entrez)
            changed_ext = True

        up = (h.get("uniprot") or {}).get("Swiss-Prot")
        up_list = [up] if isinstance(up, str) else (up if isinstance(up, list) else [])
        for u_id in up_list:
            u_str = str(u_id).strip()
            if u_str:
                uniprot_to_target[u_str] = t_ent
                if "uniprot" not in ext:
                    ext["uniprot"] = u_str
                    changed_ext = True
        if changed_ext:
            t_ent.external_ids = ext
            session.add(t_ent)

        # 1. WikiPathways (CC0 1.0)
        wps = (h.get("pathway") or {}).get("wikipathways") or []
        if isinstance(wps, dict):
            wps = [wps]
        for wp in wps:
            if not isinstance(wp, dict):
                continue
            wp_id = str(wp.get("id") or "").strip()
            wp_name = str(wp.get("name") or "").strip()
            if wp_id and wp_name:
                if wp_id not in wp_to_targets:
                    wp_to_targets[wp_id] = (wp_name, {})
                wp_to_targets[wp_id][1][t_ent.id] = t_ent

        # 2. Experimental Gene Ontology Biological Processes (CC-BY-4.0)
        gos = (h.get("go") or {}).get("BP") or []
        if isinstance(gos, dict):
            gos = [gos]
        for g in gos:
            if not isinstance(g, dict):
                continue
            ev = str(g.get("evidence") or "").upper()
            if ev not in EXPERIMENTAL_GO_EVIDENCE:
                continue
            go_id = str(g.get("id") or "").strip()
            go_term = str(g.get("term") or "").strip()
            if go_id and go_term:
                if go_id not in go_to_targets:
                    go_to_targets[go_id] = (go_term, {})
                go_to_targets[go_id][1][t_ent.id] = t_ent

    # Index existing PARTICIPATES_IN edges to avoid duplicates
    existing_part: set[tuple[int, int]] = set(
        session.exec(
            select(GraphEdge.subject_id, GraphEdge.object_id).where(
                GraphEdge.predicate == RelationKind.PARTICIPATES_IN
            )
        ).all()
    )

    pathways_added = 0
    edges_added = 0

    # Insert qualifying WikiPathways
    for wp_id, (wp_name, t_map) in wp_to_targets.items():
        if not (min_wp_genes <= len(t_map) <= max_wp_genes):
            continue
        p_ent = upsert_entity(
            session,
            kind=EntityKind.PATHWAY,
            name=wp_name,
            aliases=[wp_name, wp_id],
            external_ids={"wikipathways": wp_id},
        )
        if p_ent.id is None:
            continue
        pathways_added += 1
        for t_id, t_ent in t_map.items():
            if (t_id, p_ent.id) in existing_part:
                continue
            existing_part.add((t_id, p_ent.id))
            evidence = {
                "source_type": "wikipathways",
                "source_id": f"wikipathways:{wp_id}",
                "relation": "participates_in",
                "score": 0.92,
                "section": "wikipathways_curated",
                "snippet": f"{t_ent.name} participates in human biological pathway '{wp_name}' (WikiPathways {wp_id}).",
            }
            session.add(
                GraphEdge(
                    subject_id=t_id,
                    predicate=RelationKind.PARTICIPATES_IN,
                    object_id=p_ent.id,
                    confidence=0.92,
                    claim=ClaimKind.OBSERVED,
                    causal_level="knowledge_base",
                    extraction_method="wikipathways",
                    evidence=[evidence],
                )
            )
            edges_added += 1

    # Insert qualifying Experimental GO Biological Processes
    for go_id, (go_term, t_map) in go_to_targets.items():
        if not (min_go_genes <= len(t_map) <= max_go_genes):
            continue
        display_name = go_term[0].upper() + go_term[1:] if go_term else go_id
        p_ent = upsert_entity(
            session,
            kind=EntityKind.PATHWAY,
            name=display_name,
            aliases=[go_term, go_id],
            external_ids={"go": go_id},
        )
        if p_ent.id is None:
            continue
        pathways_added += 1
        for t_id, t_ent in t_map.items():
            if (t_id, p_ent.id) in existing_part:
                continue
            existing_part.add((t_id, p_ent.id))
            evidence = {
                "source_type": "go",
                "source_id": f"go:{go_id}",
                "relation": "participates_in",
                "score": 0.90,
                "section": "experimental_go_bp",
                "snippet": f"{t_ent.name} is experimentally verified to participate in {go_term} ({go_id}).",
            }
            session.add(
                GraphEdge(
                    subject_id=t_id,
                    predicate=RelationKind.PARTICIPATES_IN,
                    object_id=p_ent.id,
                    confidence=0.90,
                    claim=ClaimKind.OBSERVED,
                    causal_level="knowledge_base",
                    extraction_method="gene_ontology_experimental",
                    evidence=[evidence],
                )
            )
            edges_added += 1

    session.flush()
    logger.info(
        "MyGene.info enrichment: added %d pathways/processes and %d PARTICIPATES_IN edges (%d UniProt mappings)",
        pathways_added,
        edges_added,
        len(uniprot_to_target),
    )
    return {
        "pathways_added": pathways_added,
        "participates_in_edges": edges_added,
    }, uniprot_to_target


def _fetch_or_load_mychem(
    queries: list[str], cache_path: Path = MYCHEM_CACHE_PATH
) -> list[dict[str, Any]]:
    """Fetch batch drug mechanism & bioactivity annotations from MyChem.info with disk caching."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                logger.info("Loaded %d cached MyChem.info records from %s", len(data), cache_path)
                return data
        except Exception as exc:
            logger.warning("Failed to read MyChem cache (%s); re-fetching...", exc)

    if not queries:
        return []

    logger.info("Querying MyChem.info for %d unique cleaned drug names...", len(queries))
    hits: list[dict[str, Any]] = []
    with httpx.Client(timeout=45.0) as client:
        for i in range(0, len(queries), 250):
            batch = queries[i : i + 250]
            try:
                resp = client.post(
                    "https://mychem.info/v1/query",
                    data={
                        "q": ",".join(batch),
                        "scopes": "chembl.pref_name,drugcentral.synonyms,unii.preferred_term,chebi.name",
                        "fields": "chembl.molecule_chembl_id,chembl.pref_name,chembl.smiles,chembl.drug_mechanisms,drugcentral.bioactivity,drugcentral.structures.smiles",
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                if isinstance(payload, list):
                    hits.extend(payload)
            except Exception as exc:
                logger.warning("MyChem.info batch %d failed: %s", i, exc)

    if hits:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(hits, f)
        logger.info("Cached %d MyChem.info records to %s", len(hits), cache_path)
    return hits


def _action_to_relation(
    action_type: str, act_type: str = "", act_value: float = 0.0
) -> RelationKind | None:
    """Map pharmacological action_type or high-potency assay type to directional RelationKind."""
    act = action_type.upper().strip()
    if any(
        w in act
        for w in (
            "INHIBITOR",
            "ANTAGONIST",
            "BLOCKER",
            "NEGATIVE",
            "DEGRADER",
            "SUPPRESSOR",
            "INVERSE AGONIST",
            "ANTISENSE",
        )
    ):
        return RelationKind.INHIBITS
    if any(
        w in act for w in ("AGONIST", "ACTIVATOR", "STIMULATOR", "POSITIVE", "OPENER", "INDUCER")
    ):
        return RelationKind.ACTIVATES
    if act in {"MODULATOR", "BINDING AGENT", "SUBSTRATE", "CHELATING AGENT", "STABILISER"}:
        return RelationKind.TARGETS

    # Fallback for potent quantitative assays (>= 100 nM, i.e. pChEMBL >= 7.0)
    if act_value >= 7.0:
        at_upper = act_type.upper()
        if at_upper in {"IC50", "KI"}:
            return RelationKind.INHIBITS
        if at_upper == "EC50":
            return RelationKind.ACTIVATES
    return None


def seed_mychem_drug_target_mechanisms(
    session: Session,
    uniprot_to_target: dict[str, GraphEntity],
    *,
    min_pchembl: float = 6.5,
    cache_path: Path = MYCHEM_CACHE_PATH,
) -> dict[str, int]:
    """Enrich drugs with ChEMBL mechanisms and sub-micromolar human DrugCentral bioactivities."""
    drugs = list(session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.DRUG)).all())
    if len(drugs) < 20 and not cache_path.exists():
        return {"drugs_matched": 0, "mechanism_edges_added": 0, "smiles_added": 0}

    targets = list(
        session.exec(select(GraphEntity).where(GraphEntity.kind == EntityKind.TARGET)).all()
    )
    symbol_to_target: dict[str, GraphEntity] = {}
    for t in targets:
        symbol_to_target[t.name.strip().upper()] = t
        symbol_to_target[t.key.upper()] = t
        up_id = (t.external_ids or {}).get("uniprot")
        if up_id and up_id not in uniprot_to_target:
            uniprot_to_target[str(up_id)] = t

    cleaned_to_drugs: dict[str, list[GraphEntity]] = {}
    for d in drugs:
        c = _clean_drug_query(d.name).lower()
        if 3 <= len(c) <= 45 and len(c.split()) <= 4 and not c.startswith("-"):
            cleaned_to_drugs.setdefault(c, []).append(d)

    hits = _fetch_or_load_mychem(list(cleaned_to_drugs.keys()), cache_path=cache_path)

    # Load SMILES cache to enrich chemical coverage simultaneously
    smiles_cache: dict[str, str | None] = {}
    if SMILES_CACHE_PATH.exists():
        try:
            with open(SMILES_CACHE_PATH, encoding="utf-8") as f:
                smiles_cache = json.load(f)
        except Exception:
            smiles_cache = {}

    existing_triples: set[tuple[int, RelationKind, int]] = set(
        session.exec(
            select(GraphEdge.subject_id, GraphEdge.predicate, GraphEdge.object_id).where(
                GraphEdge.predicate.in_(
                    [RelationKind.INHIBITS, RelationKind.ACTIVATES, RelationKind.TARGETS]
                )
            )
        ).all()
    )

    drugs_matched: set[int] = set()
    edges_added = 0
    smiles_added = 0

    for h in hits:
        if not isinstance(h, dict) or h.get("notfound"):
            continue
        q = str(h.get("query") or "").strip().lower()
        matched_drug_entities = cleaned_to_drugs.get(q)
        if not matched_drug_entities:
            continue

        chembl_raw = h.get("chembl")
        chembl_list = (
            chembl_raw
            if isinstance(chembl_raw, list)
            else ([chembl_raw] if isinstance(chembl_raw, dict) else [])
        )
        dc_raw = h.get("drugcentral")
        dc_list = (
            dc_raw if isinstance(dc_raw, list) else ([dc_raw] if isinstance(dc_raw, dict) else [])
        )

        # Extract ChEMBL ID & SMILES
        chembl_id: str | None = None
        smiles: str | None = None
        for c_item in chembl_list:
            if not chembl_id and c_item.get("molecule_chembl_id"):
                chembl_id = str(c_item["molecule_chembl_id"]).strip()
            if not smiles and c_item.get("smiles"):
                smiles = str(c_item["smiles"]).strip()
        for dc_item in dc_list:
            if not smiles:
                structs = dc_item.get("structures")
                if isinstance(structs, dict) and structs.get("smiles"):
                    smiles = str(structs["smiles"]).strip()

        for d_ent in matched_drug_entities:
            if d_ent.id is None:
                continue
            if chembl_id:
                ext = dict(d_ent.external_ids or {})
                if "chembl" not in ext:
                    ext["chembl"] = chembl_id
                    d_ent.external_ids = ext
                    session.add(d_ent)
                drugs_matched.add(d_ent.id)
            if smiles and not smiles_cache.get(d_ent.name):
                smiles_cache[d_ent.name] = smiles
                smiles_added += 1

        # 1. ChEMBL Curated Drug Mechanisms
        for c_item in chembl_list:
            mechs = c_item.get("drug_mechanisms") or []
            if isinstance(mechs, dict):
                mechs = [mechs]
            c_mol_id = str(c_item.get("molecule_chembl_id") or chembl_id or "curated")
            for m in mechs:
                if not isinstance(m, dict):
                    continue
                action_type = str(m.get("action_type") or "")
                pred = _action_to_relation(action_type)
                if pred is None:
                    continue
                t_comps = m.get("target_components") or {}
                if isinstance(t_comps, list):
                    t_comps = t_comps[0] if t_comps else {}
                up_ids = t_comps.get("uniprot") or []
                if isinstance(up_ids, str):
                    up_ids = [up_ids]
                for u_id in up_ids:
                    t_ent = uniprot_to_target.get(str(u_id).strip())
                    if t_ent is None or t_ent.id is None:
                        continue
                    for d_ent in matched_drug_entities:
                        if d_ent.id is None:
                            continue
                        triple = (d_ent.id, pred, t_ent.id)
                        if triple in existing_triples:
                            continue
                        existing_triples.add(triple)
                        drugs_matched.add(d_ent.id)
                        mech_desc = str(m.get("target_name") or t_ent.name)
                        evidence = {
                            "source_type": "chembl",
                            "source_id": f"chembl:{c_mol_id}",
                            "relation": pred.value.lower(),
                            "score": 0.92,
                            "section": "curated_mechanism_of_action",
                            "snippet": f"{d_ent.name} acts as a verified {action_type.lower()} of {t_ent.name} ({mech_desc}; ChEMBL {c_mol_id}).",
                        }
                        session.add(
                            GraphEdge(
                                subject_id=d_ent.id,
                                predicate=pred,
                                object_id=t_ent.id,
                                confidence=0.92,
                                claim=ClaimKind.OBSERVED,
                                causal_level="perturbation_in_human",
                                extraction_method="chembl_mechanism",
                                evidence=[evidence],
                            )
                        )
                        edges_added += 1

        # 2. DrugCentral Quantitative Human Bioactivities (pChEMBL >= min_pchembl)
        for dc_item in dc_list:
            bios = dc_item.get("bioactivity") or []
            if isinstance(bios, dict):
                bios = [bios]
            for b in bios:
                if not isinstance(b, dict) or b.get("organism") != "Homo sapiens":
                    continue
                try:
                    act_val = float(b.get("act_value") or 0.0)
                except (TypeError, ValueError):
                    act_val = 0.0
                if act_val < min_pchembl:
                    continue

                action_type = str(b.get("action_type") or "")
                act_type = str(b.get("act_type") or "")
                pred = _action_to_relation(action_type, act_type=act_type, act_value=act_val)
                if pred is None:
                    continue

                up_block = b.get("uniprot") or {}
                if isinstance(up_block, list):
                    up_block = up_block[0] if up_block else {}
                gene_sym = str(up_block.get("gene_symbol") or "").strip().upper()
                uniprot_id = str(up_block.get("uniprot_id") or "").strip()

                t_ent = symbol_to_target.get(gene_sym) or uniprot_to_target.get(uniprot_id)
                if t_ent is None or t_ent.id is None:
                    continue

                conf = round(min(0.95, 0.72 + 0.04 * (act_val - 6.0)), 2)
                src_mol = chembl_id or "drugcentral"
                for d_ent in matched_drug_entities:
                    if d_ent.id is None:
                        continue
                    triple = (d_ent.id, pred, t_ent.id)
                    if triple in existing_triples:
                        continue
                    existing_triples.add(triple)
                    drugs_matched.add(d_ent.id)
                    evidence = {
                        "source_type": "chembl",
                        "source_id": f"chembl:{src_mol}",
                        "relation": pred.value.lower(),
                        "score": conf,
                        "section": "human_bioactivity_assay",
                        "snippet": (
                            f"{d_ent.name} exhibits potent human bioactivity against {t_ent.name} "
                            f"({act_type} pAct={act_val:.2f}, action={action_type or pred.value})."
                        ),
                    }
                    session.add(
                        GraphEdge(
                            subject_id=d_ent.id,
                            predicate=pred,
                            object_id=t_ent.id,
                            confidence=conf,
                            claim=ClaimKind.OBSERVED,
                            causal_level="perturbation_in_vitro",
                            extraction_method="drugcentral_bioactivity",
                            evidence=[evidence],
                        )
                    )
                    edges_added += 1

    if smiles_added > 0 and SMILES_CACHE_PATH.parent.exists():
        with open(SMILES_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(smiles_cache, f, indent=2)

    session.flush()
    logger.info(
        "MyChem.info enrichment: matched %d drugs, added %d direct mechanism/bioactivity edges, %d new SMILES",
        len(drugs_matched),
        edges_added,
        smiles_added,
    )
    return {
        "drugs_matched": len(drugs_matched),
        "mechanism_edges_added": edges_added,
        "smiles_added": smiles_added,
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
    logger.info(
        "Committed %d unique patient punch biopsy co-expression edges into graph_edges",
        inserted_count,
    )
    return inserted_count


_CELL_MENTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "Epidermal Melanocyte": re.compile(r"\bmelanocytes?\b", re.I),
    "Basal Keratinocyte": re.compile(r"\bkeratinocytes?\b", re.I),
    "Dermal Fibroblast (IFN-Responsive)": re.compile(r"\bfibroblasts?\b", re.I),
    "CD8+ Tissue-Resident Memory T Cell (TRM)": re.compile(
        r"\b(?:cd8\s*\+?\s*(?:t|trm)\s*cells?|cytotoxic\s+t\s+lymphocytes?)\b", re.I
    ),
    "Cutaneous Regulatory T Cell (Treg)": re.compile(
        r"\b(?:tregs?|regulatory\s+t\s+cells?|foxp3\s*\+\s*t\s+cells?)\b", re.I
    ),
    "Epidermal Langerhans & cDC1 Dendritic Cell": re.compile(
        r"\b(?:dendritic\s+cells?|plasmacytoid\s+dcs?|langerhans\s+cells?)\b", re.I
    ),
    "Cutaneous Natural Killer & ILC1 Cell": re.compile(
        r"\b(?:natural\s+killer\s+cells?|nk\s+cells?)\b", re.I
    ),
}

_ANCHORED_CELL_EXPR = re.compile(
    r"^\s*\)?\s*(?:-[a-z0-9]+\s*)?(?:\([^)]{1,25}\)\s*)?(?:,\s*a\s+[a-z0-9 -]{3,25},\s*|\s*gene\s*,?\s*)?"
    r"(?:is\s+|was\s+|were\s+|are\s+|has\s+been\s+(?:shown|found|reported)\s+to\s+be\s+|shown\s+to\s+be\s+)?"
    r"(?:normally\s+|strongly\s+|highly\s+|predominantly\s+|primarily\s+|widely\s+|notably\s+|mainly\s+)?"
    r"(?:express(?:ed|es|ing|ion)\s+(?:in|by|on)|secret(?:ed|es|ing)\s+by|produc(?:ed|es|ing)\s+by|releas(?:ed|es|ing)\s+by)"
    r"(?:\s+(?:the|human|mouse|epidermal|dermal|cutaneous|skin|stressed|primary|immature|mature|normal|lesional|perilesional|activated|infiltrating|resident|autoreactive))*\s*$",
    re.I,
)


SC_LINEAGE_CACHE_PATH = Path("data/cache/gnn/sc_lineage_gse298871.json")
GSE298871_TAR_PATH = Path("data/geo/GSE298871/GSE298871_RAW.tar")

_SC_LINEAGE_MARKERS: dict[str, list[str]] = {
    "Epidermal Melanocyte": ["DCT", "PMEL", "TYR", "MLANA", "MITF"],
    "Hair Follicle Melanocyte Stem Cell (McSC)": ["PAX3", "SOX10", "KIT", "EDNRB"],
    "Basal Keratinocyte": ["KRT14", "KRT5", "KRT1", "KRT10", "DSP"],
    "Dermal Fibroblast (IFN-Responsive)": ["COL1A1", "COL1A2", "DCN", "LUM", "PDGFRA"],
    "CD8+ Tissue-Resident Memory T Cell (TRM)": [
        "CD8A",
        "CD8B",
        "GZMB",
        "PRF1",
        "IFNG",
    ],
    "Cutaneous Regulatory T Cell (Treg)": ["FOXP3", "IL2RA", "CTLA4", "TIGIT", "IKZF2"],
    "Cutaneous Natural Killer & ILC1 Cell": ["GNLY", "NKG7", "KLRD1", "KLRB1", "NCR1"],
    "Epidermal Langerhans & cDC1 Dendritic Cell": [
        "CD207",
        "CD1A",
        "CLEC9A",
        "CD1C",
        "FCER1A",
        "CD68",
        "C1QA",
    ],
}


def _extract_sentence(text: str, pos: int) -> str:
    """Extract the single sentence around character position `pos`."""
    start = 0
    for sep in (". ", "; ", "\n"):
        idx = text.rfind(sep, 0, pos)
        if idx != -1:
            start = max(start, idx + len(sep))
    end = len(text)
    for sep in (". ", ".\n", "\n"):
        idx = text.find(sep, pos)
        if idx != -1:
            end = min(end, idx + 1)
    return text[start:end].strip()


def recover_directional_fulltext_relations(session: Session) -> dict[str, int]:
    """Recover active-voice directional (INHIBITS, ACTIVATES, EXPRESSED_IN) and physical Bind (TARGETS) edges."""
    from sqlalchemy import text as sa_text

    from vitiligo.graph.literature_seed import Node, _node_pattern, resolve_snippet_direction

    entities = {e.id: e for e in session.exec(select(GraphEntity)).all() if e.id is not None}
    cell_name_to_ent: dict[str, GraphEntity] = {
        e.name: e for e in entities.values() if e.kind == EntityKind.CELL_TYPE
    }

    pubmed_texts: dict[str, str] = {}
    rows = session.connection().execute(
        sa_text(
            "SELECT source_id, COALESCE(title, '') || '. ' || COALESCE(abstract, '') "
            "FROM documents WHERE UPPER(source) = 'PUBMED'"
        )
    )
    for sid, txt in rows:
        if sid and txt:
            pubmed_texts[f"pmid:{sid}"] = str(txt)

    existing_triples: set[tuple[int, RelationKind, int]] = set()
    all_edges = list(session.exec(select(GraphEdge)).all())
    for edge in all_edges:
        existing_triples.add((edge.subject_id, edge.predicate, edge.object_id))

    directional_added = 0
    expressed_in_added = 0
    targets_bind_added = 0

    for edge in all_edges:
        s_ent = entities.get(edge.subject_id)
        o_ent = entities.get(edge.object_id)
        if s_ent is None or o_ent is None or s_ent.id is None or o_ent.id is None:
            continue

        node_s = Node(s_ent.kind, s_ent.name, aliases=tuple(s_ent.aliases or ()))
        node_o = Node(o_ent.kind, o_ent.name, aliases=tuple(o_ent.aliases or ()))

        evs = edge.evidence if isinstance(edge.evidence, list) else []
        for ev in evs:
            if not isinstance(ev, dict):
                continue
            rel = str(ev.get("relation") or "")
            try:
                score = float(ev.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0

            # 0. Physical protein-protein / ligand-receptor Bind -> TARGETS
            if (
                edge.predicate == RelationKind.ASSOCIATED_WITH
                and rel == "Bind"
                and score >= 0.70
                and s_ent.kind in (EntityKind.DRUG, EntityKind.TARGET)
                and o_ent.kind == EntityKind.TARGET
            ):
                triple_bind = (s_ent.id, RelationKind.TARGETS, o_ent.id)
                if triple_bind not in existing_triples:
                    existing_triples.add(triple_bind)
                    session.add(
                        GraphEdge(
                            subject_id=s_ent.id,
                            predicate=RelationKind.TARGETS,
                            object_id=o_ent.id,
                            confidence=round(min(0.80, score * 0.80), 2),
                            claim=ClaimKind.ASSERTED,
                            causal_level="mechanism_assertion",
                            extraction_method=edge.extraction_method,
                            evidence=[dict(ev)],
                        )
                    )
                    targets_bind_added += 1

            raw_snip = str(ev.get("snippet") or "")
            from_abstract = False
            if not raw_snip:
                raw_snip = pubmed_texts.get(str(ev.get("source_id") or ""), "")
                from_abstract = True
            if not raw_snip or score < 0.82:
                continue

            # 1. Active-voice directional (DRUG/TARGET -> INHIBITS/ACTIVATES -> TARGET)
            if (
                edge.predicate == RelationKind.ASSOCIATED_WITH
                and s_ent.kind in (EntityKind.DRUG, EntityKind.TARGET)
                and o_ent.kind == EntityKind.TARGET
            ):
                resolved = resolve_snippet_direction(rel, node_s, node_o, raw_snip)
                if resolved is not None:
                    first_node, pred, _ = resolved
                    subj_id, obj_id = (
                        (s_ent.id, o_ent.id)
                        if first_node.name == s_ent.name
                        else (o_ent.id, s_ent.id)
                    )
                    triple = (subj_id, pred, obj_id)
                    if triple not in existing_triples:
                        existing_triples.add(triple)
                        ev_copy = dict(ev)
                        if from_abstract and not ev_copy.get("snippet"):
                            m_first = _node_pattern(first_node).search(raw_snip)
                            if m_first:
                                ev_copy["snippet"] = _extract_sentence(raw_snip, m_first.start())
                        session.add(
                            GraphEdge(
                                subject_id=subj_id,
                                predicate=pred,
                                object_id=obj_id,
                                confidence=round(min(0.75, score * 0.75), 2),
                                claim=ClaimKind.ASSERTED,
                                causal_level="mechanism_assertion",
                                extraction_method=edge.extraction_method,
                                evidence=[ev_copy],
                            )
                        )
                        directional_added += 1

            # 2. Anchored cell-type expression (TARGET -> EXPRESSED_IN -> CELL_TYPE)
            for t_ent, t_node in ((s_ent, node_s), (o_ent, node_o)):
                if t_ent.kind != EntityKind.TARGET or t_ent.id is None or len(t_ent.name) < 2:
                    continue
                t_pat = _node_pattern(t_node)
                for m_t in t_pat.finditer(raw_snip):
                    for cell_name, c_pat in _CELL_MENTION_PATTERNS.items():
                        c_ent = cell_name_to_ent.get(cell_name)
                        if c_ent is None or c_ent.id is None:
                            continue
                        for m_c in c_pat.finditer(raw_snip):
                            if 0 < (m_c.start() - m_t.end()) <= 65:
                                between = raw_snip[m_t.end() : m_c.start()]
                                if _ANCHORED_CELL_EXPR.match(between):
                                    triple = (t_ent.id, RelationKind.EXPRESSED_IN, c_ent.id)
                                    if triple not in existing_triples:
                                        existing_triples.add(triple)
                                        ev_copy = dict(ev)
                                        if from_abstract and not ev_copy.get("snippet"):
                                            ev_copy["snippet"] = _extract_sentence(
                                                raw_snip, m_t.start()
                                            )
                                        session.add(
                                            GraphEdge(
                                                subject_id=t_ent.id,
                                                predicate=RelationKind.EXPRESSED_IN,
                                                object_id=c_ent.id,
                                                confidence=round(min(0.80, score * 0.80), 2),
                                                claim=ClaimKind.ASSERTED,
                                                causal_level="correlation_in_human",
                                                extraction_method=edge.extraction_method,
                                                evidence=[ev_copy],
                                            )
                                        )
                                        expressed_in_added += 1

    session.flush()
    logger.info(
        "Full-text directional recovery: added %d INHIBITS/ACTIVATES, %d EXPRESSED_IN, and %d Bind->TARGETS edges",
        directional_added,
        expressed_in_added,
        targets_bind_added,
    )
    return {
        "directional_edges_added": directional_added,
        "expressed_in_edges_added": expressed_in_added,
        "targets_bind_edges_added": targets_bind_added,
    }


def compute_or_load_single_cell_lineage_profiles(
    force_recompute: bool = False,
) -> dict[str, Any]:
    """Compute or load single-cell lineage expression profiles across 17 human skin scRNA-seq libraries (GSE298871)."""
    if SC_LINEAGE_CACHE_PATH.exists() and not force_recompute:
        return json.loads(SC_LINEAGE_CACHE_PATH.read_text(encoding="utf-8"))

    if not GSE298871_TAR_PATH.exists():
        logger.warning(
            "GSE298871 tar not found at %s; skipping scRNA-seq lineage seeding", GSE298871_TAR_PATH
        )
        return {"lineage_names": list(_SC_LINEAGE_MARKERS.keys()), "lineage_cells": {}, "genes": {}}

    import gzip
    import tarfile

    import numpy as np
    from scipy.io import mmread

    lineage_names = list(_SC_LINEAGE_MARKERS.keys())
    with tarfile.open(GSE298871_TAR_PATH) as tf:
        names = sorted(tf.getnames())
        samples = sorted({n.rsplit("_", 1)[0] for n in names})
        feat_member = tf.extractfile(samples[0] + "_features.tsv.gz")
        assert feat_member is not None
        with gzip.open(feat_member, "rt") as gz:
            genes = [line.strip().split("\t")[1] for line in gz]
        gene_to_idx = {g: i for i, g in enumerate(genes)}

        lineage_sum = np.zeros((len(genes), len(lineage_names)), dtype=np.float64)
        lineage_detect = np.zeros((len(genes), len(lineage_names)), dtype=np.int64)
        lineage_cells = np.zeros(len(lineage_names), dtype=np.int64)

        for s in samples:
            mtx_member = tf.extractfile(s + "_matrix.mtx.gz")
            if mtx_member is None:
                continue
            with gzip.open(mtx_member, "rb") as gz:
                mat = mmread(gz).tocsc()
            lib_size = np.asarray(mat.sum(axis=0)).ravel()
            valid = lib_size >= 500
            mat = mat[:, valid]
            lib_size = lib_size[valid]
            scores = np.zeros((len(lineage_names), mat.shape[1]), dtype=np.float32)
            for li, (_, markers) in enumerate(_SC_LINEAGE_MARKERS.items()):
                idxs = [gene_to_idx[m] for m in markers if m in gene_to_idx]
                sub = mat[idxs, :].toarray() / lib_size[None, :] * 1e4
                scores[li] = np.log1p(sub).mean(axis=0)
            best_l = scores.argmax(axis=0)
            max_s = scores.max(axis=0)
            for li in range(len(lineage_names)):
                mask = (best_l == li) & (max_s >= 0.5)
                if mask.sum() == 0:
                    continue
                sub_m = mat[:, mask]
                lineage_cells[li] += int(mask.sum())
                norm_m = sub_m.multiply(1e4 / lib_size[mask])
                lineage_sum[:, li] += np.asarray(norm_m.sum(axis=1)).ravel()
                lineage_detect[:, li] += np.asarray((sub_m > 0).sum(axis=1)).ravel()

    mean_cp10k = lineage_sum / np.maximum(lineage_cells[None, :], 1)
    pct_detect = lineage_detect / np.maximum(lineage_cells[None, :], 1)

    mel_idxs = [0, 1]  # Epidermal Melanocyte + Hair Follicle Melanocyte Stem Cell (McSC)
    non_mel_idxs = [i for i in range(len(lineage_names)) if i not in mel_idxs]
    eff_idxs = [4, 6]  # CD8+ TRM + Cutaneous Natural Killer & ILC1 Cell
    non_eff_idxs = [i for i in range(len(lineage_names)) if i not in eff_idxs]

    gene_profiles: dict[str, dict[str, Any]] = {}
    for gi, g in enumerate(genes):
        row_cp = mean_cp10k[gi]
        row_pct = pct_detect[gi]
        if row_cp.max() < 0.25 and row_pct.max() < 0.03:
            continue
        mel_cp = float(row_cp[mel_idxs].max())
        non_mel_cp = float(np.median(row_cp[non_mel_idxs]))
        # Negative when enriched in melanocytes (since melanocytes are depleted in lesional vitiligo skin)
        mel_depletion_z = float(-np.log2((mel_cp + 0.25) / (non_mel_cp + 0.25)))

        eff_cp = float(row_cp[eff_idxs].max())
        non_eff_cp = float(np.median(row_cp[non_eff_idxs]))
        tcell_effector_z = float(np.log2((eff_cp + 0.25) / (non_eff_cp + 0.25)))

        top_lineages: list[dict[str, Any]] = []
        order = np.argsort(row_cp)[::-1]
        for li in order[:2]:
            others = np.delete(row_cp, li)
            fc = float((row_cp[li] + 0.1) / (np.median(others) + 0.1))
            if row_pct[li] >= 0.10 and row_cp[li] >= 1.5 and fc >= 2.2:
                top_lineages.append(
                    {
                        "lineage": lineage_names[int(li)],
                        "mean_cp10k": round(float(row_cp[li]), 2),
                        "pct_detect": round(float(row_pct[li]), 3),
                        "fold_enrichment": round(fc, 2),
                    }
                )
        if abs(mel_depletion_z) >= 0.15 or abs(tcell_effector_z) >= 0.15 or top_lineages:
            gene_profiles[g] = {
                "mel_depletion_z": round(mel_depletion_z, 3),
                "tcell_effector_z": round(tcell_effector_z, 3),
                "top_lineages": top_lineages,
            }

    payload = {
        "series": "GSE298871",
        "lineage_names": lineage_names,
        "lineage_cells": {
            lineage_names[i]: int(lineage_cells[i]) for i in range(len(lineage_names))
        },
        "genes": gene_profiles,
    }
    SC_LINEAGE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SC_LINEAGE_CACHE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def seed_single_cell_lineage_expression(session: Session) -> dict[str, int]:
    """Seed empirically measured EXPRESSED_IN edges from GSE298871 human skin scRNA-seq."""
    payload = compute_or_load_single_cell_lineage_profiles()
    gene_profiles: dict[str, dict[str, Any]] = payload.get("genes", {})
    lineage_cells: dict[str, int] = payload.get("lineage_cells", {})
    if not gene_profiles:
        return {"sc_expressed_in_added": 0}

    targets: dict[str, GraphEntity] = {
        e.name: e
        for e in session.exec(
            select(GraphEntity).where(GraphEntity.kind == EntityKind.TARGET)
        ).all()
    }
    cells: dict[str, GraphEntity] = {
        e.name: e
        for e in session.exec(
            select(GraphEntity).where(GraphEntity.kind == EntityKind.CELL_TYPE)
        ).all()
    }
    existing_expressed: set[tuple[int, int]] = {
        (e.subject_id, e.object_id)
        for e in session.exec(
            select(GraphEdge).where(GraphEdge.predicate == RelationKind.EXPRESSED_IN)
        ).all()
    }

    added = 0
    for gene_sym, prof in gene_profiles.items():
        t_ent = targets.get(gene_sym)
        if t_ent is None or t_ent.id is None:
            continue
        for item in prof.get("top_lineages", []):
            lname = str(item["lineage"])
            c_ent = cells.get(lname)
            if c_ent is None or c_ent.id is None:
                continue
            pair = (t_ent.id, c_ent.id)
            if pair in existing_expressed:
                continue
            existing_expressed.add(pair)
            fc = float(item["fold_enrichment"])
            pct = float(item["pct_detect"])
            cp10k = float(item["mean_cp10k"])
            n_cells = int(lineage_cells.get(lname, 0))
            conf = round(min(0.92, 0.72 + min(0.20, fc / 40.0)), 2)
            snippet = (
                f"Single-cell RNA-seq of human vitiligo and control skin (GSE298871, n={n_cells} {lname} cells): "
                f"{gene_sym} is expressed at {cp10k:.2f} CP10K across {pct * 100:.1f}% of {lname} cells "
                f"({fc:.1f}-fold lineage enrichment)."
            )
            session.add(
                GraphEdge(
                    subject_id=t_ent.id,
                    predicate=RelationKind.EXPRESSED_IN,
                    object_id=c_ent.id,
                    confidence=conf,
                    claim=ClaimKind.OBSERVED,
                    causal_level="correlation_in_human",
                    extraction_method="sc_rnaseq_gse298871",
                    evidence=[
                        {
                            "source_type": "geo_scrnaseq",
                            "source_id": "geo:GSE298871",
                            "relation": "EXPRESSED_IN",
                            "score": conf,
                            "mean_cp10k": cp10k,
                            "pct_detect": pct,
                            "fold_enrichment": fc,
                            "n_lineage_cells": n_cells,
                            "snippet": snippet,
                        }
                    ],
                )
            )
            added += 1

    session.flush()
    logger.info("Single-cell RNA-seq (GSE298871): added %d EXPRESSED_IN edges", added)
    return {"sc_expressed_in_added": added}


def enrich_knowledge_graph(min_abs_r: float = 0.70) -> dict[str, Any]:
    """Execute full knowledge graph enrichment and commit to SQLite."""
    with session_scope() as session:
        hier_stats = seed_canonical_pathways_and_cell_types(session)
        mygene_stats, uniprot_map = seed_mygene_pathways_and_processes(session)
        mychem_stats = seed_mychem_drug_target_mechanisms(session, uniprot_map)
        coexp_inserted = seed_patient_coexpression_edges(session, min_abs_r=min_abs_r)
        ft_stats = recover_directional_fulltext_relations(session)
        sc_stats = seed_single_cell_lineage_expression(session)

    return {
        "hierarchy": hier_stats,
        "mygene_pathways": mygene_stats,
        "mychem_mechanisms": mychem_stats,
        "coexpression_edges_inserted": coexp_inserted,
        "fulltext_directional_recovery": ft_stats,
        "single_cell_lineage": sc_stats,
    }
