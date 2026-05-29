"""DrugBank source — local XML file import.

DrugBank full-database XML requires an academic or commercial license and
is not freely downloadable without credentials (official open CC0 packages
are vocabulary/structures only). The supported workflow is:

1. Create a free academic account at https://go.drugbank.com/
2. Download ``all-full-database`` XML (or place an older export on disk)
3. Import locally::

       vitiligo ingest drugbank --file full_database.xml

We parse the standard DrugBank 5.x XML namespace, filter to vitiligo-relevant
drugs (text match + optional Open Targets name seeding), and persist drug and
target priors under ``source=drugbank``.
"""

from __future__ import annotations

import re
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lxml import etree

from vitiligo.logging import get_logger
from vitiligo.sources.opentargets import DEFAULT_VITILIGO_EFO_ID
from vitiligo.storage.models import Prior, PriorKind, PriorSourceKind

logger = get_logger(__name__)

DB_NS = "http://www.drugbank.ca"
TAG_DRUG = f"{{{DB_NS}}}drug"

DEFAULT_VITILIGO_QUERY = "vitiligo"

_TARGET_TAGS = ("target", "enzyme", "carrier", "transporter")
_GROUP_STAGE: dict[str, str] = {
    "approved": "APPROVAL",
    "vet approved": "APPROVAL",
    "investigational": "PHASE_2",
    "experimental": "PHASE_1",
    "nutraceutical": "UNKNOWN",
    "illicit": "UNKNOWN",
    "withdrawn": "WITHDRAWN",
}


def resolve_drugbank_xml(path: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    """Return a path to XML, extracting ``.zip`` archives when needed."""
    if path.suffix.lower() != ".zip":
        return path, None

    tmp = tempfile.TemporaryDirectory(prefix="vitiligo-drugbank-")
    with zipfile.ZipFile(path) as zf:
        xml_members = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not xml_members:
            tmp.cleanup()
            raise ValueError(f"No XML file found inside DrugBank zip: {path}")
        member = sorted(xml_members, key=len)[-1]
        target = Path(tmp.name) / Path(member).name
        target.write_bytes(zf.read(member))
    return target, tmp


def count_drugbank_drugs(path: Path) -> int:
    """Count ``<drug>`` elements in a DrugBank XML export."""
    xml_path, tmp = resolve_drugbank_xml(path)
    try:
        count = 0
        for _ in _iter_drug_elements(xml_path):
            count += 1
        return count
    finally:
        if tmp is not None:
            tmp.cleanup()


def iter_drugbank_priors(
    path: Path,
    query: str = DEFAULT_VITILIGO_QUERY,
    disease_id: str = DEFAULT_VITILIGO_EFO_ID,
    disease_name: str = "Vitiligo",
    seed_names: set[str] | None = None,
    limit: int | None = None,
) -> Iterator[Prior]:
    """Yield drug + target priors from a DrugBank XML file."""
    xml_path, tmp = resolve_drugbank_xml(path)
    emitted = 0
    seen_targets: set[str] = set()

    try:
        for drug_el in _iter_drug_elements(xml_path):
            parsed = _parse_drug_element(drug_el)
            if parsed is None:
                continue
            if not _matches_filter(parsed, query=query, seed_names=seed_names):
                continue

            yield _drug_to_prior(parsed, disease_id=disease_id, disease_name=disease_name)
            emitted += 1

            for target in parsed["targets"]:
                tid = target["source_id"]
                if tid in seen_targets:
                    continue
                seen_targets.add(tid)
                yield _target_to_prior(
                    target,
                    disease_id=disease_id,
                    disease_name=disease_name,
                    linked_drug_id=parsed["drugbank_id"],
                )

            if limit is not None and emitted >= limit:
                return
    finally:
        if tmp is not None:
            tmp.cleanup()


def normalize_drug_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.upper().strip())


def _matches_filter(
    parsed: dict[str, Any],
    *,
    query: str,
    seed_names: set[str] | None,
) -> bool:
    q = query.strip().lower()
    if q:
        blob = " ".join(
            filter(
                None,
                [
                    parsed.get("name"),
                    parsed.get("description"),
                    parsed.get("indication"),
                    parsed.get("mechanism"),
                    " ".join(parsed.get("synonyms") or []),
                    " ".join(parsed.get("categories") or []),
                ],
            )
        ).lower()
        if q in blob:
            return True

    if seed_names:
        names = {normalize_drug_name(parsed["name"])}
        names.update(normalize_drug_name(s) for s in parsed.get("synonyms") or [])
        if names & seed_names:
            return True
    return False


def _drug_to_prior(
    parsed: dict[str, Any],
    *,
    disease_id: str,
    disease_name: str,
) -> Prior:
    mechanisms: list[dict[str, Any]] = []
    if parsed.get("mechanism"):
        mechanisms.append(
            {
                "mechanism": parsed["mechanism"],
                "action_type": None,
                "target_name": None,
                "targets": [
                    {"id": t["source_id"], "symbol": t["gene_name"], "name": t["name"]}
                    for t in parsed["targets"]
                ],
            }
        )
    for target in parsed["targets"]:
        if target.get("actions"):
            mechanisms.append(
                {
                    "mechanism": f"{target['name']}: {', '.join(target['actions'])}",
                    "action_type": target["actions"][0],
                    "target_name": target["name"],
                    "targets": [
                        {
                            "id": target["source_id"],
                            "symbol": target.get("gene_name"),
                            "name": target.get("name"),
                        }
                    ],
                }
            )

    return Prior(
        source=PriorSourceKind.DRUGBANK,
        kind=PriorKind.DRUG,
        source_id=parsed["drugbank_id"],
        disease_id=disease_id,
        disease_name=disease_name,
        name=parsed["name"],
        description=parsed.get("description"),
        score=None,
        clinical_stage=parsed.get("clinical_stage"),
        synonyms=list(parsed.get("synonyms") or [])[:20],
        mechanisms=mechanisms[:10],
        linked_trial_ids=[],
        linked_target_ids=[t["source_id"] for t in parsed["targets"]],
        raw_metadata={
            "drugbank_id": parsed["drugbank_id"],
            "drug_type": parsed.get("drug_type"),
            "groups": parsed.get("groups"),
            "indication": parsed.get("indication"),
            "categories": parsed.get("categories"),
        },
    )


