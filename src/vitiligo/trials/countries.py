"""One name per country, so a filter by country finds the trials in it.

Registries write the same place several ways. ClinicalTrials.gov records
Turkey as "Turkey (Türkiye)" after the UN name change; ICTRP's partners write
"Turkey". The country filter matches the stored string exactly, so a search
for Turkey returned one trial of the seven held — and a reader would
reasonably conclude Turkish vitiligo research barely exists.

The same splits Iran across three spellings, China across three, the United
States across two and Korea across two. Two British trials list "England"
beside "United Kingdom", which is not a variant but a region inside a country
already named, and counting it doubles them.

This is a lookup table rather than a library because the set is small, closed
and worth reading: every entry here was seen in the corpus, and a dependency
that knew every country in the world would still not know that ITMCTR writes
"Chinese" in the field.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# What a registry wrote, against the name this project uses. Keys are matched
# after case-folding, stripping punctuation and folding accents, so "Iran,
# Islamic Republic Of" and "Iran (Islamic Republic of)" both arrive as
# "iranislamicrepublicof".
#
# Every canonical name is ASCII. The country filter is a LIKE over the
# serialised JSON, and the serialiser escapes non-ASCII, so "Türkiye" is
# stored as "T\u00fcrkiye" and a search for it matches nothing. Turkey's UN
# name is Türkiye and this is not the place to argue otherwise; it is the
# place where a name has to survive being written to SQLite and read back by
# a string match.
_ALIASES: dict[str, str] = {
    "turkey": "Turkey",
    "turkeyturkiye": "Turkey",
    "turkiye": "Turkey",
    "iranislamicrepublicof": "Iran",
    "iran": "Iran",
    "china": "China",
    "chinese": "China",
    "peoplesrepublicofchina": "China",
    "unitedstatesofamerica": "United States",
    "unitedstates": "United States",
    "usa": "United States",
    "korearepublicof": "South Korea",
    "republicofkorea": "South Korea",
    "southkorea": "South Korea",
    "czechrepublic": "Czechia",
    "czechia": "Czechia",
    "russianfederation": "Russia",
    "vietnam": "Viet Nam",
    "viennam": "Viet Nam",
}

# Regions written in a country field. Dropped when the country they belong to
# is already listed, kept as that country when it is not.
_REGIONS: dict[str, str] = {
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northernireland": "United Kingdom",
    "greatbritain": "United Kingdom",
    "hongkong": "China",
    "taiwanprovinceofchina": "Taiwan",
}


def _key(name: str) -> str:
    """A comparison key with case, punctuation and accents removed.

    The accents matter: stripping every character outside a-z turns
    "Turkey (Türkiye)" into "turkeyrkiye", which matches nothing, so the
    commonest spelling of the country went unrecognised by the first version
    of this table.
    """
    folded = unicodedata.normalize("NFKD", name.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", folded)


def normalize_country(name: str) -> str | None:
    """The name this project uses for a country a registry named.

    Returns ``None`` for an empty value. A country not in the table is
    returned with its surrounding whitespace stripped and nothing else
    changed, because inventing a spelling is worse than keeping theirs.
    """
    cleaned = re.sub(r"\s+", " ", (name or "")).strip().strip(",;")
    if not cleaned:
        return None
    key = _key(cleaned)
    if key in _ALIASES:
        return _ALIASES[key]
    if key in _REGIONS:
        return _REGIONS[key]
    return cleaned


def normalize_countries(names: Iterable[str]) -> list[str]:
    """Canonical country names, in first-seen order, without repeats.

    A region is dropped when its country is present either way round, so
    ["United Kingdom", "England"] and ["England", "United Kingdom"] both give
    ["United Kingdom"].
    """
    out: list[str] = []
    for raw in names or ():
        name = normalize_country(str(raw))
        if name and name not in out:
            out.append(name)
    regions = {_REGIONS[_key(str(r))] for r in (names or ()) if _key(str(r)) in _REGIONS}
    for country in regions:
        if out.count(country) > 1:  # pragma: no cover - deduped above
            out.remove(country)
    return out
