"""Weekly watch: what pending results would tell us, and what is new.

Both parts run without the corpus or PyMC, so the weekly workflow can run them.

- **Ranking.** For each pending target sealed by two or more models: the mutual
  information between its result and which model is right, at the trial's arm
  sizes (``voi.model_discrimination`` on the sealed draws). It says which result
  to watch for; it does not rank evidence the models have no forecast for.
- **New since a date.** The places past results appeared first:
  - Europe PMC: papers and preprints naming a JAK inhibitor and vitiligo;
  - ClinicalTrials.gov: JAK vitiligo trials registered or updated, and results posted;
  - SEC filings (8-K, 6-K) mentioning vitiligo, where listed sponsors report
    toplines. SEC requires a declared contact, so this runs only when
    ``SEC_USER_AGENT`` is set (for example "Jane Doe jane@example.org").

Every hit is a lead for a person to read, not a curated result.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from vitiligo.discovery import voi
from vitiligo.discovery.forecasts import Resolution, comparison_key
from vitiligo.reports.jak import JAK_AGENTS, match_agents

# (url, params, headers) -> parsed JSON
Get = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]

USER_AGENT = "vitiligo-initiative/1.0 (+https://github.com/recepsirin/vitiligo-initiative)"
EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

# Arm sizes (active, control) where the registry's equal split is wrong or the
# analysis size is known. Everything else: registered enrolment / number of arms.
ARM_SIZES: dict[tuple[str, float], tuple[int, int]] = {
    ("NCT05583526", 50.0): (401, 202),  # Tranquillo, 2:1 (EADV 2026 LB-161)
    ("NCT06072183", 50.0): (206, 208),  # Tranquillo 2, 50 mg arm vs placebo
    ("NCT06113445", 30.0): (222, 222),  # STOP-V1, 1:1 of ~444 (EU CTIS); reproduces 18.9%/6.8%
    ("NCT06113471", 30.0): (222, 222),  # STOP-V2, 1:1 of ~444 (EU CTIS)
}


def http_get(url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    response = httpx.get(
        url, params=params, headers={"User-Agent": USER_AGENT, **headers}, timeout=60.0
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


# ------------------------------------------------------------------- ranking


@dataclass
class PendingTarget:
    key: tuple[Any, ...]  # comparison_key: trial, instrument, threshold, week, dose
    models: list[str]
    n_active: int
    n_control: int
    sizes_from: str
    mutual_information_nats: float
    max_nats: float
    p_true_model_gets_75pct: float


def registry_arm_sizes(study: dict[str, Any] | None) -> tuple[int, int] | None:
    """Registered enrolment split equally over the registered arms."""
    protocol = (study or {}).get("protocolSection") or {}
    enrolled = ((protocol.get("designModule") or {}).get("enrollmentInfo") or {}).get("count")
    arms = (protocol.get("armsInterventionsModule") or {}).get("armGroups") or []
    if not enrolled or not arms:
        return None
    per_arm = int(enrolled) // len(arms)
    return per_arm, per_arm


def rank_pending(
    sealed: Sequence[tuple[str, Path, dict[str, Any], Resolution]],
    studies: dict[str, dict[str, Any] | None],
    *,
    sims: int = 2000,
    seed: int = 0,
) -> list[PendingTarget]:
    """Unresolved targets sealed (with draws) by two or more models, most informative first.

    ``sealed`` holds (model, path, record, resolution); ``studies`` maps trial
    ids to raw ClinicalTrials.gov records, for arm sizes.
    """
    draws: dict[tuple[Any, ...], dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    resolved: set[tuple[Any, ...]] = set()
    for model, path, record, result in sealed:
        key = comparison_key(record)
        if key is None:
            continue
        if result.resolved:
            resolved.add(key)
        draws_name = record.get("draws_file")
        if not draws_name or not (path.parent / draws_name).is_file():
            continue
        with np.load(path.parent / draws_name) as d:
            draws.setdefault(key, {})[model] = (
                np.asarray(d["p_active"], dtype=float),
                np.asarray(d["p_control"], dtype=float),
            )
    ranked = []
    for key, models in sorted(draws.items()):
        if key in resolved or len(models) < 2:
            continue
        known = ARM_SIZES.get((key[0], float(key[4])))
        sizes = known or registry_arm_sizes(studies.get(key[0]))
        if sizes is None:
            continue
        info = voi.model_discrimination(models, *sizes, sims=sims, seed=seed)
        ranked.append(
            PendingTarget(
                key=key,
                models=sorted(models),
                n_active=sizes[0],
                n_control=sizes[1],
                sizes_from="known allocation" if known else "equal split of enrolment",
                **info,
            )
        )
    ranked.sort(key=lambda t: -t.mutual_information_nats)
    return ranked


# ---------------------------------------------------------------------- news


@dataclass
class Hit:
    source: str
    date: str
    title: str
    url: str
    agents: list[str] = field(default_factory=list)
    note: str = ""


def _agent_terms() -> list[str]:
    terms = []
    for agent in JAK_AGENTS:
        terms.append(agent.name)
        terms += [f'"{a}"' for a in agent.aliases]
    return terms


def _plain(text: str) -> str:
    """Title text without HTML entities or tags."""
    return re.sub(r"<[^>]+>", "", html.unescape(text)).strip()


def europe_pmc(since: date, get: Get = http_get, *, limit: int = 200) -> list[Hit]:
    """Papers and preprints first published on or after ``since``."""
    # Title and abstract only: full-text matches are mostly passing mentions.
    query = (
        f"TITLE_ABS:vitiligo AND TITLE_ABS:({' OR '.join(_agent_terms())}) "
        f"AND FIRST_PDATE:[{since.isoformat()} TO 3000-12-31]"
    )
    hits: list[Hit] = []
    cursor = "*"
    while len(hits) < limit:
        data = get(
            EUROPE_PMC_URL,
            {"query": query, "format": "json", "resultType": "lite", "pageSize": 100,
             "cursorMark": cursor},
            {},
        )  # fmt: skip
        results = (data.get("resultList") or {}).get("result") or []
        for r in results:
            doi = r.get("doi")
            title = _plain(r.get("title", ""))
            hits.append(
                Hit(
                    source="Europe PMC",
                    date=r.get("firstPublicationDate") or str(r.get("pubYear", "")),
                    title=title,
                    url=f"https://doi.org/{doi}"
                    if doi
                    else f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}",
                    agents=match_agents(title),
                    note=r.get("journalTitle") or r.get("pubType") or "",
                )
            )
        next_cursor = data.get("nextCursorMark")
        if not results or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    return hits[:limit]


def ctgov(since: date, get: Get = http_get) -> list[Hit]:
    """JAK vitiligo trials registered or updated on or after ``since``."""
    params: dict[str, Any] = {
        "query.cond": "vitiligo",
        "query.intr": " OR ".join(a.name for a in JAK_AGENTS),
        "filter.advanced": f"AREA[LastUpdatePostDate]RANGE[{since.isoformat()},MAX]",
        "fields": "NCTId,BriefTitle,OverallStatus,StudyFirstPostDate,LastUpdatePostDate,HasResults",
        "pageSize": 100,
    }
    hits: list[Hit] = []
    while True:
        data = get(CTGOV_URL, params, {})
        for study in data.get("studies") or []:
            protocol = study.get("protocolSection") or {}
            ident = protocol.get("identificationModule") or {}
            status = protocol.get("statusModule") or {}
            first = (status.get("studyFirstPostDateStruct") or {}).get("date", "")
            updated = (status.get("lastUpdatePostDateStruct") or {}).get("date", "")
            new = first >= since.isoformat()
            note = "newly registered" if new else "updated"
            if study.get("hasResults"):
                note += "; results posted"
            hits.append(
                Hit(
                    source="ClinicalTrials.gov",
                    date=first if new else updated,
                    title=f"{ident.get('nctId')}: {ident.get('briefTitle', '')}",
                    url=f"https://clinicaltrials.gov/study/{ident.get('nctId')}",
                    agents=match_agents(ident.get("briefTitle", "")),
                    note=f"{note} ({status.get('overallStatus', '').lower().replace('_', ' ')})",
                )
            )
        token = data.get("nextPageToken")
        if not token:
            return hits
        params = {**params, "pageToken": token}


def sec_filings(
    since: date, user_agent: str | None, get: Get = http_get, *, until: date | None = None
) -> list[Hit] | None:
    """8-K and 6-K filings mentioning vitiligo; None when no SEC contact is configured."""
    if not user_agent or not re.search(r"\S+@\S+\.\S+", user_agent):
        return None
    data = get(
        SEC_SEARCH_URL,
        {
            "q": '"vitiligo"',
            "forms": "8-K,6-K",
            "dateRange": "custom",
            "startdt": since.isoformat(),
            "enddt": (until or date.today()).isoformat(),
        },
        {"User-Agent": user_agent},
    )
    hits = []
    for h in (data.get("hits") or {}).get("hits") or []:
        src = h.get("_source") or {}
        adsh, _, filename = str(h.get("_id", "")).partition(":")
        ciks = src.get("ciks") or [""]
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(ciks[0])}/{adsh.replace('-', '')}/{filename}"
            if ciks[0] and adsh and filename
            else ""
        )
        company = re.sub(r"\s+", " ", (src.get("display_names") or ["?"])[0])
        hits.append(
            Hit(
                source="SEC",
                date=src.get("file_date", ""),
                title=f"{company}: {src.get('form', '')} {src.get('file_type', '')}".strip(),
                url=url,
            )
        )
    return hits
