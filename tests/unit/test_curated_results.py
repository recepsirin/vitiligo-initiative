"""The checks every curated trial result must pass.

Each test is a way a transcribed number could be wrong and still look right:
a count changed by one, a quote paraphrased, a cell taken from the wrong row,
a percentage that does not match its count. The pilot also showed two ways a
right number can look wrong -- a count written as a word, a percentage a paper
truncates -- and the checks must pass those.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from vitiligo.storage import Document, SourceKind, session_scope
from vitiligo.trials.curated_results import Sources, compare, unmatched_primary, verify

ABSTRACT = (
    "Twenty-two children completed the study. Nineteen (86.4%) children showed some "
    "repigmentation at the end of 3 months (p = 0.013)."
)
TABLE = {
    "label": "Table 5",
    "caption": "Side effects",
    "header": ["", "Group A (total=23 patients)", "Group B (total=23 patients)"],
    "rows": [
        ["Pain", "18 (78.26%)", "20 (86.9%)"],
        ["Ulceration", "04 (17.39%)", "02 (8.69%)"],
        ["Total", "23", "23"],
    ],
}


def _store() -> None:
    with session_scope() as session:
        session.add(
            Document(source=SourceKind.PUBMED, source_id="1", title="A trial", abstract=ABSTRACT)
        )
        session.add(
            Document(source=SourceKind.PMC, source_id="PMC1", raw_metadata={"tables": [TABLE]})
        )


def _record(**value: Any) -> dict[str, Any]:
    base = {
        "arm": "A",
        "outcome": "any repigmentation",
        "type": "responders",
        "population": "as_observed",
        "source": "pmid:1#abstract",
        "quote": [
            "Twenty-two children completed the study.",
            "Nineteen (86.4%) children showed some repigmentation",
        ],
        "responders": 19,
        "n": 22,
        "percent": 86.4,
    }
    base.update(value)
    return {"trial": "pmid:1", "sources": ["pmid:1#abstract", "pmc:PMC1#table"], "values": [base]}


def _problems(record: dict[str, Any]) -> list[str]:
    with session_scope() as session:
        return verify(record, Sources(session))


def test_every_number_must_be_printed_in_its_quotes_in_digits_or_words(test_db_path: Path) -> None:
    _store()
    assert _problems(_record()) == []
    # 38 of 44 is 86.4% too: arithmetic alone would pass it, but neither is printed.
    assert _problems(_record(responders=38, n=44))
    assert _problems(_record(responders=38, n=44, derived=["responders", "n"])) == []


def test_numbers_are_read_as_papers_print_them(test_db_path: Path) -> None:
    """A count in words past ninety-nine, a range after a percent sign, a spread after +/-."""
    text = (
        "One hundred thirty-five patients were included. Total depigmentation was "
        "achieved in 11 of the 16 patients (69%; 95% CI, 41%-89%). The mean dose was "
        "3.93+/-0.59 J/cm2."
    )
    with session_scope() as session:
        session.add(Document(source=SourceKind.PUBMED, source_id="2", title="A", abstract=text))
    record = _record(
        source="pmid:2#abstract",
        quote=["One hundred thirty-five patients were included.", text.split(". ")[1]],
        responders=11,
        n=16,
        percent=69,
        ci_low=41,
        ci_high=89,
    )
    record["sources"] = ["pmid:2#abstract"]
    assert _problems(record) == []
    counted = _record(source="pmid:2#abstract", quote=text.split(". ")[0], responders=None, n=135)
    counted["values"][0]["percent"] = None
    counted["sources"] = ["pmid:2#abstract"]
    assert _problems(counted) == []
    dose = _record(source="pmid:2#abstract", quote="3.93+/-0.59", responders=None, n=None)
    dose["values"][0].update(percent=None, mean=3.93, se=0.59)
    dose["sources"] = ["pmid:2#abstract"]
    assert _problems(dose) == []


def test_a_quote_must_be_in_the_source_the_trial_lists(test_db_path: Path) -> None:
    _store()
    # Every number is still there; only the words are not the source's.
    paraphrased = _record(
        quote=["Twenty-two children completed the study.", "Nineteen (86.4%) children improved"]
    )
    assert _problems(paraphrased)
    unlisted = _record()
    unlisted["sources"] = ["pmc:PMC1#table"]
    assert _problems(unlisted)


def test_a_p_value_must_be_printed_as_written(test_db_path: Path) -> None:
    """A p is kept as text ("< .001"), so the number checks never saw it."""
    _store()
    quote = [
        "Twenty-two children completed the study.",
        "Nineteen (86.4%) children showed some repigmentation at the end of 3 months (p = 0.013)",
    ]
    assert _problems(_record(quote=quote, p="= 0.013")) == []
    assert _problems(_record(quote=quote, p="= 0.0013"))
    # A digit dropped: 0.01 is inside the printed 0.013, but it is not what is printed.
    assert _problems(_record(quote=quote, p="= 0.01"))


def test_a_percentage_must_match_its_count_to_the_last_printed_place(test_db_path: Path) -> None:
    """20 of 23 is 86.96%; the paper truncates it to 86.9, which must pass."""
    _store()

    def pain(cell: str, row: int, responders: int, percent: float) -> dict[str, Any]:
        return _record(
            source="pmc:PMC1#table",
            quote=[cell, "23"],
            cell=[
                {
                    "table": "Table 5",
                    "row": row,
                    "column": 2,
                    "row_label": "Pain" if row == 0 else "Ulceration",
                },
                {"table": "Table 5", "row": 2, "column": 2, "row_label": "Total"},
            ],
            responders=responders,
            n=23,
            percent=percent,
        )

    assert _problems(pain("20 (86.9%)", 0, 20, 86.9)) == []
    assert _problems(pain("02 (8.69%)", 1, 2, 8.69)) == []
    misplaced = pain("02 (8.69%)", 1, 2, 86.9)  # a percentage ten times its count's
    misplaced["values"][0]["derived"] = ["percent"]
    assert _problems(misplaced)


def test_a_table_value_must_be_in_the_row_and_column_it_names(test_db_path: Path) -> None:
    _store()
    value = {
        "source": "pmc:PMC1#table",
        "quote": ["18 (78.26%)", "23"],
        "cell": [
            {
                "table": "Table 5",
                "row": 0,
                "column": 1,
                "row_label": "Pain",
                "column_label": "Group A (total=23 patients)",
            },
            {"table": "Table 5", "row": 2, "column": 1, "row_label": "Total"},
        ],
        "responders": 18,
        "n": 23,
        "percent": 78.26,
    }
    assert _problems(_record(**value)) == []
    wrong_row = copy.deepcopy(value)
    wrong_row["cell"][0]["row_label"] = "Ulceration"
    assert _problems(_record(**wrong_row))
    wrong_column = copy.deepcopy(value)
    wrong_column["cell"][0]["column_label"] = "Group B (total=23 patients)"
    assert _problems(_record(**wrong_column))


def test_a_blind_reading_is_paired_with_the_first_wherever_the_first_filed_it() -> None:
    # The first reader filed a paper's table cell under its registry record; the
    # second read the same number from the body. The pair must still be found,
    # and a field read differently told apart from one only one reader recorded.
    arms = [{"id": "A", "role": "active"}, {"id": "B", "role": "control"}]
    sources = ["pmid:1#abstract", "pmc:PMC1#body", "pmc:PMC1#table"]

    def record(trial: str, randomised: str, values: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "trial": trial,
            "sources": sources,
            "design": {"randomised": randomised},
            "population": {"n_enrolled": 40},
            "arms": arms,
            "values": values,
        }

    count = {"arm": "A", "type": "responders", "responders": 12, "n": 20, "percent": 60}
    first = [
        record(
            "NCT1", "yes", [count | {"source": "pmc:PMC1#table", "population": "nri", "weeks": 12}]
        ),
        record("pmid:1", "yes", []),
    ]
    second = [
        record(
            "pmid:1",
            "not reported",
            [
                count | {"source": "pmc:PMC1#body", "population": "as_observed"},
                {
                    "source": "pmid:1#abstract",
                    "arm": "B",
                    "type": "responders",
                    "responders": 5,
                    "n": 20,
                },
            ],
        )
    ]
    result = compare(first, second)
    assert (result.first, result.second, result.paired) == (1, 2, 1)
    assert result.value_fields["percent"] == [1, 0, 0]
    assert result.value_fields["population"] == [0, 1, 0]
    assert result.value_fields["weeks"] == [0, 0, 1]
    assert result.trial_fields["randomised"] == [0, 1, 0]


def test_a_registry_primary_number_is_found_in_the_paper_as_printed() -> None:
    # The registry posts -19.12 % change; the paper prints a 19.1 % improvement.
    # That is the same number; 25.8 is not in the paper; a secondary is not checked.
    posted = {
        "outcomes": [
            {
                "type": "PRIMARY",
                "title": "T-VASI change",
                "measurements": [{"value": "-19.12"}, {"value": "2.29"}, {"value": "25.8"}],
            },
            {"type": "SECONDARY", "title": "DLQI", "measurements": [{"value": "7.4"}]},
        ]
    }
    curated = [{"values": [{"mean": 19.1}, {"mean": -2.3}]}]
    assert unmatched_primary(posted, curated) == [("T-VASI change", 3, ["25.8"])]
