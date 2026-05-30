"""Embedding generation and semantic search over the document store."""

from vitiligo.embed.cache import clear_embedding_index_cache, warm_embedding_index
from vitiligo.embed.encoder import DEFAULT_MODEL, Encoder, get_encoder
from vitiligo.embed.pipeline import EmbeddingStats, embed_documents
from vitiligo.embed.search import SearchHit, semantic_search

__all__ = [
    "DEFAULT_MODEL",
    "EmbeddingStats",
    "Encoder",
    "SearchHit",
    "clear_embedding_index_cache",
    "embed_documents",
    "get_encoder",
    "semantic_search",
    "warm_embedding_index",
]
