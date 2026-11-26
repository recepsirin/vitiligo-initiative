"""The GNN screens' Markdown reports say what the screens returned, and only that."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import torch  # noqa: F401
    import torch_geometric  # noqa: F401

    from vitiligo.gnn.reverse_screen import (
        TargetScreenHit,
        TargetScreenResult,
        _render_reverse_screen_md,
    )
    from vitiligo.gnn.synergy import SynergyPairResult, _render_synergy_markdown

    HAS_GNN_DEPS = True
except ImportError:
    HAS_GNN_DEPS = False

pytestmark = pytest.mark.skipif(
    not HAS_GNN_DEPS, reason="torch and torch_geometric are required for GNN tests"
)


def _hit(rank: int, name: str, score: float) -> TargetScreenHit:
    return TargetScreenHit(
        rank=rank,
        drug_name=name,
        canonical_name=name.lower(),
        score=score,
        mechanism_class="kinase inhibitor",
        safety_tier="standard",
        is_cytotoxic=False,
    )


def test_the_reverse_screen_summary_names_only_drugs_the_screen_returned(tmp_path: Path) -> None:
    results = {
        "INHIBITS_PDE4B": TargetScreenResult(
            target_name="PDE4B",
            relation="INHIBITS",
            pillar="Pillar 3: Barrier Reversal",
            biological_function="Hydrolyzes cAMP.",
            hits=[_hit(1, "cobimetinib", 4.18), _hit(2, "dabrafenib", 4.05)],
        )
    }
    out = tmp_path / "reverse.md"
    _render_reverse_screen_md(results, out)
    text = out.read_text(encoding="utf-8")
    summary = text.split("## Summary", 1)[1].split("---", 1)[0]
    assert "**cobimetinib** (`4.18`)" in summary
    # The score is an uncalibrated inner product: never shown as a percentage.
    assert "%" not in text and "Probability" not in text
    assert "| 1 | **cobimetinib** | `4.180` | kinase inhibitor | standard |" in text
    # Drugs the screen did not return must not appear anywhere in the report.
    for absent in ("Roflumilast", "Crisaborole", "Zasocitinib", "Ruxolitinib"):
        assert absent not in text


def test_the_synergy_summary_quotes_no_clinical_figures(tmp_path: Path) -> None:
    pair = SynergyPairResult(
        rank=1,
        drug_a="cyclosporine",
        drug_b="Pioglitazone",
        drug_a_pillar="Pillar 1",
        drug_b_pillar="Pillar 2",
        synergy_score=4.18,
        bliss_excess=0.1476,
        virtual_ci=0.35,
        target_orthogonality=0.9,
        route_compatibility="Oral / Systemic Combination",
        safety_tier="standard",
        drug_a_targets=["CD8A"],
        drug_b_targets=["MITF"],
        mechanistic_rationale="Immune disarmament + McSC mobilization",
    )
    out = tmp_path / "synergy.md"
    _render_synergy_markdown([pair], out)
    summary = out.read_text(encoding="utf-8").split("## Summary", 1)[1].split("| Rank", 1)[0]
    assert not re.search(r"\d+(\.\d+)?\s*%", summary)


def test_the_reverse_screen_asks_only_for_drugs_a_source_records(tmp_path: Path) -> None:
    """Chloroform, glucose, serotonin and nitrogen reached a target's top five: the screen
    ranked every canonical drug, including entities known only from sentences in papers."""
    from types import SimpleNamespace

    from vitiligo.gnn.reverse_screen import run_reverse_target_screening

    asked: list[object] = []

    def predict_top_k(**kwargs):  # type: ignore[no-untyped-def]
        asked.append(kwargs.get("candidate_indices"))
        return [
            {"name": "ruxolitinib", "score": 4.2, "kind": "DRUG", "key": "ruxolitinib"},
        ]

    dataset = SimpleNamespace(canonical_drug_indices=[1, 2, 3], screenable_drug_indices=[1])
    results = run_reverse_target_screening(
        dataset=dataset,
        gnn_model=SimpleNamespace(predict_top_k=predict_top_k),
        out_json=tmp_path / "rev.json",
        out_md=tmp_path / "rev.md",
    )
    assert asked and all(pool == [1] for pool in asked)  # never the whole canonical list
    hit = next(iter(results.values())).hits[0]
    assert hit.safety_tier and isinstance(hit.safety_tier, str)  # was the is_cytotoxic bool
    assert not hasattr(hit, "probability")  # an uncalibrated score is not a probability


def test_the_reverse_screen_cli_reads_only_fields_a_hit_has() -> None:
    """Dropping TargetScreenHit.probability left `vitiligo gnn reverse-screen` raising
    AttributeError in its own table, after it had already written the JSON."""
    import dataclasses
    import inspect
    import re

    from vitiligo.cli import gnn_reverse_screen
    from vitiligo.gnn.reverse_screen import TargetScreenHit

    fields = {f.name for f in dataclasses.fields(TargetScreenHit)}
    source = inspect.getsource(gnn_reverse_screen)
    read = set(re.findall(r"\bh\.([a-z_]+)", source))
    assert read, "the table reads no hit fields; this guard has stopped guarding"
    assert read <= fields, f"the table reads fields a hit does not have: {sorted(read - fields)}"


def test_no_screen_table_prints_the_uncalibrated_score_as_a_probability(tmp_path: Path) -> None:
    """A candidate's "probability" is sigmoid of its score. The reports printed it as
    "97.6%", which reads as a chance of something; the pair screen still consumes the
    number, so it stays in the JSON with a note saying what it is."""
    import inspect

    from vitiligo.gnn import screen

    for fn in (screen._render_markdown_report, screen.screen_candidates):
        source = inspect.getsource(fn)
        assert "probability" not in source.lower() or "probability_is" in source, (
            f"{fn.__name__} prints a probability again"
        )
    assert '"probability_is"' in inspect.getsource(screen.screen_candidates)
