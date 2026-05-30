"""Orchestrate knowledge graph seeding and optional LLM extraction."""

from __future__ import annotations

from dataclasses import dataclass

from vitiligo.graph.extract import GraphExtractStats, extract_graph_from_documents
from vitiligo.graph.seed import GraphSeedStats, seed_graph_from_structured_sources
from vitiligo.reasoning.llm import LLMClient
from vitiligo.storage import init_db


@dataclass(frozen=True)
class GraphBuildStats:
    seed: GraphSeedStats | None
    extract: GraphExtractStats | None


def run_graph_build(
    *,
    seed: bool = True,
    extract: bool = False,
    extract_limit: int = 50,
    llm: LLMClient | None = None,
) -> GraphBuildStats:
    """Seed structured sources and optionally run LLM extraction."""
    init_db()
    seed_stats: GraphSeedStats | None = None
    extract_stats: GraphExtractStats | None = None

    if seed:
        seed_stats = seed_graph_from_structured_sources()
    if extract:
        extract_stats = extract_graph_from_documents(limit=extract_limit, llm=llm)

    return GraphBuildStats(seed=seed_stats, extract=extract_stats)
