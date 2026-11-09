"""External gold relation extraction corpora to complement BioRED.

BioRED provides gold annotations across all pairs, but only holds 400 training
abstracts (yielding just 61 Bind relations and 31 Cotreatment relations).
This module ingests two standard, high-quality BioCreative gold benchmarks:

1. BC5CDR (BioCreative V Chemical-Disease Relations):
   1,000 PubMed abstracts with expert-curated Chemical-induced-Disease
   (Positive_Correlation) relations.
2. ChemProt (BioCreative VI Chemical-Protein Interactions):
   1,632 PubMed abstracts with expert-curated Chemical-Protein interactions:
   - CPR:3 / CPR:5 -> Positive_Correlation (activator / upregulator / agonist)
   - CPR:4 / CPR:6 -> Negative_Correlation (inhibitor / downregulator / antagonist)
   - CPR:9 -> Bind (substrate / product / physical binder)
   - CPR:2 -> Association (general regulator)

Any PMID present in BioRED's development or test splits is strictly excluded
so that the BioRED test benchmark remains unseen.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx

from vitiligo.logging import get_logger
from vitiligo.sources.biored import load_split as load_biored_split
from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Mention, Passage, Relation
from vitiligo.sources.raw_cache import DEFAULT_RAW_CACHE, load_payload, save_payload

logger = get_logger(__name__)

BC5CDR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/lu/BC5CDR/CDR_Data.zip"


def _held_out_biored_pmids() -> frozenset[str]:
    return frozenset(d.pmid for split in ("Dev", "Test") for d in load_biored_split(split))


def load_bc5cdr(
    *, cache: Path = DEFAULT_RAW_CACHE, exclude_pmids: frozenset[str] | None = None
) -> list[AnnotatedDocument]:
    """Parse BC5CDR training and development abstracts as AnnotatedDocument instances."""
    if exclude_pmids is None:
        exclude_pmids = _held_out_biored_pmids()

    cached = load_payload("bc5cdr", "CDR_Data.zip", cache)
    if cached is None:
        logger.info("Downloading BC5CDR corpus from %s", BC5CDR_URL)
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            resp = client.get(BC5CDR_URL)
            resp.raise_for_status()
            cached = resp.content
        save_payload("bc5cdr", "CDR_Data.zip", cached, url=BC5CDR_URL, cache=cache)

    documents: list[AnnotatedDocument] = []
    with zipfile.ZipFile(io.BytesIO(cached)) as archive:
        for split_name in ("Training", "Development"):
            filename = f"CDR_Data/CDR.Corpus.v010516/CDR_{split_name}Set.PubTator.txt"
            raw_text = archive.read(filename).decode("utf-8")
            documents.extend(_parse_bc5cdr_txt(raw_text, exclude_pmids=exclude_pmids))
    return documents


def _parse_bc5cdr_txt(text: str, exclude_pmids: frozenset[str]) -> list[AnnotatedDocument]:
    docs: list[AnnotatedDocument] = []
    cur_pmid: str | None = None
    title = ""
    abstract = ""
    mentions: list[Mention] = []
    relations: list[tuple[str, str]] = []

    def flush() -> None:
        if not cur_pmid or cur_pmid in exclude_pmids:
            return
        kinds = {m.concept.identifier: m.concept.type for m in mentions}
        rel_objs: list[Relation] = []
        for c_id, d_id in relations:
            if c_id in kinds and d_id in kinds:
                rel_objs.append(
                    Relation(
                        type="Positive_Correlation",
                        score=1.0,
                        first=Concept(type="Chemical", identifier=c_id, name=c_id),
                        second=Concept(type="Disease", identifier=d_id, name=d_id),
                    )
                )
        docs.append(
            AnnotatedDocument(
                pmid=cur_pmid,
                pmcid=None,
                passages=(
                    Passage("title", 0, title),
                    Passage("abstract", len(title) + 1, abstract),
                ),
                mentions=tuple(mentions),
                relations=tuple(rel_objs),
                target_type_pairs=frozenset({("Chemical", "Disease")}),
            )
        )

    for line in text.splitlines():
        line = line.strip()
        if not line:
            flush()
            cur_pmid = None
            title, abstract = "", ""
            mentions, relations = [], []
            continue
        if "|t|" in line:
            pmid, _, title = line.partition("|t|")
            cur_pmid = pmid
        elif "|a|" in line:
            pmid, _, abstract = line.partition("|a|")
            cur_pmid = pmid
        else:
            parts = line.split("\t")
            if len(parts) >= 6:
                pmid, start, _end, m_text, kind, ident = parts[:6]
                if ident != "-" and kind in ("Chemical", "Disease"):
                    offset = int(start)
                    pass_name = "title" if offset < len(title) else "abstract"
                    mentions.append(
                        Mention(
                            concept=Concept(type=kind, identifier=ident, name=m_text),
                            text=m_text,
                            passage=pass_name,
                            offset=offset,
                        )
                    )
            elif len(parts) == 4 and parts[1] == "CID":
                _, _, c_id, d_id = parts
                relations.append((c_id, d_id))
    flush()
    return docs


CHEMPROT_CPR_MAP = {
    "CPR:2": "Association",
    "CPR:3": "Positive_Correlation",
    "CPR:4": "Negative_Correlation",
    "CPR:5": "Positive_Correlation",
    "CPR:6": "Negative_Correlation",
    "CPR:9": "Bind",
}


def load_chemprot(*, exclude_pmids: frozenset[str] | None = None) -> list[AnnotatedDocument]:
    """Parse ChemProt BioCreative VI training and development abstracts."""
    if exclude_pmids is None:
        exclude_pmids = _held_out_biored_pmids()

    from huggingface_hub import hf_hub_download

    archive_path = hf_hub_download(
        repo_id="DFKI-SLT/chemprot", filename="ChemProt_Corpus.zip", repo_type="dataset"
    )

    documents: list[AnnotatedDocument] = []
    with zipfile.ZipFile(archive_path) as outer:
        for split_name in ("training", "development"):
            inner_bytes = outer.read(f"ChemProt_Corpus/chemprot_{split_name}.zip")
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
                abss_raw = inner.read(
                    f"chemprot_{split_name}/chemprot_{split_name}_abstracts.tsv"
                ).decode("utf-8")
                ents_raw = inner.read(
                    f"chemprot_{split_name}/chemprot_{split_name}_entities.tsv"
                ).decode("utf-8")
                rels_raw = inner.read(
                    f"chemprot_{split_name}/chemprot_{split_name}_relations.tsv"
                ).decode("utf-8")
                documents.extend(
                    _parse_chemprot(abss_raw, ents_raw, rels_raw, exclude_pmids=exclude_pmids)
                )
    return documents


def _parse_chemprot(
    abss_tsv: str, ents_tsv: str, rels_tsv: str, exclude_pmids: frozenset[str]
) -> list[AnnotatedDocument]:
    abss: dict[str, tuple[str, str]] = {}
    for line in abss_tsv.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0] not in exclude_pmids:
            abss[parts[0]] = (parts[1], parts[2])

    ents_by_pmid: dict[str, list[tuple[str, str, int, int, str]]] = {}
    for line in ents_tsv.splitlines():
        parts = line.split("\t")
        if len(parts) >= 6 and parts[0] in abss:
            pmid, tid, etype, s, e, text = parts[:6]
            kind = "Chemical" if etype == "CHEMICAL" else "Gene"
            ents_by_pmid.setdefault(pmid, []).append((tid, kind, int(s), int(e), text))

    rels_by_pmid: dict[str, list[tuple[str, str, str]]] = {}
    for line in rels_tsv.splitlines():
        parts = line.split("\t")
        if len(parts) >= 6 and parts[0] in abss and parts[1] in CHEMPROT_CPR_MAP:
            pmid, cpr = parts[0], parts[1]
            arg1 = parts[4].split(":")[-1]
            arg2 = parts[5].split(":")[-1]
            rels_by_pmid.setdefault(pmid, []).append((cpr, arg1, arg2))

    documents: list[AnnotatedDocument] = []
    for pmid, (title, body) in abss.items():
        doc_ents = ents_by_pmid.get(pmid, [])
        doc_rels = rels_by_pmid.get(pmid, [])
        if not doc_ents or not doc_rels:
            continue

        term_to_concept: dict[str, tuple[str, str, str]] = {}
        mentions: list[Mention] = []
        for tid, kind, start_pos, _end_pos, text in doc_ents:
            cid = f"{kind.lower()}:{text.strip().lower()}"
            term_to_concept[tid] = (cid, kind, text)
            mentions.append(
                Mention(
                    concept=Concept(type=kind, identifier=cid, name=text),
                    text=text,
                    passage="title" if start_pos < len(title) else "abstract",
                    offset=start_pos,
                )
            )

        relations: dict[tuple[str, str], Relation] = {}
        for cpr, arg1, arg2 in doc_rels:
            if arg1 in term_to_concept and arg2 in term_to_concept:
                c1, t1, n1 = term_to_concept[arg1]
                c2, t2, n2 = term_to_concept[arg2]
                if c1 != c2:
                    rel_type = CHEMPROT_CPR_MAP[cpr]
                    key = (min(c1, c2), max(c1, c2))
                    relations[key] = Relation(
                        type=rel_type,
                        score=1.0,
                        first=Concept(type=t1, identifier=c1, name=n1),
                        second=Concept(type=t2, identifier=c2, name=n2),
                    )

        if relations:
            documents.append(
                AnnotatedDocument(
                    pmid=pmid,
                    pmcid=None,
                    passages=(
                        Passage("title", 0, title),
                        Passage("abstract", len(title) + 1, body),
                    ),
                    mentions=tuple(mentions),
                    relations=tuple(relations.values()),
                    target_type_pairs=frozenset({("Chemical", "Gene")}),
                )
            )
    return documents


def load_augmented_training() -> list[AnnotatedDocument]:
    """Returns BioRED Train augmented with non-overlapping BC5CDR and ChemProt gold documents."""
    biored_train = load_biored_split("Train")
    bc5cdr = load_bc5cdr()
    chemprot = load_chemprot()
    logger.info(
        "Loaded augmented gold training: %d BioRED + %d BC5CDR + %d ChemProt = %d total documents",
        len(biored_train),
        len(bc5cdr),
        len(chemprot),
        len(biored_train) + len(bc5cdr) + len(chemprot),
    )
    return [*biored_train, *bc5cdr, *chemprot]
