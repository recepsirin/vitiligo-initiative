"""Graph edges built from measurements, not from database listings.

``seed.py`` builds the graph from what Open Targets, DrugBank and the trial
registries *state*: a drug is listed against a disease, a trial is registered
for it. Useful, and every edge of it is an assertion by that source. Nothing
in it was measured by anyone whose numbers we hold.

This module adds the other kind. Three sources in the corpus carry real
measurements with a cohort and a number behind them:

- **Human genetics.** A GWAS association is a variant's frequency difference
  between cases and controls, with a p-value and a named cohort. Genotype is
  fixed at conception, so the association cannot run the other way.
- **Trial results.** A posted responder rate is what happened when people
  took a drug: an intervention effect measured in humans, the strongest rung
  of the ladder.
- **Mechanistic hypotheses.** Each record in ``curation/mechanisms.json``
  carries its own evidence on that ladder, already gated by
  ``vitiligo mechanism verify``.

Every edge written here is ``ClaimKind.OBSERVED`` and carries the rung it
reached, so a reader can tell a measured relation from a listed one without
reading the predicate and guessing.

The node types come with it: trial outcomes (F-VASI75 and the rest), the
phenotypes and cell types a mechanism names, and the pathways it runs
through — none of which the structured seed could express.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.logging import get_logger
from vitiligo.mechanisms.schema import CURATION_PATH, Mechanism
from vitiligo.mechanisms.schema import load as load_mechanisms
from vitiligo.storage import GeneticAssociation, init_db, session_scope
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEntity, RelationKind

if TYPE_CHECKING:  # reports imports graph, so this one stays a type-only import
    from vitiligo.reports.jak_arms import ArmEndpointRow

logger = get_logger(__name__)

DISEASE_NAME = "Vitiligo"
# Below this, an association is not reliably distinguishable from noise.
GENOME_WIDE = 5e-8
# The Catalog separates two flanking genes with a spaced hyphen
# ("HLA-DRB1 - HLA-DQA1") and several genes with commas ("GZMB, GZMH-AS1").
# A hyphen inside a symbol is part of the name: HLA-DRB1, MIR4435-2HG,
# TAGAP-AS1. Splitting on a bare hyphen invents genes that do not exist.
_GENE_SPLIT = re.compile(r"\s+-\s+|\s*,\s*")


@dataclass
class EvidenceSeedStats:
    """What a run added."""

    genetic_edges: int = 0
    outcome_edges: int = 0
    mechanism_edges: int = 0
    entities: int = 0

    @property
    def total_edges(self) -> int:
        return self.genetic_edges + self.outcome_edges + self.mechanism_edges


def split_genes(mapped_gene: str | None) -> list[str]:
    """Gene symbols out of a Catalog mapping, which may name two flanking genes."""
    if not mapped_gene:
        return []
    parts = [p.strip() for p in _GENE_SPLIT.split(mapped_gene)]
    # Keep symbol-shaped tokens; the Catalog also writes free text like "intergenic".
    return [p for p in parts if p and re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{1,19}", p, re.IGNORECASE)]


def _disease(session: Session) -> GraphEntity:
    return upsert_entity(
        session,
        kind=EntityKind.DISEASE,
        name=DISEASE_NAME,
        aliases=["vitiligo"],
        external_ids={"efo": "EFO_0004208"},
    )


def seed_genetics(session: Session, disease: GraphEntity) -> tuple[int, int]:
    """Gene-disease edges from genome-wide significant GWAS associations.

    One edge per gene, carrying the strongest association found for it. The
    Catalog's mapped gene is what sits near the variant, which is not proof
    that this gene's function matters; the edge says ``associated_with`` and
    nothing stronger.
    """
    rows = [
        r
        for r in session.exec(select(GeneticAssociation)).all()
        if r.p_value is not None and r.p_value < GENOME_WIDE
    ]
    strongest: dict[str, GeneticAssociation] = {}
    for row in rows:
        for gene in split_genes(row.mapped_gene):
            held = strongest.get(gene)
            if held is None or (row.p_value or 1) < (held.p_value or 1):
                strongest[gene] = row

    edges = entities = 0
    for gene, row in sorted(strongest.items()):
        target = upsert_entity(
            session, kind=EntityKind.TARGET, name=gene, external_ids={"gwas_variant": row.variant}
        )
        entities += 1
        _, inserted = upsert_edge(
            session,
            subject=target,
            predicate=RelationKind.ASSOCIATED_WITH,
            obj=disease,
            confidence=0.9,
            extraction_method="gwas",
            claim=ClaimKind.OBSERVED,
            causal_level="human_genetics",
            evidence={
                "source_type": "gwas",
                "source_id": f"gwas:{row.study_accession}",
                "variant": row.variant,
                "p_value": row.p_value_text,
                "odds_ratio_or_beta": row.odds_ratio_or_beta,
                "pubmed_id": row.pubmed_id,
                "cohort": row.initial_sample,
            },
        )
        edges += int(inserted)
    return edges, entities


def seed_trial_outcomes(session: Session, rows: Sequence[ArmEndpointRow]) -> tuple[int, int]:
    """Drug-outcome edges from posted responder rates.

    ``rows`` are harmonized arm-table rows. Only active arms with a reported
    responder count become edges: a measured effect in people, which is the
    top of the ladder. The arm's own numbers travel with the edge, so the
    claim can be checked against the registry.
    """
    edges = entities = 0
    best: dict[tuple[str, str], ArmEndpointRow] = {}
    for row in rows:
        if row.arm_role != "active" or not row.arm_agent or row.responders is None:
            continue
        if not row.n_analyzed or row.percent is None or not row.endpoint:
            continue
        key = (row.arm_agent.lower(), row.endpoint)
        held = best.get(key)
        # Keep the largest arm for each drug and endpoint: the firmest number.
        if held is None or (row.n_analyzed or 0) > (held.n_analyzed or 0):
            best[key] = row

    for (agent, endpoint), row in sorted(best.items()):
        drug = upsert_entity(session, kind=EntityKind.DRUG, name=agent)
        outcome = upsert_entity(
            session,
            kind=EntityKind.OUTCOME,
            name=endpoint,
            aliases=[f"{row.instrument} {row.threshold}% improvement"],
        )
        entities += 2
        _, inserted = upsert_edge(
            session,
            subject=drug,
            predicate=RelationKind.CHANGES,
            obj=outcome,
            confidence=0.9,
            extraction_method="trial_result",
            claim=ClaimKind.OBSERVED,
            causal_level="perturbation_in_human",
            evidence={
                "source_type": "trial_result",
                "source_id": f"trial:{row.source_id}",
                "arm": row.arm_label,
                "week": row.week,
                "responders": row.responders,
                "n_analyzed": row.n_analyzed,
                "percent": row.percent,
            },
        )
        edges += int(inserted)
    return edges, entities


def seed_mechanisms(
    session: Session, disease: GraphEntity, mechanisms: list[Mechanism]
) -> tuple[int, int]:
    """Nodes and edges for each mechanistic hypothesis.

    The hypothesis itself becomes a node joined to the disease at whatever
    rung its supporting evidence actually reaches — computed in the record,
    never asserted here. Its context (the cell type it concerns, the tissue
    state, the pathways upstream of it) becomes the node types the structured
    seed had no way to express. Those context edges are ``asserted``: they
    are the curator's framing of the claim, not a measurement.
    """
    edges = entities = 0
    for mechanism in mechanisms:
        node = upsert_entity(
            session,
            kind=EntityKind.MECHANISM,
            name=mechanism.title,
            aliases=[mechanism.id],
            external_ids={"mechanism_id": mechanism.id},
        )
        entities += 1
        support = mechanism.causal_support
        citations = [
            {"source_type": "mechanism", "source_id": e.ref, "shows": e.shows[:300]}
            for e in mechanism.supporting()
        ]
        _, inserted = upsert_edge(
            session,
            subject=node,
            predicate=RelationKind.ASSOCIATED_WITH,
            obj=disease,
            confidence=0.6,
            extraction_method="mechanism_record",
            claim=ClaimKind.OBSERVED if support != "none" else ClaimKind.ASSERTED,
            causal_level=None if support == "none" else support,
            evidence=citations[0]
            if citations
            else {"source_type": "mechanism", "source_id": mechanism.id},
        )
        edges += int(inserted)

        for kind, name, predicate in (
            (EntityKind.CELL_TYPE, mechanism.context.cell_type, RelationKind.OCCURS_IN),
            (EntityKind.PHENOTYPE, mechanism.context.tissue, RelationKind.OCCURS_IN),
        ):
            if not name.strip():
                continue
            other = upsert_entity(session, kind=kind, name=name)
            entities += 1
            _, ins = upsert_edge(
                session,
                subject=node,
                predicate=predicate,
                obj=other,
                confidence=0.7,
                extraction_method="mechanism_record",
                claim=ClaimKind.ASSERTED,
                evidence={"source_type": "mechanism", "source_id": mechanism.id},
            )
            edges += int(ins)

        for pathway in mechanism.upstream:
            if not pathway.strip():
                continue
            node_pathway = upsert_entity(session, kind=EntityKind.PATHWAY, name=pathway)
            entities += 1
            _, ins = upsert_edge(
                session,
                subject=node_pathway,
                predicate=RelationKind.EXPRESSED_IN,
                obj=node,
                confidence=0.6,
                extraction_method="mechanism_record",
                claim=ClaimKind.ASSERTED,
                evidence={"source_type": "mechanism", "source_id": mechanism.id},
            )
            edges += int(ins)
    return edges, entities


def seed_graph_from_evidence(
    mechanisms_path: Path = CURATION_PATH,
    *,
    with_trial_outcomes: bool = True,
) -> EvidenceSeedStats:
    """Add every edge the corpus can support with a measurement."""
    init_db()
    stats = EvidenceSeedStats()
    rows: list[ArmEndpointRow] = []
    if with_trial_outcomes:
        from vitiligo.reports import build_jak_atlas
        from vitiligo.reports.jak_arms import harmonize_arms

        rows = harmonize_arms(build_jak_atlas())

    mechanisms = load_mechanisms(mechanisms_path) if mechanisms_path.is_file() else []

    with session_scope() as session:
        disease = _disease(session)
        stats.genetic_edges, genetic_entities = seed_genetics(session, disease)
        stats.outcome_edges, outcome_entities = seed_trial_outcomes(session, rows)
        stats.mechanism_edges, mechanism_entities = seed_mechanisms(session, disease, mechanisms)
        stats.entities = genetic_entities + outcome_entities + mechanism_entities
        session.commit()

    logger.info(
        "Evidence seed: %d genetic, %d outcome, %d mechanism edge(s)",
        stats.genetic_edges,
        stats.outcome_edges,
        stats.mechanism_edges,
    )
    return stats
