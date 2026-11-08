"""Genes vitiligo skin expresses differently: the statistics, the guard, and the graph."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from sqlmodel import select

import vitiligo.config as cfg
import vitiligo.storage.db as dbmod
from vitiligo.graph.evidence_seed import seed_expression
from vitiligo.graph.store import upsert_entity
from vitiligo.models.expression import (
    MELANOCYTE,
    Contrast,
    compare,
    moderated_t,
    prior,
    read_results,
    write_results,
)
from vitiligo.sources.geo_expression import Expression
from vitiligo.storage import init_db, session_scope
from vitiligo.storage.models import EntityKind, GraphEdge, GraphEntity


def test_the_moderated_t_recovers_its_prior_and_is_calibrated_under_the_null() -> None:
    """Gene variances drawn from limma's model give back its prior, and with no
    difference anywhere one test in twenty falls below 0.05.
    """
    pytest.importorskip("scipy")
    rng = np.random.default_rng(1)
    genes, n, d0, s02 = 20_000, 6, 4.0, 0.25
    sigma = np.sqrt(s02 * d0 / rng.chisquare(d0, genes))[:, None]
    x, y = rng.normal(0, sigma, (genes, n)), rng.normal(0, sigma, (genes, n))
    s2 = (x.var(axis=1, ddof=1) + y.var(axis=1, ddof=1)) / 2

    fitted = prior(s2, 2 * n - 2)
    _, p = moderated_t(x.mean(axis=1) - y.mean(axis=1), s2, 2 * n - 2, np.sqrt(2 / n))

    assert fitted == pytest.approx((d0, s02), rel=0.05)
    assert (p < 0.05).mean() == pytest.approx(0.05, abs=0.005)


def _skin(lesion_shift: float) -> Expression:
    """Six patients, a lesional and a non-lesional sample each; 400 genes of noise,
    the pigment genes moved by ``lesion_shift`` in lesions and CXCL10 raised. Patients
    differ far more than a lesion does, so only a paired test sees the lesion.
    """
    rng = np.random.default_rng(7)
    genes = [*MELANOCYTE, "CXCL10", *(f"G{i}" for i in range(400))]
    patients = rng.normal(8, 1, (len(genes), 1)) + rng.normal(0, 3, (len(genes), 6))
    lesional = patients + rng.normal(0, 0.2, patients.shape)
    non_lesional = patients + rng.normal(0, 0.2, patients.shape)
    lesional[: len(MELANOCYTE)] += lesion_shift
    lesional[len(MELANOCYTE)] += 3
    samples = [f"P{i}L" for i in range(6)] + [f"P{i}N" for i in range(6)]
    return Expression(genes, samples, np.hstack([lesional, non_lesional]))


@pytest.fixture
def graph_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("VITILIGO_DB_PATH", str(tmp_path / "graph.db"))
    cfg._settings = None
    dbmod._engine = None
    init_db()
    yield
    cfg._settings = None
    dbmod._engine = None


def test_a_comparison_blind_to_melanocyte_loss_is_not_used_and_agreement_ranks_a_gene(
    tmp_path: Path, graph_db: None
) -> None:
    """Pairs are tested as pairs; a comparison whose lesions keep their pigment genes
    writes nothing; a gene two cohorts agree on ranks above one seen once.
    """
    pytest.importorskip("scipy")

    def contrast(series: str) -> Contrast:
        return Contrast(series, "lesional vs non-lesional", r"L$", r"N$", pair=r"^(P\d)")

    seen = compare(contrast("GSE1"), _skin(-3))
    again = compare(contrast("GSE2"), _skin(-3))
    blind = compare(contrast("GSE3"), _skin(0))
    write_results([seen, again, blind], tmp_path)
    rows = read_results(tmp_path)

    assert (seen.n_case, seen.n_control) == (6, 6)
    assert seen.sees_melanocyte_loss and not blind.sees_melanocyte_loss
    assert {r["series"] for r in rows} == {"GSE1", "GSE2"}
    assert {r["gene"] for r in rows} >= {*MELANOCYTE, "CXCL10"}

    with session_scope() as session:
        vitiligo = upsert_entity(session, kind=EntityKind.DISEASE, name="vitiligo")
        once = [r for r in rows if r["gene"] != "TYR" or r["series"] == "GSE1"]
        seed_expression(session, vitiligo, once)
    with session_scope() as session:
        names = {e.id: e.name for e in session.exec(select(GraphEntity)).all()}
        edges = {names[e.subject_id]: e for e in session.exec(select(GraphEdge)).all()}

    assert [r["cohorts_agreeing"] for r in edges["DCT"].evidence] == [2, 2]
    assert [r["cohorts_agreeing"] for r in edges["TYR"].evidence] == [1]
    assert edges["TYR"].confidence < edges["DCT"].confidence
