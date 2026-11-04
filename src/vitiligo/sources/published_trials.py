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
from vitiligo.storage.models import Document, SourceKind, Trial, TrialSourceKind
from vitiligo.trials.countries import normalize_country
from vitiligo.trials.relevance import (
    ONCOLOGY_CONDITION,
    VITILIGO_AS_OUTCOME_SCOPE,
    fold,
    studies_vitiligo,
)

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
    r"\b(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida"
    r"|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland"
    r"|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada"
    r"|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio"
    r"|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee"
    r"|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b"
)

# A state or province by its postal code, which is how an American or Canadian
# address ends: "Chicago, IL.", "IL 60637", "Ottawa, ON". The code is read only
# after a comma or before a ZIP, because on its own "IN" is a preposition, "OR"
# a conjunction and "ME" a pronoun. Cased, for the same reason.
_SUBDIVISION_CODE = re.compile(
    r"(?:,\s*|\b)(A[LKZR]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]"
    r"|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY]|ON|QC|BC|AB|MB|SK|NS|NB|NL|PE)"
    r"(?=\s*\d{5}\b|[.,;)\s]*$|\s*\|)"
)
_CANADIAN_CODE = frozenset({"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"})

# Where a letterhead names the place but not the country. Every entry here was
# read off an affiliation this corpus holds and could not otherwise place: 66
# of them named an institution or a city and no country at all, and 11 of those
# say only "Lahore". A city's country is a fact, not an inference -- but the
# list is deliberately only as long as the evidence, so nothing is placed by
# guesswork about where an institution probably is.
_PLACES: tuple[tuple[str, str], ...] = (
    ("Pakistan", r"\blahore\b|\bmultan\b|\brawalpindi\b|\bgujranwala\b|\bsahiwal\b"),
    ("Egypt", r"\bain[- ]?shams\b|\bal[- ]?azhar\b|\bzagazig\b|\bmansoura\b"),
    (
        "India",
        r"\bchandigarh\b|\bjamnagar\b|\bsolapur\b|\bmaharashtra\b|\bbengaluru\b"
        r"|\bkarnataka\b|\bsrinagar\b|\bmumbai\b|\bbombay\b",
    ),
    ("Russia", r"\bsechenov\b|\bmoscow\b"),
    ("Brazil", r"\bsao paulo\b"),
    ("Poland", r"\blublin"),
    ("China", r"\bpeking\b|\bxingtai\b|\bnanfang\b|\bnanhua\b|\bhunan\b"),
    ("Japan", r"\bnagasaki\b"),
    ("Saudi Arabia", r"\briyadh\b|\bqassim\b|\bburaidah\b|\balmadinah\b|\btaibah\b"),
    ("Indonesia", r"\bsebelas maret\b|\bhang tuah\b"),
    ("Germany", r"\bfrankfurt\b|\bberlin\b"),
    ("United States", r"\bchicago\b|\bnew haven\b|\bwayne state\b|\bcarolinas\b"),
    ("Canada", r"\bottawa\b"),
    # "Cali, Columbia" is Colombia misspelled, and reading the misspelling
    # itself would make Colombians of Columbia University and British
    # Columbia. The city carries the fact without the collision.
    ("Colombia", r"\bcali\b"),
)
_PLACE_PATTERNS = tuple((n, re.compile(p)) for n, p in _PLACES)

# The country code at the end of an email address. One held paper's whole
# affiliation is "raffaele.cagiano@uniba.it." -- a domain is as much a
# statement of country as a city is.
_EMAIL_TLD = re.compile(r"@[\w.-]+\.([a-z]{2})\b")
_TLD_COUNTRY = {
    "it": "Italy",
    "fr": "France",
    "de": "Germany",
    "es": "Spain",
    "nl": "Netherlands",
    "be": "Belgium",
    "at": "Austria",
    "ch": "Switzerland",
    "pl": "Poland",
    "pt": "Portugal",
    "gr": "Greece",
    "tr": "Turkey",
    "ru": "Russia",
    "cn": "China",
    "jp": "Japan",
    "kr": "South Korea",
    "tw": "Taiwan",
    "in": "India",
    "pk": "Pakistan",
    "eg": "Egypt",
    "ir": "Iran",
    "il": "Israel",
    "br": "Brazil",
    "mx": "Mexico",
    "ca": "Canada",
    "au": "Australia",
    "nz": "New Zealand",
    "za": "South Africa",
    "sa": "Saudi Arabia",
    "th": "Thailand",
    "my": "Malaysia",
    "id": "Indonesia",
    "sg": "Singapore",
    "ng": "Nigeria",
}


