"""Trial results read out of papers, and the checks every number must pass.

The rules are ``curation/trial-results-guideline.md``. Each line of
``curation/trial-results.jsonl`` is one trial: its design, population and arms,
and its values -- each one number, with the source it is printed in and the
words or table cell it is printed as. Nothing here trusts the reader that
wrote the file. :func:`verify` re-reads every cited source from the store and
rejects a value whose quote is not there, whose numbers are not in its quote
unless declared derived, or whose arithmetic does not hold.

A source is cited as ``scheme:id#part``:

- ``pmid:12345678#abstract`` -- a PubMed record's title and abstract
- ``doi:10.1000/x#abstract`` -- a Crossref record's title and abstract
- ``pmc:PMC1234567#body`` -- a PMC article's full text
- ``pmc:PMC1234567#table`` -- one of its tables; the value names the table's
  label, the row and the column, and quotes the cell
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from vitiligo.reports.paper_results import norm as paper_norm
from vitiligo.storage import Document, SourceKind

CURATION = Path("curation/trial-results.jsonl")
POPULATIONS = frozenset({"nri", "as_observed", "locf", "per_lesion", "not_reported"})
NUMERIC = (
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
    "ci_level",
)
# A p value is kept as printed ("< .001"); its number must be printed as written.
_P_NUMBER = re.compile(r"\d*\.?\d+")
# A hyphen after a percent sign is a range ("41%-89%"), not a minus.
_NUMBER = re.compile(r"(?<![\w.%])-?\d+(?:\.\d+)?")


def norm(text: str) -> str:
    """Text as compared: the curation's normal form, with a middle dot read as a point."""
    return paper_norm(text).replace("\u00b7", ".")


_UNITS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_WORDS = {word: n for n, word in enumerate(_UNITS)} | {w: 20 + 10 * i for i, w in enumerate(_TENS)}
_WORD_NUMBER = re.compile(
    r"\b("
    + "|".join(_TENS)
    + r")(?:[- ]("
    + "|".join(_UNITS[1:10])
    + r"))?\b|\b("
    + "|".join(_UNITS)
    + r")\b",
    re.IGNORECASE,
)


_BELOW_100 = (
    r"(?:("
    + "|".join(_TENS)
    + r")(?:[- ]("
    + "|".join(_UNITS[1:10])
    + r"))?|("
    + "|".join(_UNITS)
    + r"))"
)
# "One hundred thirty-five patients": a count that opens a sentence.
_HUNDREDS = re.compile(
    r"\b(" + "|".join(_UNITS[1:10]) + r")[- ]hundred(?:[- ]and)?(?:[- ]" + _BELOW_100 + r")?\b",
    re.IGNORECASE,
)


def numbers_in(text: str) -> list[float]:
    """Every number a text prints, in digits or, as papers often write counts, in words."""
    # "3.93+/-0.59" is a mean and its spread, not 3.93 and -0.59.
    text = norm(text).replace("+/-", " ± ")
    found = [float(m) for m in _NUMBER.findall(text.replace(",", ""))]
    for match in _WORD_NUMBER.finditer(text):
        tens, unit, alone = match.groups()
        if alone:
            found.append(float(_WORDS[alone.lower()]))
        else:
            found.append(float(_WORDS[tens.lower()] + (_WORDS[unit.lower()] if unit else 0)))
    for match in _HUNDREDS.finditer(text):
        hundreds, tens, unit, alone = match.groups()
        rest = _WORDS[tens.lower()] + (_WORDS[unit.lower()] if unit else 0) if tens else 0
        found.append(
            float(100 * _WORDS[hundreds.lower()] + (rest or _WORDS.get((alone or "").lower(), 0)))
        )
    return found


def quotes_of(value: dict[str, Any]) -> list[str]:
    """A value's quotes: one passage, or several when its numbers are printed apart."""
    quote = value.get("quote")
    return [str(q) for q in quote] if isinstance(quote, list) else [str(quote or "")]


@dataclass(frozen=True)
class Table:
    label: str
    caption: str
    header: list[str]
    rows: list[list[str]]


