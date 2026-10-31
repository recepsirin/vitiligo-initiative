"""Tests for giving each country one name."""

from __future__ import annotations

import json
import unicodedata

import pytest

from vitiligo.trials.countries import _ALIASES, _REGIONS, normalize_countries, normalize_country


@pytest.mark.parametrize(
    ("written", "canonical"),
    [
        ("Turkey (Türkiye)", "Turkey"),
        ("Turkey", "Turkey"),
        ("Türkiye", "Turkey"),
        ("TÜRKIYE", "Turkey"),
        ("Iran (Islamic Republic of)", "Iran"),
        ("Iran, Islamic Republic Of", "Iran"),
        ("CHINA", "China"),
        ("Chinese", "China"),
        ("United States of America", "United States"),
        ("Korea, Republic of", "South Korea"),
        ("Czech Republic", "Czechia"),
    ],
)
def test_the_spellings_seen_in_the_corpus_resolve(written: str, canonical: str) -> None:
    """Each of these was a separate country in the store.

    The filter matches the stored string, so "Turkey" found one trial of the
    seven held and a reader could conclude Turkish vitiligo research barely
    exists.
    """
    assert normalize_country(written) == canonical


def test_an_accent_does_not_defeat_the_lookup() -> None:
    """Stripping everything outside a-z turns "Türkiye" into "trkiye".

    The first version of this table did exactly that, so the commonest
    spelling of the country — the one ClinicalTrials.gov uses — matched
    nothing.
    """
    assert normalize_country("Turkey (Türkiye)") == normalize_country("Turkey")


def test_every_canonical_name_is_ascii() -> None:
    """The country filter is a LIKE over serialised JSON.

    The serialiser escapes non-ASCII, so a canonical "Türkiye" is stored as
    "T\\u00fcrkiye" and a search for it matches nothing. This failed in the
    store before the canonical name was changed to its ASCII spelling.
    """
    for name in {*_ALIASES.values(), *_REGIONS.values()}:
        assert name.isascii(), f"{name!r} will not survive the country filter"
        assert json.dumps([name]) == json.dumps([name], ensure_ascii=False)


def test_a_region_does_not_double_its_country() -> None:
    """Two British trials list England beside the United Kingdom."""
    assert normalize_countries(["United Kingdom", "England"]) == ["United Kingdom"]
    assert normalize_countries(["England", "United Kingdom"]) == ["United Kingdom"]
    assert normalize_countries(["England"]) == ["United Kingdom"]


def test_variants_of_one_country_collapse_to_one_entry() -> None:
    assert normalize_countries(["Turkey (Türkiye)", "Turkey"]) == ["Turkey"]
    assert normalize_countries(["China", "CHINA", "Chinese"]) == ["China"]


def test_order_is_kept_and_unknown_names_are_left_alone() -> None:
    """A country absent from the table keeps the spelling its registry used.

    Inventing one would be worse: the table holds what was actually seen, and
    a name it has never met is more likely correct than guessed.
    """
    assert normalize_countries(["France", "Netherlands"]) == ["France", "Netherlands"]
    assert normalize_country("Ruritania") == "Ruritania"


@pytest.mark.parametrize("blank", ["", "   ", ",", None])
def test_nothing_is_not_a_country(blank) -> None:
    assert normalize_country(blank or "") is None


@pytest.mark.corpus
def test_the_store_holds_one_name_per_country(require_local_corpus) -> None:
    """No two strings in the store should fold to the same key.

    This is what the filter depends on, and it is the condition that was
    broken: seven spellings of four countries, splitting their trials.
    """
    import sqlite3

    from vitiligo.config import get_settings

    con = sqlite3.connect(f"file:{get_settings().resolved_db_path}?mode=ro", uri=True)
    names: set[str] = set()
    for (raw,) in con.execute("SELECT countries FROM trials"):
        names.update(json.loads(raw or "[]"))
    con.close()

    def fold(name: str) -> str:
        decomposed = unicodedata.normalize("NFKD", name.lower())
        return "".join(c for c in decomposed if c.isalpha() and not unicodedata.combining(c))

    seen: dict[str, str] = {}
    for name in sorted(names):
        key = fold(name)
        assert key not in seen or seen[key] == name, (
            f"{name!r} and {seen[key]!r} are the same country under two names"
        )
        seen[key] = name
        assert name.isascii(), f"{name!r} cannot be found by the country filter"