def countries_of(document: Document) -> list[str]:
    """The countries the authors wrote in their affiliations.

    An affiliation ends with its country more often than it names a city, so
    the country names are searched for first and the rest of the line ignored.
    That left 66 held papers placed nowhere, because a national journal's
    letterhead names the institution and assumes the country: "Department of
    Dermatology, Ain Shams University" is Cairo to every reader of it, and
    eleven more say only "Lahore". Those are read from the place, and a
    postal code, an abbreviation and an email domain are read too.

    A US state is read as the United States, except where the affiliation is
    Georgian: "Georgia" is a state and a country, and the one paper here that
    means the country says Tbilisi.
    """
    affiliations: list[str] = []
    for author in document.authors or []:
        if isinstance(author, dict):
            affiliations += [str(a) for a in (author.get("affiliations") or [])]
    written = " | ".join(affiliations)
    text = fold(written)
    out: list[str] = []

    def add(name: str) -> None:
        canonical = normalize_country(name)
        if canonical and canonical not in out:
            out.append(canonical)

    for name, pattern in _COUNTRY_PATTERNS:
        if pattern.search(text):
            add(name)
    for name, pattern in _ABBREVIATION_PATTERNS:
        if pattern.search(written):
            add(name)
    if not out:
        # Only where the country is named nowhere, so a place never overrides
        # what the affiliation actually says.
        for name, pattern in _PLACE_PATTERNS:
            if pattern.search(text):
                add(name)
        for match in _EMAIL_TLD.finditer(text):
            country = _TLD_COUNTRY.get(match.group(1))
            if country:
                add(country)
    # Benin is a country and a Nigerian city, and every held paper that names
    # it means the city: "University of Benin Teaching Hospital, Benin City,
    # Edo State, Nigeria". Where both appear, the one the affiliation spells
    # out wins. This is the Georgia rule again, for neighbours rather than for
    # a state and a country.
    # A country's name that is also a place inside another country, where both
    # are found: the one the affiliation spells out as its own last word wins.
    # These three are what an audit of every country in three papers or fewer
    # turned up -- "Benin City, Edo State, Nigeria", "Armenia, Colombia" and
    # "Jamaica Plain, MA, USA" -- and the Georgia rule above is the fourth.
    for city, country in (("Benin", "Nigeria"), ("Armenia", "Colombia")):
        if city in out and country in out:
            out.remove(city)
    if "Georgia" not in out:
        codes = {m.group(1) for m in _SUBDIVISION_CODE.finditer(written)}
        if _US_STATE.search(text) or (codes - _CANADIAN_CODE):
            add("United States")
        if codes & _CANADIAN_CODE:
            add("Canada")
    return out


