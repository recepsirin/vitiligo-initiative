"""Thin wrapper around fastembed for batched, normalized embeddings.

We use fastembed (ONNX-runtime under the hood) so we don't pull torch
into the install. The default model is `BAAI/bge-small-en-v1.5` — a
solid baseline at 384 dims. Swap in domain-specific models (e.g. a
PubMedBERT-tuned encoder) later by passing `model_name`.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from vitiligo.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

_encoders: dict[str, Encoder] = {}


def get_encoder(model_name: str = DEFAULT_MODEL) -> Encoder:
    """Return a process-wide cached ``Encoder`` for ``model_name``."""
    encoder = _encoders.get(model_name)
    if encoder is None:
        encoder = Encoder(model_name=model_name)
        _encoders[model_name] = encoder
    return encoder


class Encoder:
    """Lazy-loading text encoder.

    The underlying fastembed model is downloaded on first use and cached
    on disk by fastembed itself.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._model: object | None = None
        self._dim: int | None = None

    def _load(self) -> None:
        if self._model is not None:
            return
        logger.info("Loading embedding model: %s", self.model_name)
        # Imported lazily so the rest of the package can be used without fastembed loaded.
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=self.model_name)

        # Probe dim with a tiny throwaway embedding; cheaper than reading model card.
        sample = next(self._model.embed(["dimension probe"]))
        self._dim = int(np.asarray(sample).shape[-1])
        logger.info("Embedding model ready (dim=%d)", self._dim)

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._load()
        assert self._dim is not None
        return self._dim

    def encode(self, texts: Iterable[str], batch_size: int = 32) -> np.ndarray:
        """Encode an iterable of texts into a (N, dim) float32 matrix.

        Vectors are L2-normalized so cosine similarity reduces to dot product.
        """
        self._load()
        assert self._model is not None

        text_list = list(texts)
        if not text_list:
            return np.zeros((0, self.dim), dtype=np.float32)

        # fastembed yields one vector at a time; batch_size controls its internal batching.
        vectors = list(self._model.embed(text_list, batch_size=batch_size))
        matrix = np.asarray(vectors, dtype=np.float32)
        # Normalize for cosine via dot product.
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    @staticmethod
    def vector_to_bytes(vec: np.ndarray) -> bytes:
        return np.ascontiguousarray(vec, dtype=np.float32).tobytes()

    @staticmethod
    def vector_from_bytes(blob: bytes, dim: int) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32, count=dim)
