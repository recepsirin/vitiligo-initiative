"""Tests for splitting paper full text into embeddable passages."""

from __future__ import annotations

from itertools import pairwise

import pytest

from vitiligo.embed.chunking import Chunk, chunk_text, snippet

PAPER = """## Introduction

Vitiligo is an autoimmune disease of the skin. Melanocytes are destroyed by CD8 T cells.

Treatment options remain limited despite recent approvals.

## Results

F-VASI75 was reached by 14 of 38 patients at week 52. The placebo arm reached 6.8 per cent.

Response continued to rise after week 24 in both cohorts under study.
"""


def _texts(chunks: list[Chunk]) -> list[str]:
    return [c.text for c in chunks]


def test_empty_text_yields_nothing() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_offsets_point_back_at_the_source_text() -> None:
    """A passage is identified by position, so the text is never stored twice."""
    for chunk in chunk_text(PAPER, target_chars=120, min_chars=10):
        assert PAPER[chunk.char_start : chunk.char_end] == chunk.text


def test_sections_are_carried_through() -> None:
    chunks = chunk_text(PAPER, target_chars=120, min_chars=10)
    sections = {c.section for c in chunks}
    assert sections == {"Introduction", "Results"}


def test_a_passage_never_spans_two_sections() -> None:
    """Introduction text appearing under a Results hit would be a false quote."""
    for chunk in chunk_text(PAPER, target_chars=4000, min_chars=10):
        body = PAPER[chunk.char_start : chunk.char_end]
        assert "## " not in body


def test_short_text_without_headings_is_one_passage() -> None:
    chunks = chunk_text("A single short paragraph about melanocytes.", min_chars=5)
    assert len(chunks) == 1
    assert chunks[0].section is None
    assert chunks[0].index == 0


def test_chunks_are_numbered_from_zero_without_gaps() -> None:
    chunks = chunk_text(PAPER, target_chars=100, min_chars=10)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_paragraphs_are_packed_up_to_the_target() -> None:
    """Two short paragraphs belong together; packing avoids thousands of tiny vectors."""
    text = "## Results\n\nFirst short paragraph.\n\nSecond short paragraph.\n"
    [chunk] = chunk_text(text, target_chars=900, min_chars=5)
    assert "First short paragraph." in chunk.text
    assert "Second short paragraph." in chunk.text


def test_a_long_paragraph_is_split_at_sentence_ends() -> None:
    sentences = [f"Sentence number {i} describes a finding in detail." for i in range(40)]
    text = "## Results\n\n" + " ".join(sentences) + "\n"
    chunks = chunk_text(text, target_chars=300, overlap_chars=0, min_chars=10)
    assert len(chunks) > 1
    # Every passage should start at a sentence beginning, not mid-word.
    for chunk in chunks:
        assert chunk.text.startswith("Sentence number")


def test_a_paragraph_with_no_sentence_breaks_is_still_split() -> None:
    """A wall of text without punctuation must not produce one giant passage."""
    text = "## Methods\n\n" + ("abcdefghij" * 300) + "\n"
    chunks = chunk_text(text, target_chars=400, overlap_chars=0, min_chars=10)
    assert len(chunks) > 1
    assert all(len(c.text) <= 400 for c in chunks)


def test_passages_overlap_so_a_fact_at_a_seam_survives() -> None:
    sentences = [f"Finding {i} was recorded at week {i}." for i in range(30)]
    text = "## Results\n\n" + " ".join(sentences) + "\n"
    with_overlap = chunk_text(text, target_chars=300, overlap_chars=120, min_chars=10)
    without = chunk_text(text, target_chars=300, overlap_chars=0, min_chars=10)
    assert len(with_overlap) >= len(without)
    joined = "".join(c.text for c in with_overlap)
    assert len(joined) > len(text.replace("## Results", "").strip())


def test_tiny_trailing_passages_are_dropped() -> None:
    text = "## Results\n\n" + ("A sentence of reasonable length. " * 30) + "\n\nok\n"
    chunks = chunk_text(text, target_chars=400, min_chars=100)
    assert all(len(c.text) >= 100 for c in chunks)


def test_a_document_shorter_than_the_minimum_is_still_kept() -> None:
    """Dropping everything would make a short paper unsearchable."""
    chunks = chunk_text("Brief note.", min_chars=500)
    assert len(chunks) == 1


def test_text_before_the_first_heading_is_not_lost() -> None:
    text = "Preamble sentence that matters.\n\n## Results\n\nThe finding was significant.\n"
    chunks = chunk_text(text, target_chars=200, min_chars=5)
    assert any(c.section is None and "Preamble" in c.text for c in chunks)
    assert any(c.section == "Results" for c in chunks)


def test_realistic_paper_produces_a_sane_number_of_passages() -> None:
    body = "## Results\n\n" + "\n\n".join(
        f"Paragraph {i} reports an outcome measured at week {i} in the trial cohort." * 3
        for i in range(40)
    )
    chunks = chunk_text(body)
    assert 5 <= len(chunks) <= 80
    assert all(len(c.text) <= 1200 for c in chunks)


@pytest.mark.parametrize("limit", [40, 120, 320])
def test_snippet_is_trimmed_and_whitespace_collapsed(limit: int) -> None:
    text = "## Results\n\nThe   response    rate\nwas   high across every cohort studied here.\n"
    out = snippet(text, 0, len(text), limit=limit)
    assert "  " not in out
    assert len(out) <= limit + 1  # the ellipsis
    if len(out) > limit:
        assert out.endswith("…")


def test_snippet_of_a_short_passage_is_returned_whole() -> None:
    assert snippet("Short finding.", 0, 14, limit=100) == "Short finding."


def test_an_overlap_tail_never_becomes_a_passage_of_its_own() -> None:
    """Emitting the carried-over tail alone would store a near-duplicate vector."""
    paragraphs = [f"Paragraph {i} " + "word " * 50 for i in range(6)]
    text = "## Results\n\n" + "\n\n".join(paragraphs)
    chunks = chunk_text(text, target_chars=300, overlap_chars=150, min_chars=10)
    for earlier, later in pairwise(chunks):
        assert later.text not in earlier.text


def test_a_passage_does_not_begin_with_half_a_word() -> None:
    paragraphs = [f"Paragraph {i} reports findings " + "word " * 40 for i in range(5)]
    text = "## Results\n\n" + "\n\n".join(paragraphs)
    for chunk in chunk_text(text, target_chars=320, overlap_chars=150, min_chars=10):
        preceding = text[: chunk.char_start]
        assert not preceding or preceding[-1].isspace() or chunk.char_start == 0
