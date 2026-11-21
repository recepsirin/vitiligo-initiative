"""Results read from trial papers, as the Space's trial explorer shows them.

``curation/trial-results.jsonl`` holds what one AI reader extracted from the papers
of 1,245 vitiligo trials, plus two pooled TRuE-V analyses: 8,696 values, each
checked by ``vitiligo trials verify-results`` against the sentence or table cell it
was read from (all pass). A blind re-reading of 125 trials found 97% of its numbers
in the first reading; both readings are an AI's, and no person has audited them.
The page says so beside the results.

What reaches the page:

- **Values that carry a result**: a count, rate, mean, median, effect, confidence
  limit or p-value, printed as a number or as a bound such as ``<0.001``. Values
  that only record a direction, or that something was not reported, stay in the
  curation file.
- **No adverse events, baselines or access figures.** The README's rule for the
  trial-results view applies to adverse events: they belong in the label and the
  registry record, not in a table that cannot carry their context. A baseline
  describes patients before treatment, and an access figure (insurance coverage)
  is not a trial result. On 2026-11-21 these rules left out 1,009, 140 and 4 values
  that carry a number, and 6,667 values reached the page.
- **A quote only where its paper's licence allows it** -- CC BY or CC0 as Europe
  PMC records it, the rule the knowledge-graph release follows. Every other value
  carries its source pointer (the paper, and its abstract, body or table) and no
  text.
- **Filed under the explorer's own trial row.** A paper is keyed by its PMID or DOI
  and a registered trial by its registry id; a paper of a registered trial follows
  its link to that trial, and a pooled analysis is filed under every trial it
  combines and marked as pooled.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

# The fields that hold a result. A value is shown only if one of them does.
RESULT_FIELDS = (
    "responders",
    "n",
    "percent",
    "mean",
    "sd",
    "se",
    "median",
    "q1",
    "q3",
    "effect",
    "ci_low",
    "ci_high",
    "p",
)
DETAIL_FIELDS = (
    "outcome",
    "type",
    "measure",
    "instrument",
    "threshold",
    "time",
    "weeks",
    "population",
    "subgroup",
    "assessor",
    "direction",
    "ci_level",
)
EXCLUDED_TYPES = frozenset({"adverse event", "baseline", "access"})
OPEN_LICENCES = frozenset({"cc by", "cc0"})  # as vitiligo.graph.export
_PRINTED_BOUND = re.compile(r"^\s*[<>≤≥=]?\s*\d")


def carries_result(value: Mapping[str, Any]) -> bool:
    """True when the value holds a number, or a p-value printed as a bound."""
    for field in RESULT_FIELDS:
        item = value.get(field)
        if isinstance(item, bool):
            continue
        if isinstance(item, int | float):
            return True
        if field == "p" and isinstance(item, str) and _PRINTED_BOUND.match(item):
            return True
    return False


def explorer_index(trials: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Curated trial keys to explorer ids: registry ids as they are, papers by PMID and DOI."""
    index: dict[str, str] = {}
    for trial in trials:
        tid = str(trial["id"])
        index[tid] = tid
        if trial.get("pmid"):
            index[f"pmid:{trial['pmid']}"] = tid
        if trial.get("doi"):
            index[f"doi:{str(trial['doi']).lower()}"] = tid
    return index


def _lookup(index: Mapping[str, str], key: str) -> str | None:
    return index.get(key.lower() if key.startswith("doi:") else key)


def explorer_trials(entry: Mapping[str, Any], index: Mapping[str, str]) -> list[str]:
    """The explorer rows an entry's results belong to."""
    key = str(entry["trial"])
    linked = [tid for k in entry.get("linked") or [] if (tid := _lookup(index, str(k)))]
    if key.startswith("pooled:"):
        return list(dict.fromkeys(linked))
    own = _lookup(index, key)
    if own:
        return [own]
    return linked[:1]


def result_row(
    entry: Mapping[str, Any],
    value: Mapping[str, Any],
    trials: list[str],
    quote_allowed: Callable[[str], bool],
) -> dict[str, Any] | None:
    """One curated value as the page shows it, or None when it does not belong there."""
    if value.get("type") in EXCLUDED_TYPES or not carries_result(value):
        return None
    arms = {arm.get("id"): arm.get("label") for arm in entry.get("arms") or []}
    printed_arm = value.get("arm")
    row: dict[str, Any] = {"trials": trials, "arm": arms.get(printed_arm) or printed_arm}
    for field in (*DETAIL_FIELDS, *RESULT_FIELDS):
        if value.get(field) not in (None, "", []):
            row[field] = value[field]
    source = str(value.get("source") or "")
    if source:
        row["source"] = source
    cell = value.get("cell")
    if isinstance(cell, Mapping) and cell.get("table"):
        row["table"] = cell["table"]
    if value.get("derived"):
        row["derived"] = value["derived"]
    if str(entry["trial"]).startswith("pooled:"):
        row["pooled"] = True
    if value.get("quote") and source and quote_allowed(source):
        row["quote"] = value["quote"]
    return row


def quote_rule(
    licences: Mapping[str, str | None], pmcid_of: Mapping[str, str]
) -> Callable[[str], bool]:
    """Whether a source's text may be quoted: its paper is CC BY or CC0 in Europe PMC."""

    def allowed(source: str) -> bool:
        scheme, _, rest = source.partition(":")
        ident = rest.split("#", 1)[0]
        pmcid = ident if scheme == "pmc" else pmcid_of.get(ident) if scheme == "pmid" else None
        return bool(pmcid) and (licences.get(pmcid or "") or "").lower() in OPEN_LICENCES

    return allowed


def results_rows(
    entries: Iterable[Mapping[str, Any]],
    index: Mapping[str, str],
    quote_allowed: Callable[[str], bool],
) -> list[dict[str, Any]]:
    """Every value of every entry that belongs on the page, filed under its explorer rows."""
    rows: list[dict[str, Any]] = []
    for entry in entries:
        trials = explorer_trials(entry, index)
        if not trials:
            continue
        for value in entry.get("values") or []:
            row = result_row(entry, value, trials, quote_allowed)
            if row is not None:
                rows.append(row)
    return rows
