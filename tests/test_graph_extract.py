"""Tests for LLM graph extraction JSON parsing."""

from __future__ import annotations

from vitiligo.graph.extract import parse_llm_extraction


def test_parse_llm_extraction_plain_json() -> None:
    text = """
    {
      "entities": [{"kind": "drug", "name": "Ruxolitinib"}],
      "relations": [
        {"subject": "Ruxolitinib", "predicate": "treats", "object": "Vitiligo", "confidence": 0.9}
      ]
    }
    """
    entities, relations = parse_llm_extraction(text)
    assert len(entities) == 1
    assert entities[0]["name"] == "Ruxolitinib"
    assert len(relations) == 1
    assert relations[0]["predicate"] == "treats"


def test_parse_llm_extraction_fenced_json() -> None:
    text = """```json
{"entities": [], "relations": []}
```"""
    entities, relations = parse_llm_extraction(text)
    assert entities == []
    assert relations == []


def test_parse_llm_extraction_invalid() -> None:
    entities, relations = parse_llm_extraction("not json")
    assert entities == []
    assert relations == []
