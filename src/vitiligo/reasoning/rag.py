"""Retrieval-augmented generation with citations.

The output is structured: every claim must be tied to one or more
retrieved papers, surfaced as numbered citations the UI renders inline.
"""

from __future__ import annotations

from dataclasses import dataclass

from vitiligo.embed import semantic_search
from vitiligo.embed.search import SearchHit
from vitiligo.logging import get_logger
from vitiligo.reasoning.llm import LLMClient

logger = get_logger(__name__)


@dataclass
class Citation:
    """A single retrieved paper used as evidence."""

    index: int
    source: str
    source_id: str
    title: str
    journal: str | None
    year: int | None
    doi: str | None
    score: float


@dataclass
class RagAnswer:
    question: str
    answer: str
    citations: list[Citation]
    model: str


_SYSTEM_PROMPT = """You are a careful biomedical research assistant for the Vitiligo Initiative.

Your job is to answer questions about vitiligo using ONLY the retrieved papers provided in the user message. Follow these rules strictly:

1. Cite every factual claim using bracketed numeric citations like [1], [2], or [1, 3]. Citation numbers MUST refer to the papers listed in the user message.
2. If the retrieved papers do not contain enough information to answer, say so explicitly. Do not invent facts, drugs, mechanisms, or trial results.
3. Distinguish strength of evidence (e.g. randomized trial vs. mouse model vs. case report) when the abstract makes it clear.
4. Be concise and structured. Prefer short paragraphs and tight bullet points over flowery prose.
5. Never use marketing language ("revolutionary", "breakthrough"). Stay scientific.
6. Surface uncertainty and disagreement when the literature is split.
7. Do not make recommendations to individual patients; answer at the level of evidence and clinical context.
"""


def ask_with_citations(
    question: str,
    top_k: int = 8,
    llm: LLMClient | None = None,
) -> RagAnswer:
    """Run retrieval over the embedded corpus, then call the LLM with the hits as context."""
    hits = semantic_search(query=question, top_k=top_k)
    if not hits:
        raise RuntimeError(
            "No embeddings stored yet. Run `vitiligo embed run` to index the corpus first."
        )

    citations = [_hit_to_citation(idx + 1, hit) for idx, hit in enumerate(hits)]
    user_prompt = _build_user_prompt(question, hits)

    client = llm or LLMClient()
    response = client.complete(system=_SYSTEM_PROMPT, user=user_prompt, max_tokens=1500)
    return RagAnswer(
        question=question,
        answer=response.text,
        citations=citations,
        model=response.model,
    )


def _build_user_prompt(question: str, hits: list[SearchHit]) -> str:
    lines: list[str] = ["RETRIEVED PAPERS:", ""]
    for idx, hit in enumerate(hits, start=1):
        doc = hit.document
        meta_bits: list[str] = []
        if doc.journal:
            meta_bits.append(doc.journal)
        if doc.year is not None:
            meta_bits.append(str(doc.year))
        if doc.doi:
            meta_bits.append(f"doi:{doc.doi}")
        meta = " | ".join(meta_bits) if meta_bits else ""

        lines.append(f"[{idx}] {doc.title or '(no title)'}")
        if meta:
            lines.append(f"    {meta}")
        if doc.abstract:
            abstract = doc.abstract.strip()
            if len(abstract) > 1500:
                abstract = abstract[:1500] + " ..."
            lines.append(f"    ABSTRACT: {abstract}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"QUESTION: {question}")
    lines.append("")
    lines.append(
        "Answer the question using only the retrieved papers above. "
        "Cite with bracketed numbers like [1] or [2, 5]. If the papers are insufficient, say so."
    )
    return "\n".join(lines)


def _hit_to_citation(index: int, hit: SearchHit) -> Citation:
    doc = hit.document
    return Citation(
        index=index,
        source=doc.source.value,
        source_id=doc.source_id,
        title=doc.title or "(no title)",
        journal=doc.journal,
        year=doc.year,
        doi=doc.doi,
        score=hit.score,
    )
