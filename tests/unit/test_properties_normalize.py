"""Property-based tests for normalization helpers."""

from __future__ import annotations

import re

from hypothesis import given
from hypothesis import strategies as st

from vitiligo.graph.normalize import normalize_entity_key
from vitiligo.reports.candidates import normalize_drug_token

_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")


@given(st.text(min_size=0, max_size=200))
def test_normalize_entity_key_is_idempotent(name: str) -> None:
    once = normalize_entity_key(name)
    assert normalize_entity_key(once) == once


@given(st.text(min_size=0, max_size=200))
def test_normalize_entity_key_shape(name: str) -> None:
    key = normalize_entity_key(name)
    assert len(key) <= 120
    assert key == "unknown" or _KEY_PATTERN.fullmatch(key)


@given(st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
def test_normalize_entity_key_ignores_outer_whitespace(name: str) -> None:
    assert normalize_entity_key(name) == normalize_entity_key(name.strip())


@given(st.text(min_size=0, max_size=200))
def test_normalize_drug_token_is_lowercase(name: str) -> None:
    token = normalize_drug_token(name)
    assert token == token.lower()


@given(
    st.text(
        min_size=1,
        max_size=80,
        alphabet=st.characters(
            whitelist_categories=("L", "N"), min_codepoint=97, max_codepoint=122
        ),
    )
)
def test_normalize_drug_token_idempotent_on_plain_tokens(word: str) -> None:
    """Single lowercase alnum tokens should stabilize."""
    assume_word = word if len(word) >= 4 else word * 2
    token = normalize_drug_token(assume_word)
    assert normalize_drug_token(token) == token