# Countries as an affiliation writes them, matched against folded text: every
# pattern below is lower case and carries no accent, so "Türkiye", "México"
# and "España" need no variant of their own.
#
# The list is every sovereign state, not only the countries seen so far. It
# held 73, and 30 more that this corpus already knew from a registry's
# location field had no pattern at all -- a paper written in Latvia, the
# Philippines, Sri Lanka, Qatar, Kenya or Ghana could not be placed however
# plainly it said so. An incomplete list fails silently, and under-counting a
# country is the one error this table exists to prevent.
_COUNTRY_NAMES: tuple[tuple[str, str], ...] = (
    ("Afghanistan", "\\bafghanistan\\b"),
    ("Albania", "\\balbania\\b"),
    ("Algeria", "\\balgeria\\b"),
    ("Andorra", "\\bandorra\\b"),
    ("Angola", "\\bangola\\b"),
    ("Argentina", "\\bargentina\\b"),
    ("Armenia", "\\barmenia\\b"),
    ("Australia", "\\baustralia\\b"),
    ("Austria", "\\baustria\\b"),
    ("Azerbaijan", "\\bazerbaijan\\b"),
    ("Bahrain", "\\bbahrain\\b"),
    ("Bangladesh", "\\bbangladesh\\b"),
    ("Belarus", "\\bbelarus\\b"),
    ("Belgium", "\\bbelgium\\b"),
    ("Belize", "\\bbelize\\b"),
    ("Benin", "\\bbenin\\b"),
    ("Bhutan", "\\bbhutan\\b"),
    ("Bolivia", "\\bbolivia\\b"),
    ("Bosnia and Herzegovina", "\\bbosnia\\b"),
    ("Botswana", "\\bbotswana\\b"),
    ("Brazil", "\\bbrazil\\b|\\bbrasil\\b"),
    ("Brunei", "\\bbrunei\\b"),
    ("Bulgaria", "\\bbulgaria\\b"),
    ("Burkina Faso", "\\bburkina faso\\b"),
    ("Cambodia", "\\bcambodia\\b"),
    ("Cameroon", "\\bcameroon\\b"),
    ("Canada", "\\bcanada\\b"),
    ("Chad", "\\bchad\\b"),
    ("Chile", "\\bchile\\b"),
    ("China", "\\bchina\\b"),
    ("Colombia", "\\bcolombia\\b"),
    ("Costa Rica", "\\bcosta rica\\b"),
    ("Croatia", "\\bcroatia\\b|\\bhrvatska\\b"),
    ("Cuba", "\\bcuba\\b"),
    ("Cyprus", "\\bcyprus\\b"),
    ("Czechia", "\\bczech\\b|\\bczechia\\b|\\bczech republic\\b"),
    ("Denmark", "\\bdenmark\\b"),
    ("Dominican Republic", "\\bdominican republic\\b"),
    ("Ecuador", "\\becuador\\b"),
    ("Egypt", "\\begypt\\b"),
    ("El Salvador", "\\bel salvador\\b"),
    ("Eritrea", "\\beritrea\\b"),
    ("Estonia", "\\bestonia\\b"),
    ("Ethiopia", "\\bethiopia\\b"),
    ("Fiji", "\\bfiji\\b"),
    ("Finland", "\\bfinland\\b"),
    ("France", "\\bfrance\\b"),
    ("French Guiana", "\\bfrench guiana\\b"),
    ("Gabon", "\\bgabon\\b"),
    ("Gambia", "\\bgambia\\b"),
    ("Georgia", "\\btbilisi\\b"),
    ("Germany", "\\bgermany\\b|\\bdeutschland\\b"),
    ("Ghana", "\\bghana\\b"),
    ("Greece", "\\bgreece\\b"),
    ("Guatemala", "\\bguatemala\\b"),
    ("Guinea", "\\bguinea\\b"),
    ("Haiti", "\\bhaiti\\b"),
    ("Honduras", "\\bhonduras\\b"),
    ("Hungary", "\\bhungary\\b"),
    ("Iceland", "\\biceland\\b"),
    ("India", "\\bindia\\b"),
    ("Indonesia", "\\bindonesia\\b"),
    ("Iran", "\\biran\\b"),
    ("Iraq", "\\biraq\\b"),
    ("Ireland", "\\bireland\\b"),
    ("Israel", "\\bisrael\\b"),
    ("Italy", "\\bitaly\\b|\\bitalia\\b"),
    ("Ivory Coast", "\\bivory coast\\b|\\bcote d.?ivoire\\b"),
    ("Jamaica", "\\bjamaica\\b(?!\\s+plain)"),
    ("Japan", "\\bjapan\\b"),
    ("Jordan", "\\bjordan\\b"),
    ("Kazakhstan", "\\bkazakhstan\\b"),
    ("Kenya", "\\bkenya\\b"),
    ("Kuwait", "\\bkuwait\\b"),
    ("Kyrgyzstan", "\\bkyrgyzstan\\b"),
    ("Laos", "\\blaos\\b|\\blao pdr\\b"),
    ("Latvia", "\\blatvia\\b"),
    ("Lebanon", "\\blebanon\\b"),
    ("Libya", "\\blibya\\b"),
    ("Liechtenstein", "\\bliechtenstein\\b"),
    ("Lithuania", "\\blithuania\\b"),
    ("Luxembourg", "\\bluxembourg\\b"),
    ("Madagascar", "\\bmadagascar\\b"),
    ("Malawi", "\\bmalawi\\b"),
    ("Malaysia", "\\bmalaysia\\b"),
    ("Maldives", "\\bmaldives\\b"),
    ("Mali", "\\bmali\\b"),
    ("Malta", "\\bmalta\\b"),
    ("Mauritania", "\\bmauritania\\b"),
    ("Mauritius", "\\bmauritius\\b"),
    ("Mexico", "\\bmexico\\b|\\bm[ee]xico\\b"),
    ("Moldova", "\\bmoldova\\b"),
    ("Monaco", "\\bmonaco\\b"),
    ("Mongolia", "\\bmongolia\\b"),
    ("Montenegro", "\\bmontenegro\\b"),
    ("Morocco", "\\bmorocco\\b|\\bmaroc\\b"),
    ("Mozambique", "\\bmozambique\\b"),
    ("Myanmar", "\\bmyanmar\\b|\\bburma\\b"),
    ("Namibia", "\\bnamibia\\b"),
    ("Nepal", "\\bnepal\\b"),
    ("Netherlands", "\\bnetherlands\\b|\\bthe netherlands\\b|\\bholland\\b"),
    ("New Zealand", "\\bnew zealand\\b"),
    ("Nicaragua", "\\bnicaragua\\b"),
    ("Niger", "\\bniger\\b"),
    ("Nigeria", "\\bnigeria\\b"),
    ("North Macedonia", "\\bnorth macedonia\\b|\\bmacedonia\\b"),
    ("Norway", "\\bnorway\\b"),
    ("Oman", "\\boman\\b"),
    ("Pakistan", "\\bpakistan\\b"),
    ("Palestine", "\\bpalestin"),
    ("Panama", "\\bpanama\\b"),
    ("Papua New Guinea", "\\bpapua new guinea\\b"),
    ("Paraguay", "\\bparaguay\\b"),
    ("Peru", "\\bperu\\b|\\bper[uu]\\b"),
    ("Philippines", "\\bphili?l?ippines\\b"),
    ("Poland", "\\bpoland\\b"),
    ("Portugal", "\\bportugal\\b"),
    ("Puerto Rico", "\\bpuerto rico\\b"),
    ("Qatar", "\\bqatar\\b"),
    ("Reunion", "\\breunion\\b"),
    ("Romania", "\\bromania\\b"),
    ("Russia", "\\brussia\\b|\\brussian federation\\b|\\brossiya\\b"),
    ("Rwanda", "\\brwanda\\b"),
    ("Saudi Arabia", "\\bsaudi arabia\\b"),
    ("Senegal", "\\bsenegal\\b"),
    ("Serbia", "\\bserbia\\b"),
    ("Sierra Leone", "\\bsierra leone\\b"),
    ("Singapore", "\\bsingapore\\b"),
    ("Slovakia", "\\bslovakia\\b|\\bslovak republic\\b"),
    ("Slovenia", "\\bslovenia\\b"),
    ("Somalia", "\\bsomalia\\b"),
    ("South Africa", "\\bsouth africa\\b"),
    ("South Korea", "\\bkorea\\b|\\bsouth korea\\b|\\brepublic of korea\\b"),
    ("Spain", "\\bspain\\b|\\bespa[nn]a\\b|\\bespana\\b"),
    ("Sri Lanka", "\\bsri ?lanka\\b|\\bceylon\\b"),
    ("Sudan", "\\bsudan\\b"),
    ("Suriname", "\\bsuriname\\b"),
    ("Sweden", "\\bsweden\\b"),
    ("Switzerland", "\\bswitzerland\\b"),
    ("Syria", "\\bsyria\\b"),
    ("Taiwan", "\\btaiwan\\b"),
    ("Tajikistan", "\\btajikistan\\b"),
    ("Tanzania", "\\btanzania\\b"),
    ("Thailand", "\\bthailand\\b"),
    ("Togo", "\\btogo\\b"),
    ("Trinidad and Tobago", "\\btrinidad\\b"),
    ("Tunisia", "\\btunisia\\b|\\btunisie\\b"),
    ("Turkey", "\\bturkey\\b|\\bt[uu]rkiye\\b"),
    ("Turkmenistan", "\\bturkmenistan\\b"),
    ("Uganda", "\\buganda\\b"),
    ("Ukraine", "\\bukraine\\b"),
    ("United Arab Emirates", "\\bunited arab emirates\\b"),
    ("United Kingdom", "\\bunited kingdom\\b|\\bengland\\b|\\bscotland\\b|\\bwales\\b"),
    ("United States", "\\bunited states\\b"),
    ("Uruguay", "\\buruguay\\b"),
    ("Uzbekistan", "\\buzbekistan\\b"),
    ("Venezuela", "\\bvenezuela\\b"),
    ("Viet Nam", "\\bvietnam\\b|\\bviet nam\\b|\\bviet ?nam\\b"),
    ("Yemen", "\\byemen\\b"),
    ("Zambia", "\\bzambia\\b"),
    ("Zimbabwe", "\\bzimbabwe\\b"),
)
_COUNTRY_PATTERNS = tuple((n, re.compile(p)) for n, p in _COUNTRY_NAMES)

