"""Reproducible research reports (evidence-first, optionally LLM-enriched)."""

from vitiligo.reports.candidates import (
    CandidateReport,
    build_candidate_report,
    render_candidate_report_markdown,
    report_to_dict,
)

__all__ = [
    "CandidateReport",
    "build_candidate_report",
    "render_candidate_report_markdown",
    "report_to_dict",
]
