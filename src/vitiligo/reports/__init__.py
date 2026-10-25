"""Reproducible research reports, computed from stored records."""

from vitiligo.reports.candidates import (
    CandidateReport,
    build_candidate_report,
    render_candidate_report_markdown,
    report_to_dict,
)
from vitiligo.reports.jak import (
    JakAtlas,
    atlas_to_dict,
    build_jak_atlas,
    render_jak_atlas_markdown,
    write_jak_atlas_csv,
)

__all__ = [
    "CandidateReport",
    "JakAtlas",
    "atlas_to_dict",
    "build_candidate_report",
    "build_jak_atlas",
    "render_candidate_report_markdown",
    "render_jak_atlas_markdown",
    "report_to_dict",
    "write_jak_atlas_csv",
]
