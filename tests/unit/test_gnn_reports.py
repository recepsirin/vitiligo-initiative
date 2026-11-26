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


def test_the_synergy_summary_quotes_no_clinical_or_assay_synergy_figures(tmp_path: Path) -> None:
    pair = SynergyPairResult(
        rank=1,
        drug_a="cyclosporine",
        drug_b="Pioglitazone",
        drug_a_pillar="Pillar 1",
        drug_b_pillar="Pillar 2",
        synergy_score=3.85,
        pathway_complementarity=0.82,
        target_orthogonality=0.9,
        route_compatibility="Systemic / Oral Combination",
        safety_tier="standard",
        drug_a_targets=["CD8A (Inh*)"],
        drug_b_targets=["MITF (Act)"],
        mechanistic_rationale="Immune/TRM axis via cyclosporine (KG: CD8A); Regeneration axis via Pioglitazone (model-predicted: MITF)",
    )
    out = tmp_path / "synergy.md"
    _render_synergy_markdown([pair], out)
    text = out.read_text(encoding="utf-8")
    summary = text.split("## Summary", 1)[1].split("| Rank", 1)[0]
    assert not re.search(r"\d+(\.\d+)?\s*%", summary)
    assert "Chou-Talalay" not in text
    assert "Virtual CI" not in text
    assert "Bliss" not in text


def test_safety_profile_avoids_substring_and_indication_mislabels() -> None:
    from vitiligo.gnn.screen import get_safety_profile

    iso_tier, iso_chemo = get_safety_profile("Isotretinoin")
    assert not iso_chemo
    assert not iso_tier.startswith("Topical")
    assert "Retinoid" in iso_tier and "teratogenic" in iso_tier.lower()

    tret_tier, _ = get_safety_profile("tretinoin")
    assert tret_tier.startswith("Topical")

    for onc in ("fedratinib", "momelotinib", "CERDULATINIB"):
        tier, chemo = get_safety_profile(onc)
        assert not chemo
        assert "approved in derm/rheum" not in tier.lower()

    bari_tier, _ = get_safety_profile("baricitinib")
    assert "approved in derm/rheum" in bari_tier.lower()

    siro_tier, _ = get_safety_profile("SIROLIMUS")
    assert "Kinase/PDE4" not in siro_tier


def test_synergy_rationale_credits_only_drugs_assigned_to_each_pillar(tmp_path: Path) -> None:
    import json

    from vitiligo.gnn.synergy import screen_pairwise_synergy

    candidates_data = {
        "candidates": [
            {
                "drug_name": "baricitinib",
                "curative_triad_alignment": "Pillar 1: TRM Disarmament",
                "trm_disarmament_score": 1.6,
                "stem_cell_regen_score": 0.4,
                "barrier_suppression_score": 0.3,
                "matched_targets": ["JAK1 (Inh*)", "JAK3 (Inh*)", "STAT1 (Inh*)"],
                "safety_tier": "Targeted Kinase/PDE4 (Approved in derm/rheum; class safety monitoring)",
            },
            {
                "drug_name": "afamelanotide",
                "curative_triad_alignment": "Pillar 2: Stem-Cell Regeneration",
                # Higher uncalibrated latent TRM score than baricitinib, but not assigned to Pillar 1.
                "trm_disarmament_score": 2.4,
                "stem_cell_regen_score": 2.1,
                "barrier_suppression_score": 0.2,
                "matched_targets": ["MITF (Act)"],
                "safety_tier": "Repurposed Non-Oncology (Systemic/repurposed safety profile)",
            },
            {
                "drug_name": "roflumilast",
                "curative_triad_alignment": "Pillar 3: PDE4B Barrier Suppression",
                "trm_disarmament_score": 0.5,
                "stem_cell_regen_score": 0.4,
                "barrier_suppression_score": 2.2,
                "matched_targets": ["PDE4B (Inh*)", "PDE4A (Inh*)"],
                "safety_tier": "Targeted Kinase/PDE4 (Approved in derm/rheum; class safety monitoring)",
            },
        ]
    }
    cand_file = tmp_path / "candidates.json"
    cand_file.write_text(json.dumps(candidates_data), encoding="utf-8")

    results = screen_pairwise_synergy(
        top_candidates_path=cand_file,
        top_n_candidates=10,
        top_k_pairs=10,
        out_json=tmp_path / "syn.json",
        out_md=tmp_path / "syn.md",
    )
    by_pair = {frozenset((r.drug_a.lower(), r.drug_b.lower())): r for r in results}

    bari_afam = by_pair[frozenset(("baricitinib", "afamelanotide"))]
    assert "baricitinib: Immune/TRM (KG:" in bari_afam.mechanistic_rationale
    assert "afamelanotide: Regeneration (model-predicted: MITF)" in bari_afam.mechanistic_rationale
    assert "afamelanotide: Immune/TRM" not in bari_afam.mechanistic_rationale

    bari_roflu = by_pair[frozenset(("baricitinib", "roflumilast"))]
    assert "roflumilast: PDE4B barrier (KG: PDE4B, PDE4A)" in bari_roflu.mechanistic_rationale


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
