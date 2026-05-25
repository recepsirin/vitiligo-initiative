"""Embedding generation and semantic search over the document store."""

from vitiligo.embed.encoder import DEFAULT_MODEL, Encoder
from vitiligo.embed.pipeline import EmbeddingStats, embed_documents
from vitiligo.embed.search import SearchHit, semantic_search

__all__ = [
    "DEFAULT_MODEL",
    "EmbeddingStats",
    "Encoder",
    "SearchHit",
    "embed_documents",
    "semantic_search",
]