class Sources:
    """The texts a record may cite, read from the store once each."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[str, Document | None] = {}

    def _document(self, scheme: str, ident: str) -> Document | None:
        key = f"{scheme}:{ident}"
        if key not in self._cache:
            if scheme == "pmid":
                query = select(Document).where(
                    Document.source == SourceKind.PUBMED, Document.source_id == ident
                )
            elif scheme == "doi":
                query = select(Document).where(
                    Document.source == SourceKind.CROSSREF, Document.source_id == ident
                )
            elif scheme == "pmc":
                query = select(Document).where(
                    Document.source == SourceKind.PMC, Document.source_id == ident
                )
            else:
                return None
            self._cache[key] = self._session.exec(query).first()
        return self._cache[key]

    def text(self, pointer: str) -> str | None:
        """The text a pointer names, or None if the store does not hold it."""
        scheme, _, rest = pointer.partition(":")
        ident, _, part = rest.partition("#")
        doc = self._document(scheme, ident)
        if doc is None:
            return None
        if part == "abstract":
            return f"{doc.title or ''}\n{doc.abstract or ''}"
        if part == "body":
            return str((doc.raw_metadata or {}).get("full_text") or "") or None
        return None

    def tables(self, pointer: str) -> list[Table]:
        scheme, _, rest = pointer.partition(":")
        doc = self._document(scheme, rest.partition("#")[0])
        raw = (doc.raw_metadata or {}).get("tables") if doc is not None else None
        return [
            Table(
                str(t.get("label") or ""),
                str(t.get("caption") or ""),
                t.get("header") or [],
                t.get("rows") or [],
            )
            for t in raw or []
        ]


def _cell(sources: Sources, pointer: str, cell: dict[str, Any]) -> tuple[str, str, str] | None:
    """The cited cell as printed, with its row's first cell and its column's header."""
    for table in sources.tables(pointer):
        if norm(table.label) != norm(str(cell.get("table") or "")):
            continue
        row, column = cell.get("row"), cell.get("column")
        if isinstance(row, int) and isinstance(column, int) and 0 <= row < len(table.rows):
            cells = table.rows[row]
            if 0 <= column < len(cells):
                header = table.header[column] if column < len(table.header) else ""
                return cells[column], cells[0], header
    return None


def _percent_tolerance(value: float) -> float:
    """One unit of the last printed place.

    Papers round or truncate: one prints 20 of 23 (86.96%) as 86.9. A unit
    of the last place accepts both and still rejects a misplaced point --
    1 of 13 printed as 77% rather than 7.7%.
    """
    if float(value).is_integer():
        return 1.0
    return 10.0 ** -len(repr(float(value)).split(".")[1])


def verify(record: dict[str, Any], sources: Sources) -> list[str]:
    """Every way the record fails the guideline's checks; empty when it passes."""
    problems: list[str] = []
    cited = set(record.get("sources") or [])
    for index, value in enumerate(record.get("values") or []):
        where = f"value {index} ({value.get('arm')}, {value.get('outcome')})"
        pointer = str(value.get("source") or "")
        if pointer not in cited:
            problems.append(f"{where}: {pointer!r} is not among the trial's sources")
        quotes = quotes_of(value)
        if "cell" in value:
            # A value may cite several cells -- a count and, elsewhere in the
            # table, its denominator -- each with the quote at the same place.
            cells = value["cell"] if isinstance(value["cell"], list) else [value["cell"]]
            if len(cells) != len(quotes):
                problems.append(f"{where}: {len(cells)} cells but {len(quotes)} quotes")
            for cell, quote in zip(cells, quotes, strict=False):
                printed = _cell(sources, pointer, cell)
                if printed is None or norm(printed[0]) != norm(quote):
                    problems.append(f"{where}: the cited cell does not read {quote!r}")
                    continue
                # A cell is only the number it says if it is in the row and
                # column the reader named.
                if "row_label" in cell and norm(str(cell["row_label"])) != norm(printed[1]):
                    problems.append(
                        f"{where}: its row reads {printed[1]!r}, not {cell['row_label']!r}"
                    )
                if "column_label" in cell and norm(str(cell["column_label"])) != norm(printed[2]):
                    problems.append(
                        f"{where}: its column reads {printed[2]!r}, not {cell['column_label']!r}"
                    )
        else:
            text = sources.text(pointer)
            if text is None:
                problems.append(f"{where}: {pointer} is not in the store")
            else:
                for quote in quotes:
                    if not quote or norm(quote) not in norm(text):
                        problems.append(f"{where}: quote not in {pointer}: {quote[:60]!r}")
        derived = set(value.get("derived") or [])
        printed_numbers = [x for quote in quotes for x in numbers_in(quote)]
        for name in NUMERIC:
            number = value.get(name)
            if number is None or name in derived:
                continue
            if not any(abs(float(number) - x) < 1e-9 for x in printed_numbers):
                problems.append(f"{where}: {name} {number} is not printed in its quote")
        responders, n, percent = value.get("responders"), value.get("n"), value.get("percent")
        if responders is not None and n is not None:
            if responders > n:
                problems.append(f"{where}: {responders} responders of {n}")
            elif (
                percent is not None
                and n
                and abs(percent - 100 * responders / n) > _percent_tolerance(percent)
            ):
                problems.append(f"{where}: {percent}% is not {responders} of {n}")
        p = value.get("p")
        if p is not None and "p" not in derived:
            token = _P_NUMBER.search(str(p))
            quoted = " ".join(norm(quote) for quote in quotes)
            if token is None or not re.search(rf"(?<!\d){re.escape(token.group())}(?!\d)", quoted):
                problems.append(f"{where}: p {p} is not printed in its quote")
        if value.get("population") not in POPULATIONS:
            problems.append(
                f"{where}: population {value.get('population')!r} is not one of {sorted(POPULATIONS)}"
            )
    for domain, item in (record.get("rob") or {}).items():
        quote = str(item.get("quote") or "")
        if quote:
            text = sources.text(str(item.get("source") or "")) or ""
            if norm(quote) not in norm(text):
                problems.append(f"risk of bias, {domain}: its quote is not in {item.get('source')}")
    return problems


