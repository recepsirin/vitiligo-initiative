"""Trials that exist only as papers.

The trials table was built from registries, so a trial that was never
registered is not in it however well it was conducted. For vitiligo that is
most of them: PubMed lists 522 published vitiligo trials and only 28 carry a
registry accession, because registration became a condition of publication in
2005 and much of this literature is older.

Turkey is the clearest case. Eighteen published vitiligo trials carry a
Turkish affiliation -- "Mometasone cream versus pimecrolimus cream", "No
additional effect of topical calcipotriol on narrow-band UVB", "Comparison of
two surgical approaches" -- and not one names a registry id, because fourteen
of the eighteen predate 2010 and Turkey has no registry in the WHO network.
The same holds across Latin America, eastern Europe and the Middle East.

What this builds is a trial record for each such paper, so a reader asking
what has been tried in Turkey gets those eighteen rather than seven. Three
things keep it honest.

**A paper is not a protocol.** These records carry a title, an abstract, a
country and a year, and nothing else: no arms, no eligibility, no outcome
definitions, because the paper is all there is. They are marked
``published_only`` and counted apart from registered trials for that reason.

**Registration is checked two ways.** PubMed records a registry accession in
its ``DataBankList`` for 28 of the 522, and an identifier appears in the text
of a few more. Either one means the trial has a registry record, and a paper
that has one becomes no trial here -- the registry record is the better
source and is already held.

**Nothing claims a result.** ``has_results`` stays false. It means "the
registry posted results", and these have no registry; what the paper reports
is in its abstract, which the corpus already holds.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from vitiligo.logging import get_logger
from vitiligo.storage.models import Document, Trial, TrialSourceKind
from vitiligo.trials.countries import normalize_country
from vitiligo.trials.relevance import VITILIGO_AS_OUTCOME_SCOPE, studies_vitiligo

logger = get_logger(__name__)

PUBLISHED_ONLY_SCOPE = "published_only"

# Registry identifiers as they appear in a paper's text.
_REGISTRY_ID = re.compile(
    r"NCT\d{8}|CTRI/\d{4}/\d{2,3}/\d+|IRCT\w{6,}|ChiCTR[\w-]{4,}|ISRCTN\d{6,}"
    r"|ACTRN\d{10,}|DRKS\d{6,}|TCTR\d{8,}|JPRN-\w+|UMIN\d{6,}|PACTR\d{8,}"
    r"|EUCTR\d{4}-\d{6}-\d{2}|\b\d{4}-\d{6}-\d{2}\b",
    re.IGNORECASE,
)
_ACCESSION = re.compile(r"<AccessionNumber>([^<]+)</AccessionNumber>")


def registry_ids(document: Document) -> set[str]:
    """Every registry identifier the paper or PubMed associates with it.

    PubMed's ``DataBankList`` is the reliable half: a journal that required
    registration records the accession there. The text is the other half, for
    a paper that names its number only in a sentence.
    """
    metadata = document.raw_metadata or {}
    xml = str(metadata.get("pubmed_xml_excerpt") or "")
    found = set(_ACCESSION.findall(xml))
    found |= set(_REGISTRY_ID.findall(f"{document.title or ''}\n{document.abstract or ''}"))
    body = str(metadata.get("full_text") or "")
    if body:
        found |= set(_REGISTRY_ID.findall(body))
    return {f.strip() for f in found if f.strip()}


def comparison_key(identifier: str) -> str:
    """An identifier stripped to letters and digits, for comparing across styles."""
    return re.sub(r"[^A-Za-z0-9]", "", identifier).upper()


# A US affiliation often ends at the state. Sixty-three of these papers write
# "Ann Arbor, Michigan" or "Houston, Texas" and never the country, and reading
# only country names lost every one of them.
_US_STATE = re.compile(
    r"\b(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida"
    r"|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland"
    r"|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada"
    r"|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio"
    r"|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee"
    r"|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming)\b"
)


def countries_of(document: Document) -> list[str]:
    """The countries the authors wrote in their affiliations.

    An affiliation ends with its country far more often than it names a city
    this project could recognise, so the country names are searched for
    directly and the rest of the line ignored.

    A US state is read as the United States, except where the affiliation is
    Georgian: "Georgia" is a state and a country, and the one paper here that
    means the country says Tbilisi.
    """
    affiliations: list[str] = []
    for author in document.authors or []:
        if isinstance(author, dict):
            affiliations += [str(a) for a in (author.get("affiliations") or [])]
    text = " | ".join(affiliations)
    out: list[str] = []
    for name, pattern in _COUNTRY_PATTERNS:
        if pattern.search(text):
            canonical = normalize_country(name)
            if canonical and canonical not in out:
                out.append(canonical)
    if "Georgia" not in out and _US_STATE.search(text):
        united = normalize_country("United States")
        if united and united not in out:
            out.append(united)
    return out


# Countries as an affiliation writes them. The spelling a registry uses is
# not the spelling a letterhead uses, so "USA" and "UK" are here and
# ``normalize_country`` turns both into the project's name for the place.
_COUNTRY_NAMES: tuple[tuple[str, str], ...] = (
    ("United States", r"\bU\.?S\.?A\.?\b|\bUnited States\b"),
    ("United Kingdom", r"\bU\.?K\.?\b|\bUnited Kingdom\b|\bEngland\b|\bScotland\b|\bWales\b"),
    ("Turkey", r"\bTurkey\b|\bT[uü]rkiye\b"),
    ("Iran", r"\bIran\b"),
    ("Egypt", r"\bEgypt\b"),
    ("India", r"\bIndia\b"),
    ("China", r"\bChina\b|\bP\.?R\.? China\b"),
    ("Brazil", r"\bBrazil\b|\bBrasil\b"),
    ("Mexico", r"\bMexico\b|\bM[eé]xico\b"),
    ("Argentina", r"\bArgentina\b"),
    ("Chile", r"\bChile\b"),
    ("Colombia", r"\bColombia\b"),
    ("Cuba", r"\bCuba\b"),
    ("Peru", r"\bPeru\b|\bPer[uú]\b"),
    ("Russia", r"\bRussia\b|\bRussian Federation\b"),
    ("Ukraine", r"\bUkraine\b"),
    ("Poland", r"\bPoland\b"),
    ("Serbia", r"\bSerbia\b"),
    ("Hungary", r"\bHungary\b"),
    ("Czechia", r"\bCzech\b"),
    ("Romania", r"\bRomania\b"),
    ("Bulgaria", r"\bBulgaria\b"),
    ("Greece", r"\bGreece\b"),
    ("Italy", r"\bItaly\b|\bItalia\b"),
    ("Spain", r"\bSpain\b|\bEspa[nñ]a\b"),
    ("France", r"\bFrance\b"),
    ("Germany", r"\bGermany\b|\bDeutschland\b"),
    ("Netherlands", r"\bNetherlands\b|\bThe Netherlands\b"),
    ("Belgium", r"\bBelgium\b"),
    ("Switzerland", r"\bSwitzerland\b"),
    ("Austria", r"\bAustria\b"),
    ("Portugal", r"\bPortugal\b"),
    ("Denmark", r"\bDenmark\b"),
    ("Sweden", r"\bSweden\b"),
    ("Norway", r"\bNorway\b"),
    ("Finland", r"\bFinland\b"),
    ("Ireland", r"\bIreland\b"),
    ("Israel", r"\bIsrael\b"),
    ("Saudi Arabia", r"\bSaudi Arabia\b"),
    ("United Arab Emirates", r"\bUnited Arab Emirates\b|\bU\.?A\.?E\.?\b"),
    ("Jordan", r"\bJordan\b"),
    ("Lebanon", r"\bLebanon\b"),
    ("Iraq", r"\bIraq\b"),
    ("Pakistan", r"\bPakistan\b"),
    ("Bangladesh", r"\bBangladesh\b"),
    ("Nigeria", r"\bNigeria\b"),
    ("South Africa", r"\bSouth Africa\b"),
    ("Morocco", r"\bMorocco\b|\bMaroc\b"),
    ("Tunisia", r"\bTunisia\b|\bTunisie\b"),
    ("Japan", r"\bJapan\b"),
    ("South Korea", r"\bKorea\b"),
    ("Taiwan", r"\bTaiwan\b"),
    ("Thailand", r"\bThailand\b"),
    ("Malaysia", r"\bMalaysia\b"),
    ("Indonesia", r"\bIndonesia\b"),
    ("Singapore", r"\bSingapore\b"),
    ("Australia", r"\bAustralia\b"),
    ("New Zealand", r"\bNew Zealand\b"),
    ("Canada", r"\bCanada\b"),
    # Seen in these papers' affiliations and absent above until they were read.
    ("Kuwait", r"\bKuwait\b"),
    ("Libya", r"\bLibya\b"),
    ("Croatia", r"\bCroatia\b|\bHrvatska\b"),
    ("Estonia", r"\bEstonia\b"),
    ("Cyprus", r"\bCyprus\b"),
    ("Venezuela", r"\bVenezuela\b"),
    ("Nepal", r"\bNepal\b"),
    ("Viet Nam", r"\bVietnam\b|\bViet Nam\b"),
    ("Malta", r"\bMalta\b"),
    ("Slovakia", r"\bSlovakia\b|\bSlovak Republic\b"),
    # Georgia is named by its capital rather than itself, because the word
    # alone is a US state far more often. Tbilisi State Medical University
    # ran the one Georgian vitiligo trial in this corpus.
    ("Georgia", r"\bTbilisi\b"),
)
_COUNTRY_PATTERNS = tuple((name, re.compile(p)) for name, p in _COUNTRY_NAMES)


# Publication types that are about trials without being one. These beat a
# trial type: a systematic review of randomised trials is not a trial.
#
# "Letter" is deliberately absent. It is a length, not a content type:
# dermatology journals publish short randomised trials as letters, and 47
# held records carry both labels. "Can topical phenytoin augment the
# therapeutic efficacy of PUVA against vitiligo", typed Letter and Randomized
# Controlled Trial, is a trial. A letter PubMed has not also called a trial
# still has to earn it from its abstract, like anything else.
NOT_A_TRIAL: frozenset[str] = frozenset(
    {
        "Review",
        "Systematic Review",
        "Meta-Analysis",
        "Network Meta-Analysis",
        "Comment",
        "Editorial",
        "Case Reports",
        "Published Erratum",
        "Practice Guideline",
        "Guideline",
        "Observational Study",
    }
)

# Publication types that say PubMed has already decided it is a trial.
TRIAL_TYPES: frozenset[str] = frozenset(
    {
        "Randomized Controlled Trial",
        "Clinical Trial",
        "Controlled Clinical Trial",
        "Clinical Trial, Phase I",
        "Clinical Trial, Phase II",
        "Clinical Trial, Phase III",
        "Clinical Trial, Phase IV",
        "Pragmatic Clinical Trial",
        "Equivalence Trial",
        "Adaptive Clinical Trial",
        "Multicenter Study",
    }
)

# A trial report counts the people it enrolled or says how they were assigned.
# A dermatology abstract writes its sample size either way, and reading only
# digits lost 28 trials: "Twenty-two patients who were diagnosed with
# localized vitiligo", "Forty patients with stable vitiligo were equally
# divided".
_NUMBER_WORD = (
    r"(?:one\s+hundred(?:\s+and)?\s+)?"
    r"(?:ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
    r"|twenty|thirty|forty|fourty|fifty|sixty|seventy|eighty|ninety|hundred)"
    r"(?:[-\s](?:one|two|three|four|five|six|seven|eight|nine))?"
)
_ENROLLED = re.compile(
    rf"(?:\b\d{{1,4}}|\b{_NUMBER_WORD})\s+"
    r"(?:\w+\s+){0,2}?(?:patients?|participants?|subjects?|cases?|volunteers?)\b",
    re.I,
)


_ALLOCATED = re.compile(
    r"randomi[sz]ed|randomly\s+(?:assigned|allocated|divided)|double[- ]blind"
    r"|placebo[- ]controlled|were\s+(?:assigned|allocated|treated\s+with)"
    r"|split[- ]body|intra[- ]individual",
    re.I,
)


# What a title says when the record carries nothing else. Of 401 vitiligo
# papers from before 1970, 399 have no abstract -- and Europe PMC has none
# either, because it mirrors MEDLINE -- so the title is the whole record.
# Only wording that names a design counts: "Treatment of vitiligo with
# psoralen derivatives" could be a trial, a case series or an opinion, and
# nothing in the record decides.
_TITLE_DESIGN = re.compile(
    r"""
      double[- ]blind | single[- ]blind | placebo[- ]controlled | vehicle[- ]controlled
    | controlled\s+trial | controlled\s+study | randomi[sz]ed | cross[- ]?over
    | comparative\s+(?:study|trial) | a\s+(?:clinical\s+|therapeutic\s+)?trial\b
    | clinical\s+trial | split[- ]body | left[- ]right
    # A head-to-head comparison is a design statement. Leaving it out lost 30
    # papers whose title is the only record they have -- "Platelet-rich plasma
    # and follicular transplantation versus follicular transplantation", "A
    # comparative pilot study of dipstick versus open-spray cryotherapy".
    | \bversus\b | \bvs\.? | compared\s+(?:with|to) | comparison\s+of
    """,
    re.X | re.I,
)

# Diseases whose names contain a comparison word. "Graft-versus-host disease"
# is not a comparison of graft with host.
_NOT_A_COMPARISON = re.compile(r"graft[- ]versus[- ]host|host[- ]versus[- ]graft", re.I)


# A trial report names one trial. A paper whose title says "trials" is about
# them: a systematic review, a commentary, a survey of how trials report skin
# colour. That one word replaced a list of fifteen phrases and caught every
# record the others did.
#
# Widening the design wording above brought back two of them. "Meta-analysis
# reveals a lower UV signature in vitiligo skin compared to..." says
# "compared to" and carries no publication type, so the synthesis words have
# to be here after all: they were dead against the narrow pattern and are
# load-bearing against this one.
_TITLE_ABOUT_TRIALS = re.compile(r"\btrials\b|systematic\s+review|meta-?analys|comment\s+on", re.I)


def reports_a_trial(document: Document) -> bool:
    """True when the paper reports a trial rather than discussing trials.

    PubMed labels only some of them. Searching the text instead for
    "randomised" and "placebo" finds 545 more papers, and 71 are reviews, 42
    meta-analyses and 37 letters: the word appears because they are *about*
    trials. The publication type settles those, in both directions -- where
    PubMed has called it a trial there is nothing left to decide.

    Where it has not, the abstract has to count the people enrolled or say
    how they were assigned. Either will do, not both: requiring both rejected
    the ruxolitinib and narrow-band UVB study, which is single-arm and
    open-label and so allocates nobody, along with 333 other records already
    held.

    Where there is no abstract either, the title has to name a design. That is
    the whole record for 399 of the 401 vitiligo papers before 1970, and
    Europe PMC has no abstract for them either; it mirrors MEDLINE. Two
    survive the test, from 1975 and 1976. The rest cannot be judged: a 1958
    paper called "The treatment of vitiligo with psoralen derivatives" may be
    a trial, a case series or an opinion, and guessing would be inventing.
    """
    types = set(document.publication_types or [])
    if types & NOT_A_TRIAL:
        return False
    title = document.title or ""
    if _TITLE_ABOUT_TRIALS.search(title):
        return False
    if types & TRIAL_TYPES:
        return True
    abstract = document.abstract or ""
    if not abstract.strip():
        if _NOT_A_COMPARISON.search(title):
            return False
        return bool(_TITLE_DESIGN.search(title))
    return bool(_ENROLLED.search(abstract) or _ALLOCATED.search(abstract))


# A cancer, and an immunotherapy given for it. Both are needed: a melanoma
# trial of a cytotoxic drug that mentions depigmentation is reporting a rash,
# not an immune response to melanocytes, and 45 such papers are left out.
_ONCOLOGY_CONDITION = re.compile(
    r"melanoma|carcinoma|cancer|tumou?r|neoplas|lymphoma|leukemi|sarcoma|myeloma", re.I
)
_IMMUNOTHERAPY = re.compile(
    r"nivolumab|ipilimumab|pembrolizumab|atezolizumab|durvalumab|avelumab|tremelimumab"
    r"|checkpoint|anti-?PD-?1|anti-?PD-?L1|anti-?CTLA-?4|vaccin|dendritic\s+cell"
    r"|interleukin-2|\bIL-2\b|interferon|adoptive|tumou?r-infiltrating|CAR-?T|immunotherap"
    r"|\bTIL\b",
    re.I,
)
_DEPIGMENTATION = re.compile(r"vitilig|depigment|leukoderma|hypopigment|poliosis", re.I)


def observes_vitiligo_under_immunotherapy(document: Document) -> bool:
    """True when a cancer immunotherapy trial reports depigmentation.

    Checkpoint blockade and melanoma vaccines cause vitiligo through the same
    CD8 response to melanocyte antigens that causes the disease, and its
    appearance predicts durable response. That makes these trials mechanism
    evidence the disease's own literature cannot supply -- nobody randomises
    people to develop vitiligo -- while the disease being treated is a cancer,
    so they are not vitiligo trials and are held apart.
    """
    text = f"{document.title or ''} {document.abstract or ''}"
    if not _DEPIGMENTATION.search(text):
        return False
    if studies_vitiligo(document.title or "", document.abstract or ""):
        return False
    if not reports_a_trial(document):
        return False
    return bool(_ONCOLOGY_CONDITION.search(text) and _IMMUNOTHERAPY.search(text))


def outcome_trial_from_document(document: Document) -> Trial | None:
    """A record for a cancer trial in which vitiligo appeared.

    Conditions are left empty rather than guessed. The paper says which
    cancer in prose and this cannot read it reliably; the title carries it,
    and inventing a condition would put a wrong disease in a field readers
    filter on.
    """
    if not observes_vitiligo_under_immunotherapy(document):
        return None
    year = document.year
    return Trial(
        source=TrialSourceKind.PUBLICATION,
        source_id=str(document.source_id),
        brief_title=(document.title or "").strip() or None,
        summary=(document.abstract or "").strip() or None,
        conditions=[],
        countries=countries_of(document),
        study_type="INTERVENTIONAL",
        status="COMPLETED",
        has_results=False,
        start_date=str(year) if year else None,
        completion_date=str(year) if year else None,
        raw_metadata={
            "scope": VITILIGO_AS_OUTCOME_SCOPE,
            "pmid": str(document.source_id),
            "journal": document.journal,
            "year": year,
            "doi": document.doi,
            "publication_types": document.publication_types or [],
        },
    )


def trial_from_document(document: Document) -> Trial | None:
    """A trial record for a paper that reports one, or ``None``.

    ``None`` when the paper's subjects were not people with vitiligo, which
    neither the publication type nor the presence of the word settles: a
    melanoma immunotherapy paper names the disease because depigmentation was
    an adverse event, and six of them reached a corpus of vitiligo trials
    before the test asked whose disease it was.
    """
    if not studies_vitiligo(document.title or "", document.abstract or ""):
        return None
    if not reports_a_trial(document):
        return None
    year = document.year
    return Trial(
        source=TrialSourceKind.PUBLICATION,
        source_id=str(document.source_id),
        brief_title=(document.title or "").strip() or None,
        official_title=None,
        summary=(document.abstract or "").strip() or None,
        conditions=["Vitiligo"],
        countries=countries_of(document),
        study_type="INTERVENTIONAL",
        status="COMPLETED",
        # The registry sense of "results posted" does not apply: there is no
        # registry. What the paper reports lives in its abstract.
        has_results=False,
        start_date=str(year) if year else None,
        completion_date=str(year) if year else None,
        raw_metadata={
            "scope": PUBLISHED_ONLY_SCOPE,
            "pmid": str(document.source_id),
            "journal": document.journal,
            "year": year,
            "doi": document.doi,
            "publication_types": document.publication_types or [],
        },
    )


def unregistered_trials(
    documents: Iterable[Document], held_identifiers: Iterable[str]
) -> Iterator[Trial]:
    """A trial for each paper whose trial has no registry record we hold."""
    held = {comparison_key(i) for i in held_identifiers}
    for document in documents:
        if any(comparison_key(i) in held for i in registry_ids(document)):
            continue
        trial = trial_from_document(document)
        if trial is not None:
            yield trial
