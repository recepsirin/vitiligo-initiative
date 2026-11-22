"""The trial explorer's rows: one per trial, credited and labelled correctly."""

from __future__ import annotations

import re

import pytest

from vitiligo.reports.jak import match_agents
from vitiligo.storage import Trial, TrialSourceKind
from vitiligo.trials.explorer import (
    _ICTRP_REGISTRIES,
    OBSERVATIONAL,
    TREATMENT_GROUPS,
    explorer_rows,
    in_explorer,
    iso_date,
    phase_label,
    registry_of,
    treatment_groups,
    treatment_text,
)
from vitiligo.trials.relevance import fold


def _trial(source: TrialSourceKind, source_id: str, **fields: object) -> Trial:
    fields.setdefault("conditions", ["Vitiligo"])
    fields.setdefault("brief_title", "A study in vitiligo")
    return Trial(source=source, source_id=source_id, **fields)


@pytest.mark.parametrize(
    ("phases", "label"),
    [
        (["PHASE2", "PHASE3"], "Phase 2/3"),  # ClinicalTrials.gov: two values
        (["Phase I/II"], "Phase 1/2"),  # ISRCTN: one string, Roman numerals
        (["EARLY_PHASE1"], "Early phase 1"),
        (["NA"], "Not applicable"),
    ],
)
def test_phase_labels_read_each_registry_spelling(phases: list[str], label: str) -> None:
    assert phase_label(phases)[0] == label


def test_ictrp_dates_are_read_day_first() -> None:
    assert iso_date("03/12/2012") == "2012-12-03"


@pytest.mark.parametrize(
    ("source_id", "registry"),
    [
        # Neither form is reached by the citation patterns in cited_trials.py,
        # which is why the explorer reads identifiers by prefix.
        ("ChiCTR-TRC-12002594", "ChiCTR (China)"),
        ("JPRN-jRCTb030200129", "jRCT (Japan)"),
    ],
)
def test_an_ictrp_record_is_credited_to_its_registry(source_id: str, registry: str) -> None:
    assert registry_of(_trial(TrialSourceKind.ICTRP, source_id)) == registry


def test_a_trial_held_twice_is_one_row_from_its_own_registry() -> None:
    ctis = _trial(TrialSourceKind.EUCTR, "2025-524709-34-00", sponsors=[], has_results=False)
    copy = _trial(
        TrialSourceKind.ICTRP,
        "CTIS2025-524709-34-00",
        sponsors=[{"role": "lead", "name": "CHU de Nice"}],
        has_results=True,
    )
    rows, merged = explorer_rows([copy, ctis])
    assert merged == 1
    assert len(rows) == 1
    assert rows[0]["id"] == "2025-524709-34-00"
    assert rows[0]["registry"] == "EU CTIS"
    assert rows[0]["sponsor"] == "CHU de Nice"
    assert rows[0]["results"] is True


def test_an_observational_study_keeps_its_treatment_and_is_marked_observational() -> None:
    study = _trial(
        TrialSourceKind.ICTRP,
        "ChiCTR2500095163",
        brief_title="A real-world study of ruxolitinib cream in vitiligo",
        study_type="OBSERVATIONAL",
    )
    rows, _ = explorer_rows([study])
    assert rows[0]["groups"] == ["JAK inhibitor", OBSERVATIONAL]


@pytest.mark.parametrize(
    ("text", "group"),
    [
        ("ibuprofen | non steroidal antiinflammatory", "Corticosteroid"),
        (
            "Filiform fire needling therapy relieves melanocyte apoptosis",
            "Microneedling & dermabrasion",
        ),
    ],
)
def test_a_name_that_only_looks_like_a_treatment_is_not_one(text: str, group: str) -> None:
    assert group not in treatment_groups(text)


# --------------------------------------------------------------- the corpus


def _explorer_trials() -> list[Trial]:
    from sqlmodel import Session, select

    from vitiligo.storage import get_engine

    with Session(get_engine(), expire_on_commit=False) as session:
        return [t for t in session.exec(select(Trial)) if in_explorer(t)]


@pytest.mark.corpus
def test_every_treatment_pattern_alone_labels_a_corpus_trial(require_local_corpus: None) -> None:
    """A pattern that labels no trial on its own is dead weight and goes.

    The counts beside each pattern in ``TREATMENT_GROUPS`` are these sole
    matches. When this fails, re-read the pattern's remaining matches before
    deleting it: the corpus may have changed rather than the pattern.
    """
    texts = [treatment_text(t) for t in _explorer_trials()]
    folded = [fold(t) for t in texts]
    dead = []
    for group, patterns in TREATMENT_GROUPS.items():
        compiled = [re.compile(p) for p in patterns]
        for i, pattern in enumerate(compiled):
            others = compiled[:i] + compiled[i + 1 :]
            alone = sum(
                1
                for raw, text in zip(texts, folded, strict=True)
                if pattern.search(text)
                and not any(o.search(text) for o in others)
                and not (group == "JAK inhibitor" and match_agents(raw))
            )
            if alone == 0:
                dead.append((group, pattern.pattern))
    assert not dead, f"patterns that label no trial alone: {dead}"


@pytest.mark.corpus
def test_every_ictrp_record_is_credited_to_a_named_registry(require_local_corpus: None) -> None:
    ictrp = [t for t in _explorer_trials() if t.source == TrialSourceKind.ICTRP]
    unnamed = sorted(t.source_id for t in ictrp if registry_of(t) == "WHO ICTRP")
    assert not unnamed, f"add a prefix for: {unnamed[:10]}"
    unused = [
        name
        for name, pattern in _ICTRP_REGISTRIES
        if not any(pattern.search(t.source_id) for t in ictrp)
    ]
    assert not unused, f"prefixes naming no held record: {unused}"


def test_an_ictrp_trials_groups_read_the_registrys_whole_text() -> None:
    # The name is the label; the treatment is in the text the registry wrote.
    trial = Trial(
        source=TrialSourceKind.ICTRP,
        source_id="CTRI/2018/01/011120",
        brief_title="Aragvadhadi preparations in vitiligo",
        interventions=[
            {
                "type": "DRUG",
                "name": "Aragvadhadi Gel",
                "free_text": "Aragvadhadi Gel: applied with NB-UVB phototherapy twice weekly",
            }
        ],
    )
    assert "phototherapy" in treatment_text(trial).lower()
