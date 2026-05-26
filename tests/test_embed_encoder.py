"""Tests for embedding encoder lifecycle."""

from __future__ import annotations

from vitiligo.embed.encoder import DEFAULT_MODEL, get_encoder


def test_get_encoder_returns_process_singleton() -> None:
    first = get_encoder()
    second = get_encoder()
    assert first is second
    assert first.model_name == DEFAULT_MODEL


def test_get_encoder_distinct_models() -> None:
    default = get_encoder(DEFAULT_MODEL)
    other = get_encoder("other-model-name")
    assert default is not other