def records(path: Path = CURATION) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


REGISTRY = Path("curation/registry-results.jsonl")


def registry_results(session: Session) -> list[dict[str, Any]]:
    """Every registered vitiligo trial's posted ClinicalTrials.gov results.

    A registry posting with structured results is parsed by code, not read:
    each measurement stays as posted, with its group's title and the
    registry's own words on how missing participants were counted.
    """
    from dataclasses import asdict

    from vitiligo.reports.jak import parse_ctgov_adverse_events, parse_ctgov_outcomes
    from vitiligo.storage import Trial, TrialSourceKind

    posted = []
    for trial in session.exec(select(Trial).where(Trial.source == TrialSourceKind.CTGOV)):
        meta = trial.raw_metadata or {}
        study = meta.get("study") or {}
        if meta.get("scope") or not study.get("resultsSection"):
            continue
        events = parse_ctgov_adverse_events(study)
        posted.append(
            {
                "trial": trial.source_id,
                "title": trial.brief_title or trial.official_title or "",
                "outcomes": [asdict(o) for o in parse_ctgov_outcomes(study)],
                "adverse_events": asdict(events) if events else None,
            }
        )
    return sorted(posted, key=lambda item: item["trial"])


def unmatched_primary(
    posted: dict[str, Any], curated: list[dict[str, Any]]
) -> list[tuple[str, int, list[str]]]:
    """Each primary outcome the registry posts: its numbers, and those no paper value carries.

    A number is carried at the precision the paper prints it -- 29.75 posted
    is 29.8 printed -- and whatever its sign, since a paper's "improvement" is
    a registry's negative "change".
    """
    printed = {
        abs(x) for record in curated for v in record.get("values") or [] for _, x in _numbers(v)
    }
    tally = []
    for outcome in posted["outcomes"]:
        if str(outcome.get("type") or "").upper() != "PRIMARY":
            continue
        numbers = []
        for measurement in outcome["measurements"]:
            try:
                numbers.append((float(measurement["value"]), str(measurement["value"])))
            except (TypeError, ValueError):
                continue
        missing = [
            text
            for number, text in numbers
            if not any(abs(abs(number) - x) <= _percent_tolerance(x) / 2 + 1e-9 for x in printed)
        ]
        tally.append((str(outcome["title"]), len(numbers), missing))
    return tally


BLIND = Path("curation/trial-results-blind.jsonl")
# Numbers specific enough to pair two readings of one value; n and the CI
# level are shared by too many values to pair on alone.
_KEYS = frozenset(NUMERIC) - {"n", "ci_level"}
_VALUE_FIELDS = ("role", "type", "population", "weeks", "threshold", "p", "subgroup", *NUMERIC)


