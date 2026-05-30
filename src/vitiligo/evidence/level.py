"""Derive evidence-level tags from document metadata and trial registry fields."""

from __future__ import annotations

from enum import StrEnum

from vitiligo.storage import Document, Trial


class EvidenceLevel(StrEnum):
    """Canonical evidence tiers surfaced in search, Ask, and Hypothesize."""

    RCT = "rct"
    CLINICAL_TRIAL = "clinical_trial"
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    COHORT = "cohort"
    CASE_SERIES = "case_series"
    CASE_REPORT = "case_report"
    REVIEW = "review"
    MOUSE = "mouse"
    IN_VITRO = "in_vitro"
    OTHER = "other"
    UNKNOWN = "unknown"


_DISPLAY_LABELS: dict[EvidenceLevel, str] = {
    EvidenceLevel.RCT: "RCT",
    EvidenceLevel.CLINICAL_TRIAL: "Clinical trial",
    EvidenceLevel.META_ANALYSIS: "Meta-analysis",
    EvidenceLevel.SYSTEMATIC_REVIEW: "Systematic review",
    EvidenceLevel.COHORT: "Cohort / observational",
    EvidenceLevel.CASE_SERIES: "Case series",
    EvidenceLevel.CASE_REPORT: "Case report",
    EvidenceLevel.REVIEW: "Review",
    EvidenceLevel.MOUSE: "Mouse / animal",
    EvidenceLevel.IN_VITRO: "In vitro",
    EvidenceLevel.OTHER: "Other",
    EvidenceLevel.UNKNOWN: "Unknown",
}


def evidence_level_label(level: EvidenceLevel | str) -> str:
    if isinstance(level, str):
        try:
            level = EvidenceLevel(level)
        except ValueError:
            return level
    return _DISPLAY_LABELS.get(level, level.value)


def classify_document(doc: Document) -> EvidenceLevel:
    """Classify a paper using PubMed publication types, MeSH, and title/abstract cues."""
    if doc.journal == "NCBI GEO" or _source_value(doc) == "geo":
        return _classify_geo_document(doc)

    types_text = " | ".join(doc.publication_types or []).lower()
    mesh_text = " | ".join(doc.mesh_terms or []).lower()
    title = (doc.title or "").lower()
    abstract = (doc.abstract or "").lower()
    text = f"{title} {abstract}"

    if "meta-analysis" in types_text or "meta analysis" in types_text:
        return EvidenceLevel.META_ANALYSIS
    if "systematic review" in types_text:
        return EvidenceLevel.SYSTEMATIC_REVIEW
    if _is_rct(types_text, text):
        return EvidenceLevel.RCT
    if "case reports" in types_text or "case report" in types_text:
        return EvidenceLevel.CASE_REPORT
    if "case series" in types_text or "case series" in title:
        return EvidenceLevel.CASE_SERIES
    if "review" in types_text and "systematic review" not in types_text:
        return EvidenceLevel.REVIEW
    if _is_cohort(types_text, mesh_text):
        return EvidenceLevel.COHORT
    if _is_in_vitro(mesh_text, text):
        return EvidenceLevel.IN_VITRO
    if _is_mouse(mesh_text, text, types_text):
        return EvidenceLevel.MOUSE
    if doc.publication_types:
        return EvidenceLevel.OTHER
    return EvidenceLevel.UNKNOWN


def classify_trial(trial: Trial) -> EvidenceLevel:
    """Classify a registered trial record."""
    study_type = (trial.study_type or "").upper()
    if study_type == "OBSERVATIONAL":
        return EvidenceLevel.COHORT
    if study_type == "INTERVENTIONAL":
        return EvidenceLevel.CLINICAL_TRIAL
    return EvidenceLevel.UNKNOWN


def _source_value(doc: Document) -> str:
    src = doc.source
    return src.value if hasattr(src, "value") else str(src)


def _classify_geo_document(doc: Document) -> EvidenceLevel:
    taxon = " ".join(doc.keywords or []).lower()
    if "mus musculus" in taxon or "mouse" in taxon:
        return EvidenceLevel.MOUSE
    gdstype = " ".join(doc.publication_types or []).lower()
    if "in vitro" in gdstype or "cell line" in gdstype:
        return EvidenceLevel.IN_VITRO
    return EvidenceLevel.OTHER


def _is_rct(types_text: str, text: str) -> bool:
    return (
        "randomized controlled trial" in types_text
        or "randomised controlled trial" in types_text
        or ("controlled clinical trial" in types_text and "random" in text[:2500])
        or (
            "clinical trial" in types_text
            and ("randomized" in text[:2500] or "randomised" in text[:2500])
        )
    )


def _is_cohort(types_text: str, mesh_text: str) -> bool:
    cohort_markers = (
        "cohort studies",
        "observational study",
        "longitudinal studies",
        "prospective studies",
        "retrospective studies",
    )
    return any(marker in types_text for marker in cohort_markers) or "cohort studies" in mesh_text


def _is_in_vitro(mesh_text: str, text: str) -> bool:
    if any(term in mesh_text for term in ("cells, cultured", "cell line", "in vitro")):
        return True
    return "in vitro" in text[:2000]


def _is_mouse(mesh_text: str, text: str, types_text: str) -> bool:
    if any(term in types_text for term in ("clinical trial", "randomized controlled trial")):
        return False
    animal_mesh = (
        "mice",
        "mouse",
        "disease models, animal",
        "animals, laboratory",
        "mice, inbred",
        "mice, knockout",
    )
    if any(term in mesh_text for term in animal_mesh):
        return True
    animal_text = (
        " in mice",
        " in mouse",
        " murine ",
        " mouse model",
        " mice model",
        " rat model",
        "c57bl/6",
    )
    return any(term in text for term in animal_text)