def _target_to_prior(
    target: dict[str, Any],
    *,
    disease_id: str,
    disease_name: str,
    linked_drug_id: str,
) -> Prior:
    return Prior(
        source=PriorSourceKind.DRUGBANK,
        kind=PriorKind.TARGET,
        source_id=target["source_id"],
        disease_id=disease_id,
        disease_name=disease_name,
        name=target.get("gene_name") or target["name"],
        description=target.get("name"),
        score=0.5,
        clinical_stage=None,
        synonyms=[],
        mechanisms=[
            {
                "mechanism": ", ".join(target.get("actions") or []),
                "target_name": target.get("name"),
            }
        ]
        if target.get("actions")
        else [],
        linked_trial_ids=[],
        linked_target_ids=[target["source_id"]],
        raw_metadata={
            "gene_name": target.get("gene_name"),
            "organism": target.get("organism"),
            "known_action": target.get("known_action"),
            "linked_drugbank_ids": [linked_drug_id],
        },
    )


def _parse_drug_element(drug_el: etree._Element) -> dict[str, Any] | None:
    drugbank_id = _primary_drugbank_id(drug_el)
    name = _child_text(drug_el, "name")
    if not drugbank_id or not name:
        return None

    groups = [
        g.text.strip() for g in drug_el.findall(f"{{{DB_NS}}}groups/{{{DB_NS}}}group") if g.text
    ]
    clinical_stage = _groups_to_stage(groups)

    synonyms = [
        s.text.strip()
        for s in drug_el.findall(f"{{{DB_NS}}}synonyms/{{{DB_NS}}}synonym")
        if s.text and s.text.strip()
    ]

    categories = [
        c.text.strip()
        for c in drug_el.findall(f"{{{DB_NS}}}categories/{{{DB_NS}}}category")
        if c.text and c.text.strip()
    ]

    targets: list[dict[str, Any]] = []
    for tag in _TARGET_TAGS:
        for entry in drug_el.findall(f"{{{DB_NS}}}{tag}s/{{{DB_NS}}}{tag}"):
            parsed_target = _parse_target_entry(entry)
            if parsed_target is not None:
                targets.append(parsed_target)

    return {
        "drugbank_id": drugbank_id,
        "name": name,
        "drug_type": drug_el.get("type"),
        "description": _child_text(drug_el, "description")
        or _child_text(drug_el, "simple-description"),
        "indication": _child_text(drug_el, "indication"),
        "mechanism": _child_text(drug_el, "mechanism-of-action"),
        "groups": groups,
        "clinical_stage": clinical_stage,
        "synonyms": synonyms,
        "categories": categories,
        "targets": targets,
    }


def _parse_target_entry(entry: etree._Element) -> dict[str, Any] | None:
    name = _child_text(entry, "name")
    if not name:
        return None

    actions = [
        a.text.strip()
        for a in entry.findall(f"{{{DB_NS}}}actions/{{{DB_NS}}}action")
        if a.text and a.text.strip()
    ]
    polypeptide = entry.find(f"{{{DB_NS}}}polypeptide")
    gene_name = _child_text(polypeptide, "gene-name") if polypeptide is not None else None
    uniprot = polypeptide.get("id") if polypeptide is not None else None
    source_id = uniprot or gene_name or _child_text(entry, "id") or name
    source_id = source_id.strip()

    return {
        "source_id": source_id,
        "name": name,
        "gene_name": gene_name,
        "organism": _child_text(entry, "organism"),
        "known_action": _child_text(entry, "known-action"),
        "actions": actions,
    }


def _primary_drugbank_id(drug_el: etree._Element) -> str | None:
    for node in drug_el.findall(f"{{{DB_NS}}}drugbank-id"):
        if node.get("primary") == "true" and node.text:
            return node.text.strip()
    for node in drug_el.findall(f"{{{DB_NS}}}drugbank-id"):
        if node.text and node.text.strip().startswith("DB"):
            return node.text.strip()
    return None


def _groups_to_stage(groups: list[str]) -> str | None:
    for group in groups:
        stage = _GROUP_STAGE.get(group.lower())
        if stage:
            return stage
    return None


def _child_text(parent: etree._Element | None, local_name: str) -> str | None:
    if parent is None:
        return None
    node = parent.find(f"{{{DB_NS}}}{local_name}")
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _iter_drug_elements(path: Path) -> Iterator[etree._Element]:
    context = etree.iterparse(str(path), events=("end",), tag=TAG_DRUG, huge_tree=True)
    for _event, elem in context:
        yield elem
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]  # type: ignore[union-attr, index]