def _numbers(value: dict[str, Any]) -> set[tuple[str, float]]:
    return {
        (name, float(x))
        for name in NUMERIC
        if isinstance(x := value.get(name), int | float) and not isinstance(x, bool)
    }


def _category(text: Any) -> str:
    """The first word of a design answer: "no (left-right)" is "no"."""
    text = str(text or "not reported").lower()
    kinds = ("not applicable", "not reported", "quasi", "yes", "no")
    return next((kind for kind in kinds if text.startswith(kind)), text)


_TRIAL_FIELDS: dict[str, Any] = {
    "a treatment trial": lambda r: _category(r["design"].get("randomised")) != "not applicable",
    "randomised": lambda r: _category(r["design"].get("randomised")),
    "within-patient unit": lambda r: (r["design"].get("unit") or "patient") != "patient",
    "enrolled": lambda r: r["population"].get("n_enrolled"),
    "arms": lambda r: len(r.get("arms") or []),
}


def _field(value: dict[str, Any], name: str, roles: dict[str, str]) -> Any:
    if name == "role":
        return roles.get(str(value.get("arm")))
    if name == "subgroup":
        return bool(value.get("subgroup"))
    if name == "p":
        text = str(value.get("p") or "").replace("·", ".")
        number = _P_NUMBER.search(text)
        relation = next((sign for sign in "<>≤≥" if sign in text), "=")
        return (relation, float(number.group())) if number else None
    return value.get(name)


@dataclass
class Agreement:
    """A blind second extraction against the first, field by field.

    Values are paired on the numbers they share, among the sources the second
    reader read, wherever the first reader filed them (a congress abstract's
    values may sit under its trial's registry record). Each field is tallied as
    [agree, differ, recorded by one reader only].
    """

    trials: int = 0
    trial_fields: dict[str, list[int]] = field(default_factory=dict)
    value_fields: dict[str, list[int]] = field(default_factory=dict)
    first: int = 0
    second: int = 0
    paired: int = 0
    first_qualitative: int = 0
    second_qualitative: int = 0
    paired_qualitative: int = 0


