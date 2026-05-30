"""Offline tests for embedding vector serialization (no model load)."""

from __future__ import annotations

import numpy as np

from vitiligo.embed.encoder import Encoder


def test_roundtrip_vector_bytes() -> None:
    rng = np.random.default_rng(42)
    vec = rng.standard_normal(384).astype(np.float32)

    blob = Encoder.vector_to_bytes(vec)
    restored = Encoder.vector_from_bytes(blob, dim=384)

    assert restored.shape == (384,)
    assert restored.dtype == np.float32
    np.testing.assert_array_equal(restored, vec)


def test_vector_bytes_size_matches_dim() -> None:
    vec = np.zeros(768, dtype=np.float32)
    blob = Encoder.vector_to_bytes(vec)
    # 4 bytes per float32
    assert len(blob) == 768 * 4
