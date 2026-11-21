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


def _hit(rank: int, name: str, probability: float) -> TargetScreenHit:
    return TargetScreenHit(
        rank=rank,
        drug_name=name,
        canonical_name=name.lower(),
        score=1.0,
        probability=probability,
        mechanism_class="kinase inhibitor",
        route="oral",
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
            hits=[_hit(1, "cobimetinib", 0.9825), _hit(2, "dabrafenib", 0.9796)],
        )
    }
    out = tmp_path / "reverse.md"
    _render_reverse_screen_md(results, out)
    text = out.read_text(encoding="utf-8")
    summary = text.split("## Summary", 1)[1].split("---", 1)[0]
    assert "**cobimetinib** (98.2%)" in summary
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