# Abbreviations, matched against the affiliation as written rather than folded.
# Lower-cased, "UK" would match the word "uk" and "IND" the first syllable of
# an Indonesian or Indian word; cased, each one is unambiguous. "KSA" and
# "IND" are here because three held papers write only those: "Qassim
# University, Buraidah, KSA" names no other country.
_COUNTRY_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    ("United States", "\\bU\\.?S\\.?A\\.?\\b"),
    ("United Kingdom", "\\bU\\.?K\\.?\\b"),
    ("United Arab Emirates", "\\bU\\.?A\\.?E\\.?\\b"),
    ("China", "\\bP\\.?R\\.? China\\b"),
    ("Saudi Arabia", "\\bKSA\\b"),
    ("India", "\\bIND\\b"),
)
_ABBREVIATION_PATTERNS = tuple((n, re.compile(p)) for n, p in _COUNTRY_ABBREVIATIONS)


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
# A title that names how the arms were formed states the design outright, and
# nothing else in the title can take that back: "Artificial intelligence-driven
# comparative efficacy of topical crisaborole versus halometasone for vitiligo:
# A randomized and noninferiority study" is a trial, whatever its first words
# are about.
#
# "Controlled study" is not here. In observational writing it means a
# case-control study -- "Anti-thyroid peroxidase antibody and vitiligo: a
# controlled study" -- so it goes with the weaker wording below, where it
# still earns a 1975 trimethylpsoralen trial its place.
_TITLE_TRIAL = re.compile(
    r"""
      double[- ]blind | single[- ]blind | placebo[- ]controlled | vehicle[- ]controlled
    | controlled\s+trial | randomi[sz]ed | cross[- ]?over
    | a\s+(?:clinical\s+|therapeutic\s+)?trial\b | clinical\s+trial
    | split[- ]body | left[- ]right
    # The same statement where the paper is not written in Latin script.
    # 疗效观察 is "observation of therapeutic effect" and 临床观察 "clinical
    # observation": in a Chinese title both declare a study of a treatment in
    # patients, the way "a clinical trial" does in English.
    #
    # 随机 (randomised), 双盲, 安慰剂 and the Russian equivalents were here and
    # are not: across 12,086 documents not one verdict turned on them, because
    # a Chinese title that says 随机 says 临床观察 or 疗效观察 too, and the
    # Chinese trials that do not reach Crossref at all are in CNKI, which this
    # project cannot read. They would have been guards against nothing.
    | 疗效观察 | 临床观察 | 临床研究
    """,
    re.X | re.I,
)

