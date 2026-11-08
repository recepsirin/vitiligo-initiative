"""Relations the literature asserts, read by PubTator and checked against MeSH.

PubTator 3.0 gives 22,202 typed relations across the 11,697 abstracts it
holds for this corpus. Every rule below was decided by measuring all of them,
because three of PubTator's habits would each have put false claims into the
graph:

**It names the disease a description of vitiligo appears to be.** "An acquired
depigmentation disorder" becomes *Congenital, Hereditary, and Neonatal
Diseases*; "vitiligo vulgaris" becomes *Ichthyosis Vulgaris* (83 relations);
"leukoderma" becomes *Telfer Sugar Jaeger syndrome*; "vitiligo lesions" a
nameless OMIM number. So a disease mention that names vitiligo -- by this
project's own gate -- is vitiligo, whatever PubTator chose, which redirects
482 relations. Any other disease is kept only when the document writes it as
its MeSH name or one of MeSH's own entry terms, compared without regard to
word order, possessives, plurals or disorder-versus-disease: "cancer" is an
entry term of *Neoplasms* and "Hashimoto's thyroiditis" of *Hashimoto
Disease*, while "depigmentation disorder" is an entry term of nothing it was
given. A term may also stand inside a longer mention, so "metastatic
melanoma" supports *Melanoma*. Of 9,825 disease arguments that are not
vitiligo, 6,876 are kept this way; the 2,949 dropped are mostly adjectives
("inflammatory", "pigmentation") and descriptions of vitiligo itself.

**Its "treat" means "lower in".** A drug that treats a disease and a molecule
found at lower levels in it are both ``Negative_Correlation``, which PubTator
displays as "treat" -- so melanin treats vitiligo and malondialdehyde causes
it. A chemical counts as a drug if MeSH records a pharmacological action for
it, or if a trial in this corpus gives it as a drug, biological or
supplement. MeSH alone is not enough: its supplementary records carry no
pharmacological actions in the 2026 release, which would have demoted every
JAK inhibitor and checkpoint inhibitor. Anything else is a biomarker, and its
relations to a disease say only ``associated_with``. Monobenzone and
4-tert-butylphenol are demoted this way although both cause leukoderma -- an
under-claim, not a false one.

**It reads lasers as chemicals.** "Fractional CO2 laser" is *Carbon Dioxide*,
339 times, and the 308-nm excimer is *xenon chloride*. A chemical written
directly before the word "laser" is a laser intervention.

A gene is one node across species. A paper on a mouse model is annotated with
the mouse gene -- *Nr3c1*, NCBI Gene 14815, not human *NR3C1*, 2908 -- and
PubTator files both under one accession, @GENE_NR3C1. The node takes the
all-capitals spelling, which the corpus writes for every one of the 222
genes it writes more than one way; the species' own Gene id goes in the
evidence, because on the node it would overwrite the human one.

Everything is ``asserted``: a paper said it, and PubTator read it. Confidence
is the schema's default for an assertion with no special standing, below
every registry and GWAS edge, because PubTator's own score measures whether a
sentence expresses a relation, not whether the relation holds. The score is
kept in each edge's evidence instead, and relations below 0.5 -- the model's
own decision boundary -- are not loaded.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from vitiligo.graph.normalize import VITILIGO_ENTITY_NAME, normalize_entity_key
from vitiligo.graph.store import upsert_edge, upsert_entity
from vitiligo.sources.mesh import MeshRecord, normalise
from vitiligo.sources.pubtator import AnnotatedDocument, Concept, Mention
from vitiligo.storage.models import ClaimKind, EntityKind, GraphEntity, RelationKind
from vitiligo.trials.relevance import names_vitiligo

EXTRACTION_METHOD = "pubtator3"
CONFIDENCE = 0.5
MIN_SCORE = 0.5
VITILIGO_MESH = "MESH:D014820"

_LASER = re.compile(r"^\s*(?:\([^)]{1,12}\)\s*)?(?:fractional\s+)?laser", re.I)
_CORRESPONDING_GENE = re.compile(r"CorrespondingGene:(\d+)")
_RSID = re.compile(r"RS#:(\d+)")

# Interventions a trial gives a person, as opposed to a device or procedure
# it applies. "Fractional CO2 laser" is registered as a DEVICE.
_GIVEN_TYPES = frozenset({"DRUG", "BIOLOGICAL", "DIETARY_SUPPLEMENT", "COMBINATION_PRODUCT"})

_CORRELATION = frozenset({"Association", "Positive_Correlation", "Negative_Correlation"})

_PERTURB_PREFIX = re.compile(
    r"(?:knockdown|down[- ]?regulation|loss|deficiency|depletion|deletion|silencing|inhibition|blockade|absence|sh-|si-|anti-)\s*(?:of\s+)?$",
    re.I,
)
_PASSIVE_CUE = re.compile(
    r"\b(?:by|upon|from|after|following|were\s+up[- ]?regulated\s+in|was\s+up[- ]?regulated\s+in)\b",
    re.I,
)
_ACTIVE_INH = re.compile(
    r"\b(?:directly\s+|significantly\s+|potently\s+|selectively\s+|markedly\s+)?"
    r"(?:inhibit(?:s|ed|ing)|block(?:s|ed|ing)|suppress(?:es|ed|ing)|down[- ]?regulat(?:es|ed|ing)|"
    r"attenuat(?:es|ed|ing)|abrogat(?:es|ed|ing)|repress(?:es|ed|ing)|antagoniz(?:es|ed|ing))\b",
    re.I,
)
_ACTIVE_ACT = re.compile(
    r"\b(?:directly\s+|significantly\s+|potently\s+|selectively\s+|markedly\s+|robustly\s+)?"
    r"(?:activat(?:es|ed|ing)|induc(?:es|ed|ing)|up[- ]?regulat(?:es|ed|ing)|stimulat(?:es|ed|ing)|"
    r"promot(?:es|ed|ing)|enhanc(?:es|ed|ing)|phosphorylat(?:es|ed|ing)|trigger(?:s|ed|ing))\b",
    re.I,
)


def _node_pattern(node: Node) -> re.Pattern[str]:
    terms = sorted(
        {t.strip() for t in (node.name, *node.aliases) if len(t.strip()) >= 3},
        key=len,
        reverse=True,
    )
    if not terms:
        terms = [node.name]
    joined = "|".join(re.escape(t) for t in terms)
    return re.compile(rf"\b(?:{joined})\b", re.I)


def resolve_snippet_direction(
    kind: str, a: Node, b: Node, snippet: str | None
) -> tuple[Node, RelationKind, Node] | None:
    """Resolve active-voice directional mechanism (INHIBITS / ACTIVATES) from sentence snippet."""
    if not snippet or kind not in _CORRELATION:
        return None
    pat_a = _node_pattern(a)
    pat_b = _node_pattern(b)
    matches_a = list(pat_a.finditer(snippet))
    matches_b = list(pat_b.finditer(snippet))
    if not matches_a or not matches_b:
        return None

    pairs = sorted(
        ((ma, mb) for ma in matches_a for mb in matches_b if abs(ma.start() - mb.start()) >= 3),
        key=lambda p: abs(p[0].start() - p[1].start()),
    )
    for ma, mb in pairs:
        first, second = (a, b) if ma.start() < mb.start() else (b, a)
        m_first, m_second = (ma, mb) if ma.start() < mb.start() else (mb, ma)
        if EntityKind.DRUG in {a.kind, b.kind} and first.kind != EntityKind.DRUG:
            continue
        between = snippet[m_first.end() : m_second.start()]
        if len(between) > 95 or ";" in between or "." in between:
            continue
        prefix = snippet[max(0, m_first.start() - 35) : m_first.start()]
        if _PERTURB_PREFIX.search(prefix) or _PERTURB_PREFIX.search(between):
            continue
        if _PASSIVE_CUE.search(between):
            continue
        has_inh = bool(_ACTIVE_INH.search(between))
        has_act = bool(_ACTIVE_ACT.search(between))
        if has_inh and not has_act and kind in ("Negative_Correlation", "Association"):
            return first, RelationKind.INHIBITS, second
        if has_act and not has_inh and kind in ("Positive_Correlation", "Association"):
            return first, RelationKind.ACTIVATES, second
    return None


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "is", "us")):
        word = word[:-1]
    return "disease" if word == "disorder" else word


def _tokens(text: str) -> frozenset[str]:
    """A phrase as a set of words, so word order and inflection do not matter.

    MeSH writes "Thyroiditis, Autoimmune" where a paper writes "autoimmune
    thyroiditis", and lists "Autoimmune Diseases" where a paper writes
    "autoimmune disorders".
    """
    text = re.sub(r"'s\b", "", text.lower())
    return frozenset(_stem(w) for w in re.findall(r"[a-z0-9]+", text))


@dataclass(frozen=True)
class Node:
    kind: EntityKind
    name: str
    external_ids: tuple[tuple[str, str], ...] = ()
    aliases: tuple[str, ...] = ()


@dataclass
class LoadStats:
    documents: int = 0
    relations: int = 0
    loaded: int = 0
    edges_inserted: int = 0
    by_predicate: Counter[str] = field(default_factory=Counter)
    dropped: Counter[str] = field(default_factory=Counter)


class LiteratureReader:
    """Turns PubTator concepts and relations into graph nodes and edges."""

    def __init__(
        self,
        mesh: dict[str, MeshRecord],
        given_names: Iterable[str],
        gene_symbols: dict[str, str],
    ) -> None:
        self._mesh = mesh
        self._terms = {ui: [_tokens(t) for t in record.terms] for ui, record in mesh.items()}
        self._given = " | " + " | ".join(normalise(n) for n in given_names if n) + " | "
        self._gene_symbols = gene_symbols
        self._drug_cache: dict[str, bool] = {}

    def _record(self, concept: Concept) -> MeshRecord | None:
        return self._mesh.get(concept.identifier.removeprefix("MESH:"))

    def is_drug(self, concept: Concept) -> bool:
        if concept.identifier not in self._drug_cache:
            record = self._record(concept)
            self._drug_cache[concept.identifier] = record is not None and (
                bool(record.pharmacological_actions)
                or any(len(t) >= 4 and f" {t} " in self._given for t in record.terms)
            )
        return self._drug_cache[concept.identifier]

    def _supported(self, concept: Concept, written: list[str]) -> bool:
        terms = self._terms.get(concept.identifier.removeprefix("MESH:"), [])
        for text in written:
            mention = _tokens(text)
            if any(term and (term == mention or term <= mention) for term in terms):
                return True
        return False

    def node(self, concept: Concept, mentions: list[Mention]) -> Node | str:
        """The graph node a concept is, or the reason it is not one."""
        written = [m.text for m in mentions]
        if concept.type == "Disease":
            if concept.identifier == VITILIGO_MESH or any(names_vitiligo(w) for w in written):
                return Node(EntityKind.DISEASE, VITILIGO_ENTITY_NAME, (("mesh", "D014820"),))
            record = self._record(concept)
            if record is None or not self._supported(concept, written):
                return "disease the text does not support"
            return Node(EntityKind.DISEASE, record.name, (("mesh", record.ui),))
        if concept.type == "Chemical":
            record = self._record(concept)
            name = record.name if record else concept.name
            if any(_LASER.match(m.after) for m in mentions):
                return Node(EntityKind.INTERVENTION, f"{name} laser")
            ids = (("mesh", record.ui),) if record else ()
            kind = EntityKind.DRUG if self.is_drug(concept) else EntityKind.BIOMARKER
            return Node(kind, name, ids)
        if concept.type == "Gene":
            return Node(EntityKind.TARGET, self._gene_symbols.get(concept.identifier, concept.name))
        if concept.type == "Variant":
            gene = _CORRESPONDING_GENE.search(concept.identifier)
            symbol = self._gene_symbols.get(gene.group(1)) if gene else None
            if symbol is None:
                return "variant with no gene"
            return Node(EntityKind.TARGET, symbol)
        return f"{concept.type.lower()} is not a graph node"


def _predicate(
    kind: str, a: Node, b: Node, snippet: str | None = None
) -> tuple[Node, RelationKind, Node] | None:
    """Subject, predicate and object for a relation, or None if none fits."""
    agents = {EntityKind.DRUG, EntityKind.INTERVENTION}
    pair = {a.kind, b.kind}
    if a == b:
        return None
    if kind == "Cotreatment" and pair <= {
        EntityKind.DRUG,
        EntityKind.BIOMARKER,
        EntityKind.INTERVENTION,
    }:
        # Given together; neither is the subject, so A-B and B-A are one edge.
        first, second = sorted((a, b), key=lambda n: normalize_entity_key(n.name))
        return first, RelationKind.COMBINED_WITH, second
    if EntityKind.DISEASE in pair and pair & agents:
        agent, disease = (a, b) if a.kind in agents else (b, a)
        verb = {
            "Negative_Correlation": RelationKind.TREATS,
            "Positive_Correlation": RelationKind.CAUSES,
            "Association": RelationKind.ASSOCIATED_WITH,
        }.get(kind)
        return (agent, verb, disease) if verb else None
    if EntityKind.DRUG in pair and EntityKind.TARGET in pair:
        drug, target = (a, b) if a.kind == EntityKind.DRUG else (b, a)
        if kind == "Association" and snippet:
            resolved = resolve_snippet_direction(kind, drug, target, snippet)
            if resolved is not None:
                return resolved
        verb = {
            "Negative_Correlation": RelationKind.INHIBITS,
            "Positive_Correlation": RelationKind.ACTIVATES,
            "Bind": RelationKind.TARGETS,
            "Association": RelationKind.ASSOCIATED_WITH,
        }.get(kind)
        return (drug, verb, target) if verb else None
    if kind not in _CORRELATION and kind != "Bind":
        return None
    if EntityKind.DISEASE in pair:  # a target or biomarker, and a disease
        other, disease = (a, b) if b.kind == EntityKind.DISEASE else (b, a)
        if other.kind not in {EntityKind.TARGET, EntityKind.BIOMARKER}:
            return None
        return other, RelationKind.ASSOCIATED_WITH, disease
    if pair <= {EntityKind.TARGET, EntityKind.BIOMARKER, EntityKind.INTERVENTION}:
        if a.kind == EntityKind.TARGET and b.kind == EntityKind.TARGET and snippet:
            resolved = resolve_snippet_direction(kind, a, b, snippet)
            if resolved is not None:
                return resolved
        if kind == "Bind" and pair == {EntityKind.TARGET}:
            first, second = sorted((a, b), key=lambda n: normalize_entity_key(n.name))
            return first, RelationKind.TARGETS, second
        # BioRED does not annotate direction between two genes, so the edge
        # claims none; ordering by key keeps A-B and B-A one edge.
        first, second = sorted((a, b), key=lambda n: normalize_entity_key(n.name))
        return first, RelationKind.ASSOCIATED_WITH, second
    return None


def gene_symbols(documents: Iterable[AnnotatedDocument]) -> dict[str, str]:
    """NCBI Gene id to the name of its node, the same for every species.

    Genes are grouped by PubTator's accession, and each group is named by its
    all-capitals spelling -- NR3C1 over Nr3c1 -- or by its only spelling.
    """
    accession: dict[str, str] = {}
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    for doc in documents:
        for mention in doc.mentions:
            concept = mention.concept
            if concept.type == "Gene":
                group = concept.accession or concept.name.upper()
                accession.setdefault(concept.identifier, group)
                spellings[group][concept.name] += 1
    named = {
        group: max(counts, key=lambda s: (s == s.upper(), counts[s]))
        for group, counts in spellings.items()
    }
    return {gene: named[group] for gene, group in accession.items()}


def load_literature(
    session: Session,
    documents: Iterable[AnnotatedDocument],
    reader: LiteratureReader,
    *,
    method: str = EXTRACTION_METHOD,
    min_score: float = MIN_SCORE,
    confidence: float = CONFIDENCE,
    accept: Callable[[Node, RelationKind, Node], bool] | None = None,
) -> LoadStats:
    """Write every relation the reader accepts as an asserted edge.

    ``method`` names the extractor in each edge and its evidence. ``min_score``
    is the score below which a relation is not loaded: PubTator's own decision
    boundary by default. ``confidence`` is the edges' prior, and ``accept``
    lets an extractor decline the kinds of claim it was measured to get wrong.
    """
    stats = LoadStats()

    def entity(node: Node) -> GraphEntity:
        # A paper is the weakest source in the graph, so a node another source
        # already named keeps that name -- Upadacitinib does not become MeSH's
        # "upadacitinib" -- and the name read here is kept as an alias.
        held = session.exec(
            select(GraphEntity).where(
                GraphEntity.kind == node.kind,
                GraphEntity.key == normalize_entity_key(node.name),
            )
        ).first()
        return upsert_entity(
            session,
            kind=node.kind,
            name=held.name if held is not None else node.name,
            aliases=[node.name],
            external_ids=dict(node.external_ids),
        )

    for doc in documents:
        stats.documents += 1
        mentions: dict[str, list[Mention]] = defaultdict(list)
        for mention in doc.mentions:
            mentions[mention.concept.identifier].append(mention)
        for relation in doc.relations:
            stats.relations += 1
            if relation.score < min_score:
                stats.dropped["below the model's own decision boundary"] += 1
                continue
            a = reader.node(relation.first, mentions[relation.first.identifier])
            b = reader.node(relation.second, mentions[relation.second.identifier])
            if isinstance(a, str) or isinstance(b, str):
                stats.dropped[a if isinstance(a, str) else str(b)] += 1
                continue
            triple = _predicate(relation.type, a, b, relation.snippet)
            if triple is None:
                stats.dropped[f"no predicate for {relation.type}"] += 1
                continue
            subject, predicate, obj = triple
            if accept is not None and not accept(subject, predicate, obj):
                stats.dropped[f"{predicate.value} not trusted from {method}"] += 1
                continue
            evidence: dict[str, Any] = {
                "source_type": method,
                # A PMID is bare; any other document's id carries its scheme
                # (doi:, reporter:, ctgov: ...).
                "source_id": doc.pmid if ":" in doc.pmid else f"pmid:{doc.pmid}",
                "relation": relation.type,
                "score": round(relation.score, 3),
            }
            if relation.section:
                evidence["section"] = relation.section
            if relation.snippet:
                evidence["snippet"] = relation.snippet
            genes = [c.identifier for c in (relation.first, relation.second) if c.type == "Gene"]
            if genes:
                evidence["ncbi_gene"] = genes
            for concept in (relation.first, relation.second):
                rsid = _RSID.search(concept.identifier)
                if concept.type == "Variant" and rsid:
                    evidence["variant"] = f"rs{rsid.group(1)}"
            _, inserted = upsert_edge(
                session,
                subject=entity(subject),
                predicate=predicate,
                obj=entity(obj),
                confidence=confidence,
                extraction_method=method,
                evidence=evidence,
                claim=ClaimKind.ASSERTED,
            )
            stats.loaded += 1
            stats.edges_inserted += int(inserted)
            stats.by_predicate[predicate.value] += 1
    return stats
