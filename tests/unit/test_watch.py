"""Weekly watch: ranking pending results and parsing the news sources (offline)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from vitiligo.discovery import watch
from vitiligo.discovery.forecasts import Resolution


def _sealed(tmp_path: Path, model: str, trial: str, p_active: float, resolved: bool = False):
    folder = tmp_path / model
    folder.mkdir(exist_ok=True)
    rng = np.random.default_rng(0)
    np.savez(
        folder / f"{trial}.npz",
        p_active=np.clip(rng.normal(p_active, 0.02, 400), 0.01, 0.99),
        p_control=np.clip(rng.normal(0.05, 0.01, 400), 0.01, 0.99),
    )
    record = {
        "target": {"trial": trial, "instrument": "F-VASI", "threshold": 75, "week": 24,
                   "dose_value": 1.5},
        "draws_file": f"{trial}.npz",
    }  # fmt: skip
    result = Resolution("s", trial, resolved, {"log_score": -3.0} if resolved else {})
    return model, folder / f"{trial}.json", record, result


def _study(enrolled: int, arms: int) -> dict[str, Any]:
    return {
        "protocolSection": {
            "designModule": {"enrollmentInfo": {"count": enrolled}},
            "armsInterventionsModule": {"armGroups": [{}] * arms},
        }
    }


def test_rank_pending_prefers_results_that_separate_the_models(tmp_path: Path) -> None:
    sealed = [
        # A: the models disagree (10% vs 40%), so its result is informative.
        _sealed(tmp_path, "v0.2", "NCT00000001", 0.40),
        _sealed(tmp_path, "v0.4", "NCT00000001", 0.10),
        # B: the models agree.
        _sealed(tmp_path, "v0.2", "NCT00000002", 0.20),
        _sealed(tmp_path, "v0.4", "NCT00000002", 0.21),
        # C: resolved, so not pending. D: one model only.
        _sealed(tmp_path, "v0.2", "NCT00000003", 0.40, resolved=True),
        _sealed(tmp_path, "v0.4", "NCT00000003", 0.10),
        _sealed(tmp_path, "v0.2", "NCT00000004", 0.40),
    ]
    studies = {f"NCT0000000{i}": _study(300, 3) for i in range(1, 5)}
    ranked = watch.rank_pending(sealed, studies, sims=400)
    assert [t.key[0] for t in ranked] == ["NCT00000001", "NCT00000002"]
    assert ranked[0].mutual_information_nats > 0.5 > ranked[1].mutual_information_nats
    assert (ranked[0].n_active, ranked[0].n_control) == (100, 100)
    assert ranked[0].sizes_from == "equal split of enrolment"


def test_known_arm_sizes_override_the_registry_split() -> None:
    assert watch.registry_arm_sizes(_study(467, 2)) == (233, 233)
    assert watch.registry_arm_sizes(None) is None
    assert watch.ARM_SIZES[("NCT06113445", 30.0)] == (222, 222)


def test_europe_pmc_pages_and_cleans_titles() -> None:
    calls: list[dict[str, Any]] = []
    pages = [
        {"nextCursorMark": "c1", "resultList": {"result": [
            {"title": "CD8&lt;sup&gt;+&lt;/sup&gt; cells and <i>ruxolitinib</i> in vitiligo",
             "doi": "10.1/x", "firstPublicationDate": "2026-10-01", "journalTitle": "J"},
        ]}},
        {"nextCursorMark": "c1", "resultList": {"result": [
            {"title": "Povorcitinib phase 3", "source": "PPR", "id": "PPR1",
             "firstPublicationDate": "2026-10-02"},
        ]}},
    ]  # fmt: skip

    def get(url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        calls.append(params)
        return pages[len(calls) - 1]

    hits = watch.europe_pmc(date(2026, 9, 1), get)
    assert [h.title for h in hits] == [
        "CD8+ cells and ruxolitinib in vitiligo",
        "Povorcitinib phase 3",
    ]
    assert hits[0].agents == ["ruxolitinib"] and hits[0].url == "https://doi.org/10.1/x"
    assert hits[1].url == "https://europepmc.org/article/PPR/PPR1"
    assert "TITLE_ABS:vitiligo" in calls[0]["query"]
    assert "FIRST_PDATE:[2026-09-01" in calls[0]["query"]
    assert len(calls) == 2  # stops when the cursor stops moving


def test_ctgov_marks_new_trials_and_posted_results() -> None:
    def study(nct: str, first: str, results: bool) -> dict[str, Any]:
        return {
            "protocolSection": {
                "identificationModule": {"nctId": nct, "briefTitle": "Povorcitinib in vitiligo"},
                "statusModule": {
                    "overallStatus": "ACTIVE_NOT_RECRUITING",
                    "studyFirstPostDateStruct": {"date": first},
                    "lastUpdatePostDateStruct": {"date": "2026-10-10"},
                },
            },
            "hasResults": results,
        }

    pages = [
        {"studies": [study("NCT1", "2026-10-08", False)], "nextPageToken": "t"},
        {"studies": [study("NCT2", "2023-01-01", True)]},
    ]
    seen: list[dict[str, Any]] = []

    def get(url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        seen.append(params)
        return pages[len(seen) - 1]

    hits = watch.ctgov(date(2026, 10, 1), get)
    assert [(h.date, h.note) for h in hits] == [
        ("2026-10-08", "newly registered (active not recruiting)"),
        ("2026-10-10", "updated; results posted (active not recruiting)"),
    ]
    assert hits[0].agents == ["povorcitinib"]
    assert seen[1]["pageToken"] == "t"
    assert "RANGE[2026-10-01,MAX]" in seen[0]["filter.advanced"]


def test_sec_needs_a_declared_contact_and_builds_filing_links() -> None:
    def get(url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        assert headers == {"User-Agent": "Jane Doe jane@example.org"}
        assert params["forms"] == "8-K,6-K" and params["startdt"] == "2026-04-01"
        return {"hits": {"hits": [{
            "_id": "0000879169-26-000023:incy-q12026xexx991.htm",
            "_source": {"ciks": ["0000879169"], "display_names": ["INCYTE CORP  (INCY)"],
                        "file_date": "2026-04-28", "form": "8-K", "file_type": "EX-99.1"},
        }]}}  # fmt: skip

    assert watch.sec_filings(date(2026, 4, 1), None, get) is None
    assert watch.sec_filings(date(2026, 4, 1), "no contact", get) is None
    hits = watch.sec_filings(
        date(2026, 4, 1), "Jane Doe jane@example.org", get, until=date(2026, 5, 1)
    )
    assert hits is not None and len(hits) == 1
    assert hits[0].title == "INCYTE CORP (INCY): 8-K EX-99.1"
    assert hits[0].url == (
        "https://www.sec.gov/Archives/edgar/data/879169/000087916926000023/incy-q12026xexx991.htm"
    )
