"""Rows for the Space's outcome, genetics and funding tables.

The Hugging Face Space offers three tables beside its trial explorer, all in one
file, ``data_pipeline.json``. Each row is a stored or curated record passed on as
it is, so every value on the page can be found again in the corpus:

- **Outcome arms**: every row of ``curation/topline-results.json``, the phase 3
  topline response rates from press releases and conference reports, each with
  its source. A placebo arm the source gives no dose or route for has none here.
- **GWAS associations**: every GWAS Catalog association ``vitiligo ingest gwas``
  stored. The catalog prints an odds ratio or a beta in one column and says
  which only through its interval text ("[0.22-0.29] unit decrease" is a beta).
  In the corpus 14 of 157 values are betas, so the value is passed on under the
  catalog's own heading, with that text, rather than labelled an odds ratio.
- **NIH awards**: every RePORTER award record whose project is about vitiligo
  by ``is_vitiligo_centred``, one row per award and fiscal year. RePORTER's
  search returns any mention, so 427 of the corpus's 735 records -- melanoma
  and autoimmunity grants that name vitiligo in passing -- are left out.
  Start and end dates are the record's own; a record without them has none.

Before this module the file was assembled by hand. Checked against the corpus
on 2026-11-21: 16 of its 22 outcome arms were these topline rows and 6 matched
no curated or posted result; its 30 associations and 25 award records were a
subset no rule reproduces; 12 of those awards were not vitiligo projects; and 9
carried a 2024-2028 timeline their records do not have.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from vitiligo.reports.funding import is_vitiligo_centred
from vitiligo.storage import GeneticAssociation, ResearchProject


def _compact(row: dict[str, Any]) -> dict[str, Any]:
    """Drop absent values; keep ``False`` and ``0``, which are values."""
    return {k: v for k, v in row.items() if v is not None and v != "" and v != []}


def _number(value: float) -> str:
    """A dose as written: 50.0 is 50, 1.5 stays 1.5."""
    return f"{value:g}"


def outcome_row(result: dict[str, Any]) -> dict[str, Any]:
    """One curated topline arm in the shape the Space's outcome table reads."""
    placebo = result.get("arm_role") == "placebo"
    dose = result.get("dose_value")
    regimen = " ".join(
        part
        for part in (
            _number(dose) if dose is not None else None,
            result.get("dose_unit"),
            result.get("frequency"),
        )
        if part
    )
    threshold = result.get("threshold")
    return _compact(
        {
            "trial": result["trial"],
            "agent": result.get("arm_label") if placebo else result.get("agent"),
            "regimen": regimen,
            "route": result.get("route"),
            "instrument": result.get("instrument"),
            "threshold": f"{threshold}%" if threshold is not None else None,
            "week": f"Wk {result['week']}",
            "n": result.get("n"),
            "percent": f"{result['percent']}%",
            "source": result.get("source"),
            "source_url": result.get("source_url"),
        }
    )


def association_row(association: GeneticAssociation) -> dict[str, Any]:
    """One GWAS Catalog association, with the statistics as the catalog printed them."""
    pmid = association.pubmed_id
    return _compact(
        {
            "variant": association.variant,
            "risk_allele": association.risk_allele,
            "mapped_gene": association.mapped_gene,
            "reported_genes": association.reported_genes,
            "p_value": association.p_value_text,
            "or_or_beta": association.odds_ratio_or_beta,
            "ci": association.confidence_interval,
            "trait": association.trait,
            "study": association.study_accession,
            "sample": association.initial_sample,
            "pubmed_id": pmid,
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
        }
    )


def award_row(project: ResearchProject) -> dict[str, Any]:
    """One RePORTER award record: one project in one fiscal year."""
    return _compact(
        {
            "award": project.source_id,
            "project": project.core_project_num,
            "fiscal_year": project.fiscal_year,
            "title": project.title,
            "pi": project.contact_pi,
            "org": project.organization,
            "agency": project.agency,
            "amount": project.award_amount,
            "active": project.is_active,
            "start": project.project_start,
            "end": project.project_end,
            "url": project.project_url,
        }
    )


def association_rows(associations: Iterable[GeneticAssociation]) -> list[dict[str, Any]]:
    """Every association, strongest first."""
    ranked = sorted(
        associations,
        key=lambda a: (a.p_value if a.p_value is not None else 1.0, a.variant, a.study_accession),
    )
    return [association_row(a) for a in ranked]


def award_rows(projects: Iterable[ResearchProject]) -> list[dict[str, Any]]:
    """The vitiligo-centred award records, newest fiscal year first."""
    kept = [p for p in projects if is_vitiligo_centred(p)]
    kept.sort(key=lambda p: (-(p.fiscal_year or 0), p.source_id))
    return [award_row(p) for p in kept]