# A head-to-head comparison only implies one. Leaving it out lost 30 papers
# whose title is the only record they have -- "Platelet-rich plasma and
# follicular transplantation versus follicular transplantation", "A
# comparative pilot study of dipstick versus open-spray cryotherapy".
_TITLE_COMPARISON = re.compile(
    r"""
      comparative\s+(?:study|trial) | controlled\s+study
    | \bversus\b | \bvs\.? | compared\s+(?:with|to) | comparison\s+of
    """,
    re.X | re.I,
)

# Diseases whose names contain a comparison word. "Graft-versus-host disease"
# is not a comparison of graft with host.
_NOT_A_COMPARISON = re.compile(r"graft[- ]versus[- ]host|host[- ]versus[- ]graft", re.I)

# A trial gives somebody something. Either the title claims a therapeutic
# effect, or it names what was given -- surgical trials claim nothing and name
# only the procedures they put side by side: "Blister roof grafting versus
# epidermal cell suspension in stable vitiligo", "Comparison of follicular
# unit extraction vs. plucking of hair follicles". Requiring the claim alone
# rejected five of those.
_NAMES_A_TREATMENT = re.compile(
    r"""
    # What it claims to have done to somebody.
      efficac | effectiv | treatment | treating | treated | therap | repigment
    | pigmentation | tolerab | \bdose | management\s+of | regimen | intervention
    | monotherap | placebo | supplement | irritancy
    # How it was given.
    | topical | \boral\b | systemic | intraven | intralesional | injection
    | irradiation | exposure | occlusive
    # What was given, where the title names a modality rather than a drug.
    | graft | dermabras | laser | suspen | transplant | micro-?needl | dermaroller
    | cryotherap | phototherap | photochemotherap | \bUV[AB]?\b | ultraviolet
    | psoralen | PUVA | KUVA | excimer | punch | tattoo | moxibustion | needling
    | ointment | \bcream\b | \bgel\b | tincture | blister | platelet[- ]rich
    | lepa | vamana | virechana | chikitsa
    # Romance languages drop the h from phototherapy -- "fototerapia" is not
    # "phototherap" to a pattern -- and name the treatment with a word of
    # their own. German's "Heliotherapie" needs nothing: it still has therap.
    | terapi | tratamien | tratamen | traitement | behandlung | salbe
    | pomada | \bcrema\b | unguento
    """,
    re.X | re.I,
)

