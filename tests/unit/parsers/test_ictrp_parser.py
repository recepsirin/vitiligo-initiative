"""Offline tests for the WHO ICTRP XML parser."""

from __future__ import annotations

from pathlib import Path

from tests.helpers.paths import FIXTURES_DIR

from vitiligo.sources.ictrp import (
    _SKIP_PRIMARY_REGISTERS,
    count_ictrp_records,
    extract_cross_registry_keys,
    iter_ictrp_trials,
    normalize_protocol_id,
    parse_ictrp_record,
    should_skip_ictrp_record,
)
from vitiligo.storage.models import Trial, TrialSourceKind

FIXTURE = FIXTURES_DIR / "ictrp_vitiligo_sample.xml"


def test_count_and_iter_fixture() -> None:
    assert count_ictrp_records(FIXTURE) == 3
    trials = list(iter_ictrp_trials(FIXTURE))
    assert len(trials) == 3
    assert {t.source_id for t in trials} == {
        "ChiCTR2300070001",
        "NCT03099304",
        "ISRCTN99887766",
    }


def test_parse_chictr_record_fields() -> None:
    trials = list(iter_ictrp_trials(FIXTURE))
    chictr = next(t for t in trials if t.source_id == "ChiCTR2300070001")
    assert chictr.source == TrialSourceKind.ICTRP
    assert chictr.status == "RECRUITING"
    assert chictr.phases == ["PHASE2"]
    assert chictr.study_type == "INTERVENTIONAL"
    assert "Vitiligo" in chictr.conditions
    assert chictr.interventions[0]["name"] == "Ruxolitinib cream 1.5%"
    assert chictr.countries == ["China"]
    assert chictr.enrollment_count == 120
    assert chictr.minimum_age == "18 Years"
    assert chictr.has_results is False


def test_extract_cross_registry_keys() -> None:
    keys = extract_cross_registry_keys(
        "ChiCTR2300070001",
        ["NCT03099304", "2024-001234-56-01"],
    )
    assert (TrialSourceKind.CTGOV, "NCT03099304") in keys
    assert (TrialSourceKind.EUCTR, "2024-001234-56-01") in keys


def test_should_skip_ctgov_and_existing_duplicates() -> None:
    trials = list(iter_ictrp_trials(FIXTURE))
    ctgov = next(t for t in trials if t.source_id == "NCT03099304")
    isrctn = next(t for t in trials if t.source_id == "ISRCTN99887766")

    existing = {("ctgov", "NCT03099304")}
    assert should_skip_ictrp_record(ctgov, skip_duplicates=True, existing_keys=existing)
    assert not should_skip_ictrp_record(isrctn, skip_duplicates=True, existing_keys=existing)


def test_parse_single_record_root() -> None:
    from lxml import etree

    trials = list(iter_ictrp_trials(FIXTURE))
    root = etree.fromstring(Path(FIXTURE).read_bytes())
    first_record = root.find(".//trial")
    assert first_record is not None
    reparsed = parse_ictrp_record(first_record)
    assert reparsed is not None
    assert reparsed.source_id == trials[0].source_id


def _euctr(trial_id: str, secondary: list[str]) -> Trial:
    """An EU Clinical Trials Register record as the ICTRP export gives it."""
    return Trial(
        source=TrialSourceKind.ICTRP,
        source_id=trial_id,
        brief_title="A European vitiligo trial",
        conditions=["Vitiligo"],
        raw_metadata={
            "trial_id": trial_id,
            "primary_register": "EU Clinical Trials Register",
            "secondary_ids": secondary,
            "cross_registry_keys": [],
        },
    )


def test_the_eu_register_is_not_a_register_we_already_ingest() -> None:
    """The euctr pipeline reads CTIS, which replaced that register in 2023.

    Treating them as the same thing skipped every European vitiligo trial
    predating CTIS: eighteen in the ICTRP export, seven of them held nowhere
    else, including a secukinumab pilot and a tacrolimus trial.
    """
    assert "EU Clinical Trials Register" not in _SKIP_PRIMARY_REGISTERS
    assert "ClinicalTrials.gov" in _SKIP_PRIMARY_REGISTERS
    record = _euctr("EUCTR2005-002922-79-CZ", ["Vitiligo"])
    assert not should_skip_ictrp_record(
        record, skip_duplicates=True, existing_keys=set(), existing_protocol_ids=set()
    )


def test_a_sponsor_protocol_number_links_a_european_record_to_its_nct() -> None:
    """A European record names the protocol, not the NCT.

    TRuE-V1 is "INCB18424-306" in the EU register and NCT04052425 on
    ClinicalTrials.gov, and no id they share says so. Without this the trial
    is imported twice, once per registry.
    """
    record = _euctr("EUCTR2019-000846-37-FR", ["INCB18424-306"])
    assert should_skip_ictrp_record(
        record,
        skip_duplicates=True,
        existing_keys=set(),
        existing_protocol_ids={normalize_protocol_id("INCB 18424-306")},
    )


def test_protocol_matching_ignores_punctuation_and_case() -> None:
    """ClinicalTrials.gov writes "INCB 18424-306"; the EU register does not."""
    assert normalize_protocol_id("INCB 18424-306") == normalize_protocol_id("incb18424-306")
    assert normalize_protocol_id("CHUBX2022/03") == normalize_protocol_id("chubx 2022 03")


def test_a_short_secondary_id_cannot_collide() -> None:
    """Registries put "PTZ" and "vit-001" in that field.

    A three-character token would match far too much, so only tokens of at
    least six characters are compared.
    """
    record = _euctr("EUCTR2021-001442-35-IT", ["PTZ"])
    assert not should_skip_ictrp_record(
        record,
        skip_duplicates=True,
        existing_keys=set(),
        existing_protocol_ids={"PTZ", normalize_protocol_id("PTZ")},
    )


def _ctgov(nct: str, protocol: str) -> Trial:
    return Trial(
        source=TrialSourceKind.CTGOV,
        source_id=nct,
        brief_title=f"Trial {nct}",
        raw_metadata={
            "study": {
                "protocolSection": {"identificationModule": {"orgStudyIdInfo": {"id": protocol}}}
            }
        },
    )


def test_a_number_two_trials_cite_identifies_neither(test_db_path) -> None:
    """Some secondary ids name a cohort or consortium, not a protocol.

    Among the vitiligo trials held, "TARGETDERM" is cited by two separate
    ClinicalTrials.gov records. Treating it as identifying would skip a real
    European trial as a duplicate of whichever it matched first.
    """
    from sqlmodel import Session

    from vitiligo.ingest.pipeline import _load_protocol_ids
    from vitiligo.storage import get_engine

    with Session(get_engine()) as session:
        session.add(_ctgov("NCT00000001", "INCB 18424-306"))
        session.add(_ctgov("NCT00000002", "TARGETDERM"))
        session.add(_ctgov("NCT00000003", "TARGETDERM"))
        session.commit()
        keys = _load_protocol_ids(session)

    assert normalize_protocol_id("INCB18424-306") in keys, "a unique protocol must be usable"
    assert normalize_protocol_id("TARGETDERM") not in keys, "a shared number identifies neither"