def compare(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> Agreement:
    def tally(table: dict[str, list[int]], name: str, a: Any, b: Any) -> None:
        row = table.setdefault(name, [0, 0, 0])
        row[0 if a == b else 1 if a is not None and b is not None else 2] += 1

    one_by_trial = {r["trial"]: r for r in first}
    by_source: dict[str, list[tuple[dict[str, Any], dict[str, str]]]] = {}
    for record in first:
        roles = {a["id"]: a["role"] for a in record.get("arms") or []}
        for value in record.get("values") or []:
            by_source.setdefault(value["source"], []).append((value, roles))
    out = Agreement()
    for record in second:
        one = one_by_trial.get(record["trial"])
        if one is None:
            continue
        out.trials += 1
        for name, get in _TRIAL_FIELDS.items():
            tally(out.trial_fields, name, get(one), get(record))
        roles = {a["id"]: a["role"] for a in record.get("arms") or []}
        # One number may be cited from the abstract, the body or a table cell.
        ones = [pair for source in set(record["sources"]) for pair in by_source.get(source, [])]
        free = [(v, r) for v, r in ones if _numbers(v)]
        out.first += len(free)
        out.first_qualitative += len(ones) - len(free)
        quoted = {norm(q) for v, _ in ones if not _numbers(v) for q in quotes_of(v)}
        for two in record.get("values") or []:
            numbers = _numbers(two)
            if not numbers:
                out.second_qualitative += 1
                out.paired_qualitative += any(norm(q) in quoted for q in quotes_of(two))
                continue
            out.second += 1
            keys = {pair for pair in numbers if pair[0] in _KEYS}
            best = max(
                free,
                key=lambda pair: (len(keys & _numbers(pair[0])), len(numbers & _numbers(pair[0]))),
                default=None,
            )
            if best is None or not keys & _numbers(best[0]):
                continue
            free.remove(best)
            out.paired += 1
            for name in _VALUE_FIELDS:
                a, b = _field(best[0], name, best[1]), _field(two, name, roles)
                if a is not None or b is not None:
                    tally(out.value_fields, name, a, b)
    return out


def worklist(session: Session) -> list[dict[str, Any]]:
    """Every distinct vitiligo trial and the sources its results could be in.

    A trial known only from its paper has that paper: its PubMed or Crossref
    abstract, and the PMC article's body and tables when the store holds
    them. A registered trial has the papers whose abstract gives its registry
    id, as a trial's own report does, with their bodies and tables; a paper
    that only mentions the id in its body is citing the trial, not reporting
    it (TRuE-V2's id is in 22 such bodies). Ordered so that trials with tables
    come first, then those PubMed indexes as clinical trials, then the rest.
    """
    from vitiligo.storage import Trial, TrialSourceKind

    pmc_by_pmid: dict[str, Document] = {}
    texts: list[tuple[str, str]] = []  # (pmid, abstract) to search for registry ids
    pubmed: dict[str, Document] = {}
    for doc in session.exec(select(Document)):
        meta = doc.raw_metadata or {}
        if doc.source == SourceKind.PMC:
            if meta.get("pmid"):
                pmc_by_pmid[str(meta["pmid"])] = doc
        elif doc.source == SourceKind.PUBMED:
            pubmed[doc.source_id] = doc
            texts.append((doc.source_id, f"{doc.title or ''}\n{doc.abstract or ''}"))

    def paper(pmid: str) -> list[str]:
        pointers = [f"pmid:{pmid}#abstract"] if pmid in pubmed else []
        pmc = pmc_by_pmid.get(pmid)
        if pmc is not None:
            meta = pmc.raw_metadata or {}
            if meta.get("full_text"):
                pointers.append(f"pmc:{pmc.source_id}#body")
            if meta.get("tables"):
                pointers.append(f"pmc:{pmc.source_id}#table")
        return pointers

    trials = list(session.exec(select(Trial)))
    registered = {
        t.source_id: t
        for t in trials
        if t.source != TrialSourceKind.PUBLICATION and not (t.raw_metadata or {}).get("scope")
    }
    cited: dict[str, set[str]] = {}
    if registered:
        pattern = re.compile(
            "|".join(re.escape(i) for i in sorted(registered, key=len, reverse=True))
        )
        for pmid, text in texts:
            for match in set(pattern.findall(text)):
                cited.setdefault(match, set()).add(pmid)

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for trial in trials:
        meta = trial.raw_metadata or {}
        if trial.source == TrialSourceKind.PUBLICATION:
            if meta.get("scope") != "published_only":
                continue
            pmid, doi = str(meta.get("pmid") or ""), str(meta.get("doi") or "")
            ident = f"pmid:{pmid}" if pmid else f"doi:{doi or trial.source_id}"
            sources = paper(pmid) if pmid else [f"doi:{doi or trial.source_id}#abstract"]
            types = set(pubmed[pmid].publication_types or []) if pmid in pubmed else set()
        elif trial.source_id in registered:
            ident = trial.source_id
            sources = []
            for pmid in sorted(cited.get(trial.source_id, ())):
                sources.extend(paper(pmid))
            sources = list(dict.fromkeys(sources))
            types = set()
        else:
            continue
        # A trial held twice -- ISRCTN17160087 is both an ISRCTN and an ICTRP
        # record -- is one trial.
        if not sources or ident in seen:
            continue
        seen.add(ident)
        rank = 0 if any(s.endswith("#table") for s in sources) else 1 if types & _TRIAL_TYPES else 2
        items.append(
            {
                "trial": ident,
                "title": trial.official_title or trial.brief_title or "",
                "sources": sources,
                "rank": rank,
            }
        )
    items.sort(key=lambda item: (item["rank"], item["trial"]))
    return items


_TRIAL_TYPES = frozenset(
    {
        "Randomized Controlled Trial",
        "Clinical Trial",
        "Controlled Clinical Trial",
        "Clinical Trial, Phase II",
        "Clinical Trial, Phase III",
    }
)


def render(sources: Sources, pointers: list[str]) -> str:
    """A trial's sources as read while curating, table rows and columns numbered."""
    out: list[str] = []
    for pointer in pointers:
        out.append(f"===== {pointer}")
        if pointer.endswith("#table"):
            for table in sources.tables(pointer):
                out.append(f"--- {table.label}: {table.caption}")
                out.append(
                    "    header: " + " | ".join(f"[{i}] {h}" for i, h in enumerate(table.header))
                )
                for r, row in enumerate(table.rows):
                    out.append(
                        f"    row {r}: " + " | ".join(f"[{c}] {cell}" for c, cell in enumerate(row))
                    )
        else:
            out.append(sources.text(pointer) or "(not in the store)")
    return "\n".join(out)