# What is left after the treatment test. Of 49 phrases tried here, 27 never
# changed a verdict once the title had to name a treatment, and another six --
# "serum", "biomarker", "quality of life", "anxiety", "psychosocial",
# "imaging" -- rejected more real trials than studies: "Treatment of vitiligo
# patients by excimer laser improves patients' quality of life", "Efficacy and
# safety of ritlecitinib in vitiligo patients across Fitzpatrick skin types
# with biomarkers", "Three-dimensional imaging for facial vitiligo: Results
# from a phase 2 randomized controlled trial". These sixteen are the ones that
# were right every time they fired.
#
# "Correlat" is right four times in five; it loses "Correlation of clinical
# efficacy and psychosocial impact on vitiligo patients by excimer laser
# treatment" to keep out three re-analyses of trials already held.
_NOT_A_TREATMENT_STUDY = re.compile(
    r"""
      pathogenesis | prevalence | \bsurvey\b | oxidative\s+stress | correlat
    | immunolog\w+\s+profile | histopathological\s+char | baseline\s+differences
    | neural\s+network | image\s+analysis | differential\s+diagnosis
    | cross[-\u2010\u2011 ]sectional
    | \blevels?\s+(?:in|of)\b | serum\s+level
    | (?:assessment|evaluation|comparison|estimation)\s+of\s+serum
    | segmental\s+(?:and|versus|vs\.?)\s+non[- ]?segmental
    # A paper can name a treatment and claim an effect on something that is
    # not a patient: a target, an omics layer, a questionnaire, a genotype.
    | therapeutic\s+targets? | polymorphism | biomarkers?\s+associated
    | multi-?omics | proteomic | transcriptomic | metabolomic | bioinformatic
    | single-?cell | development\s+and\s+validation | computer-?aided
    # What a paper claims when it followed people who were treated but gave
    # them nothing: their risk, their perspective, the pattern of their
    # disease, the strata of a severity scale. "Predict" and "expression"
    # were tried here and are not: "Suction blister grafting for vitiligo:
    # efficacy and clinical predictive factors" is a trial, and so is
    # "Expression of Janus Kinase 1 before and after narrow band UVB".
    | perspectives?\b | insights\s+from | \brisk\s+of\b | patterns\s+in\b
    | severity\s+strata | global\s+assessment
    """,
    re.X | re.I,
)

