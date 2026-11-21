"""Genes measured in vitiligo skin, as the Space's gene explorer shows them.

Read from the knowledge-graph release (``data/release/knowledge-graph``, the files
published on Hugging Face), so the page can be rebuilt from public data alone:

- **Differential expression**: each gene a GEO cohort found expressed differently in
  lesional skin (the release's ``expression`` evidence: limma's moderated t, FDR below
  5% and a twofold change), with every cohort's fold change, p, FDR and sample sizes,
  and how many cohorts agree. On 2026-11-21: 1,484 genes, 73 agreeing in two or more.
- **Co-expression** across 105 skin punch biopsies (GSE311770): gene pairs whose
  expression correlates at |Pearson r| >= 0.70, p < 1e-5. 8,367 pairs among 1,266 genes.
- **Single-cell expression** (GSE298871): the skin cell types a gene is enriched in,
  with its mean expression and the share of cells detecting it. 505 genes.
- **GWAS**: associations in the Space's pipeline file whose mapped or reported genes
  name the gene.
- **The relapse panel**: the 17 genes of the sealed S_TRM signature, marked as such.

A gene is listed if it has any of these. An expression difference is an association,
not a cause: most of the strongest are melanocyte genes that a lesion has lost.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

GENE_KINDS = frozenset({"target", "biomarker"})
COEXPRESSION_METHOD = "geo_punch_biopsies_gse311770"
SINGLE_CELL_METHOD = "sc_rnaseq_gse298871"
EXPRESSION_FIELDS = ("contrast", "direction", "log2fc", "p", "fdr", "n_case", "n_control", "paired")
# "HLA-DRB1 - HLA-DQA1" is a variant between two genes; lists use commas or semicolons.
_GENE_LIST = re.compile(r"\s+-\s+|[,;/]")
# Placeholders the catalog writes where a gene would be: "NR" in 3 associations,
# "Intergenic" in 1 (2026-11-21).
_NOT_A_GENE = frozenset({"nr", "intergenic"})


def _details(evidence: Mapping[str, Any]) -> dict[str, Any]:
    raw = evidence.get("details")
    loaded = json.loads(raw) if isinstance(raw, str) and raw else raw
    return loaded if isinstance(loaded, dict) else {}


def gwas_genes(association: Mapping[str, Any]) -> set[str]:
    """The gene symbols an association's mapped and reported genes name."""
    names = f"{association.get('mapped_gene') or ''},{association.get('reported_genes') or ''}"
    parts = (part.strip() for part in _GENE_LIST.split(names))
    return {part for part in parts if part and part.lower() not in _NOT_A_GENE}


def expression_results(
    relations: Mapping[str, Mapping[str, Any]],
    evidence: Iterable[Mapping[str, Any]],
    genes: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Each gene's differential-expression results, one per cohort, wherever the evidence sits."""
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        if row.get("source_kind") != "expression":
            continue
        relation = relations.get(str(row.get("relation_id")))
        if not relation:
            continue
        details = _details(row)
        result = {"source": row.get("source")} | {
            k: details[k] for k in EXPRESSION_FIELDS if details.get(k) is not None
        }
        result["agreeing"] = details.get("cohorts_agreeing") or 1
        for side in (str(relation["subject_id"]), str(relation["object_id"])):
            if side in genes:
                found[side].append(result)
    return found


def coexpression_pairs(
    relations: Mapping[str, Mapping[str, Any]], evidence: Iterable[Mapping[str, Any]]
) -> list[tuple[str, str, float]]:
    """Gene pairs co-expressed across the GSE311770 biopsies, with their Pearson r."""
    pairs = []
    for row in evidence:
        relation = relations.get(str(row.get("relation_id")))
        if not relation or relation.get("extraction_method") != COEXPRESSION_METHOD:
            continue
        r = _details(row).get("pearson_r")
        if isinstance(r, int | float):
            pairs.append((str(relation["subject_id"]), str(relation["object_id"]), float(r)))
    return pairs


def cell_expression(
    relations: Mapping[str, Mapping[str, Any]],
    evidence: Iterable[Mapping[str, Any]],
    names: Mapping[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """Each gene's enriched skin cell types in GSE298871, most enriched first."""
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        relation = relations.get(str(row.get("relation_id")))
        if not relation or relation.get("extraction_method") != SINGLE_CELL_METHOD:
            continue
        d = _details(row)
        found[str(relation["subject_id"])].append(
            {
                "cell": names.get(str(relation["object_id"]), str(relation["object_id"])),
                "mean_cp10k": d.get("mean_cp10k"),
                "pct_detect": d.get("pct_detect"),
                "enrichment": d.get("fold_enrichment"),
            }
        )
    for cells in found.values():
        cells.sort(key=lambda c: -(c["enrichment"] or 0))
    return found


def gene_table(
    entities: Iterable[Mapping[str, Any]],
    relations: Iterable[Mapping[str, Any]],
    evidence: Iterable[Mapping[str, Any]],
    gwas: Iterable[Mapping[str, Any]],
    panels: Mapping[str, Iterable[str]],
) -> dict[str, Any]:
    """The genes the page lists, keyed by symbol, and the co-expression pairs between them."""
    ents = {str(e["id"]): e for e in entities}
    genes = {i: e for i, e in ents.items() if e.get("kind") in GENE_KINDS}
    names = {i: str(e.get("name")) for i, e in ents.items()}
    rels = {str(r["id"]): r for r in relations}
    rows = list(evidence)

    expression = expression_results(rels, rows, genes)
    pairs = coexpression_pairs(rels, rows)
    cells = cell_expression(rels, rows, names)
    panel_of = {symbol: role for role, symbols in panels.items() for symbol in symbols}
    by_symbol: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for association in gwas:
        for symbol in gwas_genes(association):
            by_symbol[symbol].append(association)

    # Entities that share a symbol are one gene on the page.
    symbol_ids: dict[str, list[str]] = defaultdict(list)
    for gid in genes:
        symbol_ids[names[gid]].append(gid)
    measured = {
        names[g]
        for g in set(expression) | set(cells) | {g for p in pairs for g in p[:2]}
        if g in genes
    }
    symbols = sorted(measured | set(panel_of) | set(by_symbol))
    position = {symbol: n for n, symbol in enumerate(symbols)}

    table = []
    for symbol in symbols:
        ids = symbol_ids.get(symbol, [])
        results = sorted(
            (r for g in ids for r in expression.get(g, [])), key=lambda r: r.get("fdr") or 1.0
        )
        entrez = next(
            (
                (genes[g].get("external_ids") or {}).get("entrez")
                for g in ids
                if (genes[g].get("external_ids") or {}).get("entrez")
            ),
            None,
        )
        row = {
            "symbol": symbol,
            "entrez": entrez,
            "expression": results,
            "agreeing": max((r["agreeing"] for r in results), default=0),
            "cells": sorted(
                (c for g in ids for c in cells.get(g, [])), key=lambda c: -(c["enrichment"] or 0)
            ),
            "gwas": [
                {
                    k: a.get(k)
                    for k in ("variant", "p_value", "or_or_beta", "ci", "study", "pubmed_id")
                }
                for a in by_symbol.get(symbol, [])
            ],
            "panel": panel_of.get(symbol),
        }
        table.append({k: v for k, v in row.items() if v not in (None, [])})
    return {
        "genes": table,
        "pairs": sorted(
            [position[names[a]], position[names[b]], round(r, 3)]
            for a, b, r in pairs
            if names.get(a) in position and names.get(b) in position
        ),
    }