# A trial is run in people. Nothing else in the record outranks this: "fire
# needle therapy on vitiligo induced by hydroquinone in modeled mice" and
# "topical Mycophenolate mofetil on hydroquinone-induced depigmentation in
# Guinea pigs and mice" both name a treatment and claim an effect, and a
# depigmented mouse is not a participant. "Keratinocyte" cannot go here: the
# melanocyte-keratinocyte transplant procedure is surgery on people, and
# listing the word cost 21 real surgical trials. Nor can "in vitro" or "cell
# line": a melanoma vaccine of "peptide-pulsed dendritic cells generated in
# vitro" and one of "a genetically modified interleukin 2-producing melanoma
# cell line" are both phase I trials in people, and the laboratory is where
# the product was made, not where the trial was run.
#
# Mendelian randomisation belongs here for the same reason: it randomises
# nothing and nobody. It is an analysis of inherited variants in people who
# were never assigned anything, and the word "randomization" in its name
# would otherwise settle the question by itself.
_NOT_IN_PEOPLE = re.compile(
    r"""
      \bmice\b | \bmouse\b | murine | \brats?\b | guinea\s+pigs? | zebrafish
    | \brabbits?\b | \bswine\b | \bporcine\b | B16[A-Z]?\d*
    | reconstructed\s+(?:human\s+)?skin | mendelian\s+randomi[sz]ation
    """,
    re.X | re.I,
)

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
_TITLE_ABOUT_TRIALS = re.compile(
    r"\btrials\b|systematic\s+review|meta-?analys|comment\s+on|^comment:"
    r"|subgroup\s+analysis|pooled\s+(?:results|analysis|subgroup)|post\s*-?hoc"
    r"|trial\s+landscape|trend\s+analysis|case\s+report|^incorrect\b|^erratum"
    r"|guidelines?\s+and\s+consensus|process\s+evaluation",
    re.I,
)


def reports_a_trial(document: Document) -> bool:
    """True when the paper reports a trial rather than discussing trials.

    PubMed labels only some of them. Searching the text instead for
    "randomised" and "placebo" finds 545 more papers, and 71 are reviews, 42
    meta-analyses and 37 letters: the word appears because they are *about*
    trials. The publication type settles those, in both directions -- where
    PubMed has called it a trial there is nothing left to decide.

    Where it has not, the title has to name a treatment first, because a trial
    gives somebody something. This is the test that does the work. Without it
    the abstract decided, and an abstract cannot: "148 patients were
    classified" and "148 patients were randomised" are the same sentence to a
    pattern, so every case-control study passed. The corpus was holding 120
    such papers as trials -- HLA typing, autoantibody titres, quality-of-life
    scales, electron microscopy, "[The pathogenesis of vitiligo]" -- and 116
    of them name no treatment at all. Of the four that do, two are
    re-analyses of trials held elsewhere and two are retrospective reviews.

    Then the abstract has to count the people enrolled or say how they were
    assigned. Either will do, not both: requiring both rejected the
    ruxolitinib and narrow-band UVB study, which is single-arm and open-label
    and so allocates nobody, along with 333 other records already held.

    Where there is no abstract either, the title has to compare. That is the
    whole record for 399 of the 401 vitiligo papers before 1970, and Europe
    PMC has no abstract for them either; it mirrors MEDLINE. Two survive the
    test, from 1975 and 1976. The rest cannot be judged: a 1958 paper called
    "The treatment of vitiligo with psoralen derivatives" may be a trial, a
    case series or an opinion, and guessing would be inventing.
    """
    types = set(document.publication_types or [])
    if types & NOT_A_TRIAL:
        return False
    # Folded, for the same reason the disease gate folds: "Efficacité de
    # l'association baricitinib et photothérapie versus photothérapie seule"
    # names a design and a treatment, and "phototherap" matches neither
    # spelling of the word it is written with.
    title = fold(document.title)
    if _TITLE_ABOUT_TRIALS.search(title):
        return False
    if _NOT_IN_PEOPLE.search(title):
        return False
    if _TITLE_TRIAL.search(title):
        return True
    # Before the publication type, not after it. PubMed types "Prevalence of
    # vitiligo in Brazil-A population survey" and "Turnover in humans of
    # iodine- and cobalamin-labeled transcobalamin I" as clinical trials, and
    # deferring to that let fifteen measurements in: pathogenesis, serum
    # vitamin D, oxidative stress, a neural network, a confocal-microscopy
    # differential diagnosis. The type says a trial happened somewhere; the
    # title says what this paper measured, and it is the more specific claim.
    # A title that names a design is checked first, so "randomised" still
    # outranks both.
    if _NOT_A_TREATMENT_STUDY.search(title) or _NOT_A_COMPARISON.search(title):
        return False
    if types & TRIAL_TYPES:
        return True
    # A checkpoint inhibitor is a treatment too, and those papers name the
    # drug where a vitiligo paper names a modality. The oncology stratum's own
    # vocabulary is the list of them; writing a second one here is how the
    # skin-disease list came to disagree with itself over 88 trials.
    if not (_NAMES_A_TREATMENT.search(title) or _IMMUNOTHERAPY.search(title)):
        return False
    abstract = fold(document.abstract)
    if abstract.strip():
        return bool(_ENROLLED.search(abstract) or _ALLOCATED.search(abstract))
    return bool(_TITLE_COMPARISON.search(title))


# A cancer, and an immunotherapy given for it. Both are needed: a melanoma
# trial of a cytotoxic drug that mentions depigmentation is reporting a rash,
# not an immune response to melanocytes, and 45 such papers are left out.
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
    text = fold(f"{document.title or ''} {document.abstract or ''}")
    if not _DEPIGMENTATION.search(text):
        return False
    if studies_vitiligo(document.title or "", document.abstract or ""):
        return False
    if not reports_a_trial(document):
        return False
    return bool(ONCOLOGY_CONDITION.search(text) and _IMMUNOTHERAPY.search(text))


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
            # A Crossref paper has a DOI and no PMID; recording one under
            # the other's name would make the identifier unusable.
            "pmid": (str(document.source_id) if document.source == SourceKind.PUBMED else None),
            "journal": document.journal,
            "year": year,
            "doi": document.doi,
            "publication_types": document.publication_types or [],
        },
    )


# What the paper says it did. A retrospective comparison of two treatments is
# a study of this disease and belongs in the corpus, but it assigned nobody to
# anything, so a count of trials that included it would overstate by 45.
_RETROSPECTIVE = re.compile(
    r"\bretrospectiv|chart\s+review|medical\s+records?\s+(?:were\s+)?(?:review|retriev)"
    r"|record\s+review|case[- ]control|cross[- ]sectional|registry\s+study"
    r"|database\s+(?:study|analysis)",
    re.I,
)
_PROSPECTIVE = re.compile(r"\bprospectiv|randomi[sz]ed|double[- ]blind|placebo", re.I)


def design_of(document: Document) -> str:
    """``"retrospective"`` where the paper says so and does not say otherwise.

    Nine papers say both -- "a prospective arm and a retrospective cohort" --
    and those keep the benefit of the doubt, because a paper that says
    randomised is reporting an assignment whatever else it did.
    """
    text = fold(f"{document.title or ''} {document.abstract or ''}")
    if _RETROSPECTIVE.search(text) and not _PROSPECTIVE.search(text):
        return "retrospective"
    return "prospective_or_unstated"


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
            "design": design_of(document),
            "pmid": (str(document.source_id) if document.source == SourceKind.PUBMED else None),
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
