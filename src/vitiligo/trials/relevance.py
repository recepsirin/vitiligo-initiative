"""Whether a registry record is a vitiligo trial, when it never says "vitiligo".

Searching ICTRP for "vitiligo" returns 1,022 trials. Searching the names the
disease carries elsewhere returns more: Ayurvedic trials register it as
*Switra*, Indian records as *leucoderma*, and ``is_about_vitiligo`` — which
asks only whether the literal word "vitiligo" appears — rejects every one of
them. Six real trials were being missed that way. Five treat the disease --
one of them scoring its result as VASI, the same scale the JAK trials use --
and the sixth, CTRI/2020/09/027631, is a Siddha diagnostic study that enrols
leucoderma patients beside psoriasis and eczema patients and registers its
condition as psoriasis. It is the weakest of the six and it is in, because it
names leucoderma in its title and enrols those patients; its own condition
field travels with it and says what it says.

The other half of the problem is that those names are not the disease's alone.
Two sweeps over 50 of those names returned 640 records we did not hold, and
622 were something else: gingival depigmentation, orthodontic white spot
lesions, oral leukoplakia, cosmetic skin-lightening safety tests. So the gate
has three tiers rather than one list.

**Decisive** names mean the disease and nothing else. *Switra* is the
Ayurvedic term for vitiligo; a trial that says it is one.

**Suggestive** names are the disease most of the time and another condition
the rest. "Leukoderma" is ICD L81.5, which covers depigmentation from a burn
or a chemical as readily as the autoimmune disease, so it is accepted only
when nothing disqualifies it.

**Disqualifiers** are the other causes and the other tissues. Post-burn
leukoderma and rhododenol-induced leukoderma are melanocyte loss with a known
external cause; idiopathic guttate hypomelanosis, pityriasis and hypopigmented
mycosis fungoides are different diseases, and the leukoderma listed beside
actinic keratosis and cutis laxa senilis is sun-damaged skin. Treating any of
them as vitiligo would put their response rates in the same table as a JAK
inhibitor's, which is the comparison this project exists to get right.

A name is accepted when it is how some registry actually writes *this*
disease, and dropped when it names something else more often or names the
disease never. "Achromia" and "hypomelanosis" are gone on the second count:
achromia matched nothing at all, and hypomelanosis matched only guttate
hypomelanosis, so its whole effect was to accept records the disqualifiers
then had to reject.

"White patch" is kept on the first count even though no record needs it
today. CTRI/2018/04/013496 registers its condition as "null- white patches
over the body" and is saved only by the word Switra in its title; a sibling
record without that word would be lost, and free-text conditions like that
one are how CTRI writes most of these. It brings oral leukoplakia with it --
which is described as "white or grey patches in the mouth" -- and that is
what the one tissue disqualifier is for.

Of the 640 records the two sweeps returned, 23 carried a suggestive name
*and* a disqualifier. Those 23 are the only records any disqualifier affects;
every cosmetic patch test and orthodontic white-spot study is refused for
naming the disease nowhere at all. Several disqualifiers have never had to
fire, and they stay: a missing accepted name loses a trial, which shows up as
a smaller corpus, while a missing disqualifier puts another disease's
response rate in the table beside a JAK inhibitor's, which shows up as a
wrong answer.

That is also why two obvious synonyms are absent from every tier.
"Depigmentation" and "white spot" matched 129 and 266 unheld records and not
one was a vitiligo trial another name had not already found: the first is how
dentistry describes bleaching gum tissue, the second how orthodontics
describes enamel demineralising under a bracket. Accepting either would make
the gate depend entirely on the disqualifier list being exhaustive, which no
list of other diseases can be.
"""

from __future__ import annotations

import re
import unicodedata

from vitiligo.storage import Trial
from vitiligo.storage.models import TrialSourceKind

# Names that mean this disease and no other.
#
# The misspellings are a safety net. ChiCTR2300072713 registered its condition
# as "vtiligo", ChiCTR2400086844 as "Vilitigo" and ChiCTR-TRC-14004092 as
# "Vitligo"; all three spell it correctly in their titles, so none of them
# needs this list today, and a record that misspells it in both places would.
# They are listed rather than matched by a tolerant pattern because a pattern
# loose enough to catch "vilitigo" -- where the l precedes the t -- is loose
# enough to catch words that are not the disease at all.
DECISIVE = re.compile(
    r"""
    vitilig                      # every Latin-script spelling begins this way
    | vtiligo | vilitigo | vitligo  # the three misspellings in the corpus
    | sh?witra                   # Ayurvedic; "shvitra" always appears beside it
    # The one script fold() cannot reach that this corpus actually writes in.
    # Chinese 白斑 is not here -- on its own it means a white patch anywhere,
    # oral leukoplakia included -- and neither are the traditional-Chinese
    # 白癜風, the Japanese 尋常性白斑 or the Russian витилиго: none appears in
    # any of the 17,124 titles, conditions and keywords this corpus holds.
    | 白癜风
    """,
    re.X,
)


def fold(text: str | None) -> str:
    """Lower-cased, with every diacritic removed.

    Spanish and Portuguese write the disease "vitíligo", and the accent put
    four held papers beyond the gate's reach: "Lesiones faciales de vitíligo
    tras la administración de la vacuna frente a SARS-CoV-2" names the
    disease as plainly as any English title. French does the same to the
    treatment words -- "photothérapie" is not "phototherap" to a pattern.

    Folding is what a list of spellings cannot be: complete. Every pattern in
    this project that reads free text reads it folded, so one rule covers
    every language that writes Latin script with marks on it. Cyrillic and
    CJK are untouched by the fold and are named above instead.
    """
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(ch)
    ).lower()


# Names this disease shares with others, accepted when nothing disqualifies.
SUGGESTIVE = re.compile(r"leukoderma | leucoderma | white\s+patch", re.X)

# Another cause, another disease, or another tissue entirely.
DISQUALIFYING = re.compile(
    r"""
    # Another cause of the same melanocyte loss.
      post[\s-]?burn | burn\s+scar | chemical\s+leuk | occupational
    | actinic | photoag | photodamag | nonionizing | cutis\s+laxa  # sun-damaged skin
    # The skin-whitening agent withdrawn in 2013, spelled both ways in the
    # literature. Reading only "rhododenol" let in an open-label bimatoprost
    # study of "rhododendrol-induced refractory leukoderma".
    | rhododen\w*ol
    # Another disease that also presents as a pale patch.
    | idiopathic\s+guttate | \bigh\b | pityriasis | bahaq
    | mycosis\s+fungoides | lichen\s+sclerosus | nevus\s+depigmentosus
    | striae\s+distensae | stretch\s+marks
    | dowling[\s-]?degos | acropigmentation | kitamura
    # Leukoderma in a melanoma paper is the immunotherapy's doing, and those
    # trials are held as their own stratum, keyed on the word vitiligo.
    | melanoma
    # Another disease, treated, whose complication is the pale patch. A laser
    # trial in melasma that counts punctate leukoderma as a safety outcome is
    # a melasma trial. These only ever fire where "leukoderma" or "white
    # patch" is the whole of the evidence, so a trial that says vitiligo is
    # untouched by them.
    | melasma
    # Another tissue. One word covers it: every oral record in the sweep
    # says "oral", the leukoplakia ones as "leukoplakia ... of oral
    # epithelium". Gingival and orthodontic studies need no entry at all --
    # they reach this list only if something accepted them first, and they
    # name the disease nowhere.
    | \boral\b
    """,
    re.X,
)


def names_vitiligo(text: str) -> bool:
    """True when this text names vitiligo rather than something like it."""
    lowered = fold(text)
    if DECISIVE.search(lowered):
        return True
    return bool(SUGGESTIVE.search(lowered)) and not DISQUALIFYING.search(lowered)


def _subject(trial: Trial) -> str:
    """What the registry says the trial is about.

    Conditions, keywords and titles only. Eligibility text is excluded
    because a criterion is as often an exclusion as an inclusion: one record
    reached us with "any previous surgical treatments for post burn
    leukoderma" as the only place leukoderma appeared.
    """
    return " | ".join(
        [
            *(trial.conditions or []),
            *(trial.keywords or []),
            trial.brief_title or "",
            trial.official_title or "",
        ]
    )


def is_vitiligo_trial(trial: Trial) -> bool:
    """True when the record is a vitiligo trial under any of the disease's names."""
    return names_vitiligo(_subject(trial))


# What a trial is held for. A trial of a JAK inhibitor in rheumatoid arthritis
# is in the corpus because the drug class is the same, not because the disease
# is, and its metadata says so.
#
# Two such scopes exist. ``jak_class`` is every trial of the ten JAK
# inhibitors, in any disease, because that class is what the scenario model is
# built on. ``derm_drug`` is every trial of a drug this project holds a
# vitiligo prior for -- tacrolimus, calcipotriol, methotrexate, afamelanotide
# and the rest -- restricted to skin and autoimmune disease, because
# "metformin in type 2 diabetes" is a trial of a vitiligo prior and is not
# about vitiligo in any useful sense.
DRUG_CLASS_SCOPE = "jak_class"
DERM_DRUG_SCOPE = "derm_drug"
DRUG_CLASS_SCOPES: frozenset[str] = frozenset({DRUG_CLASS_SCOPE, DERM_DRUG_SCOPE})

# A vitiligo trial that was never registered, reconstructed from its paper.
# It belongs to the vitiligo corpus -- it is a trial of this disease -- but
# it is not a registered trial, and a count of registrations must say so.
PUBLISHED_ONLY_SCOPE = "published_only"

# A cancer immunotherapy trial in which vitiligo appeared. Checkpoint
# blockade and melanoma vaccines cause depigmentation through the same CD8
# response to melanocyte antigens, and it predicts durable response, so these
# are the mechanism evidence that the disease's own literature cannot supply.
# The disease treated is a cancer, so they are not vitiligo trials.
VITILIGO_AS_OUTCOME_SCOPE = "vitiligo_outcome"

# Every scope that is in the corpus for a reason other than being a trial of
# this disease. A figure about vitiligo trials excludes all of them.
NON_VITILIGO_SCOPES: frozenset[str] = DRUG_CLASS_SCOPES | {VITILIGO_AS_OUTCOME_SCOPE}


def is_drug_class_trial(trial: Trial) -> bool:
    """True when the trial is held for its drug rather than its disease."""
    return str((trial.raw_metadata or {}).get("scope") or "") in DRUG_CLASS_SCOPES


def in_vitiligo_corpus(trial: Trial) -> bool:
    """True when the trial counts towards a figure about vitiligo trials.

    This is the filter behind every published count. Without it, importing a
    drug class's 1,358 trials in other diseases would silently turn "1,027
    vitiligo trials" into a number about rheumatoid arthritis, and 77 melanoma
    immunotherapy trials would turn it into one about melanoma.
    """
    return str((trial.raw_metadata or {}).get("scope") or "") not in NON_VITILIGO_SCOPES


# The skin and autoimmune diseases whose trials of a vitiligo drug are worth
# holding, and the oncology words that mean the trial is chemotherapy.
#
# Both lists are needed because a search cannot be trusted to answer the
# question it was asked. Requesting these drugs "in a list of skin diseases"
# returned 2,974 trials, of which 1,579 were oncology -- 420 breast cancer at
# the top, because methotrexate and fluorouracil are chemotherapy drugs and
# the condition expression expands much further than it reads.
_SKIN_DISEASE = re.compile(
    r"""
      vitilig | psoriasis | psoriatic | atopic\s+dermatit | dermatitis,\s*atopic | eczema
    | alopecia\s+areata | lichen\s+planus | lichen\s+sclerosus | hidradenitis | urticaria
    | pemphig | morphea | localized\s+scleroderma | cutaneous\s+lupus | discoid\s+lupus
    | seborrh | contact\s+dermatit | hypopigmentat | prurigo
    | rosacea | acne | granuloma\s+annulare | pityriasis | leukoderma | dermatomyositis
    """,
    re.X | re.I,
)
_ONCOLOGY = re.compile(
    r"cancer|neoplas|carcinoma|lymphoma|leukemia|leukaemia|melanoma|sarcoma|myeloma|tumou?r"
    r"|mycosis\s+fungoides|sezary|s..zary",
    re.I,
)


def treats_skin_disease(trial: Trial) -> bool:
    """True when the record's own conditions are a skin or autoimmune disease.

    Checked against the conditions the record carries, not the search that
    found it. A disease that is both is refused: mycosis fungoides is a
    lymphoma of the skin, and its population is an oncology population
    whatever organ it presents in. The 33 such records are not worth the
    1,579 oncology trials they would let in beside them.
    """
    conditions = " | ".join([*(trial.conditions or []), *(trial.keywords or [])])
    if _ONCOLOGY.search(conditions):
        return False
    return bool(_SKIN_DISEASE.search(conditions))


def is_registered(trial: Trial) -> bool:
    """True when a registry holds this trial, rather than only a journal.

    The 18 published Turkish vitiligo trials name no registry id between
    them, and fourteen of the eighteen predate 2010. They are vitiligo trials
    and they are not registered trials, and any figure about registration has
    to keep the two apart.

    What decides it is where the record came from, not which stratum it sits
    in. Reading one scope name called all 62 cancer immunotherapy trials
    registered, and every one of those was reconstructed from a paper and
    names no registry either.
    """
    return trial.source != TrialSourceKind.PUBLICATION


# How near a drug-class trial sits to this disease. "Held for the drug" is
# true of all of them and says too little: ritlecitinib in alopecia areata
# and ruxolitinib in myelofibrosis are not equally informative about vitiligo,
# and a figure that counted them together would imply they were.
CLOSE_RELATION = "skin"
SAFETY_RELATION = "class_safety"
DISTANT_RELATION = "distant"

# Another autoimmune disease on the same drug. The class's boxed warning comes
# from ORAL Surveillance, a tofacitinib trial in rheumatoid arthritis, so this
# is where a vitiligo prescriber's safety evidence actually lives.
_SAFETY = re.compile(
    r"arthritis|lupus|colitis|crohn|spondyl|sjogren|thyroid|diabetes|uveitis"
    r"|myositis|sarcoid|autoimmun|celiac|vasculitis|behcet",
    re.I,
)


def drug_class_relation(trial: Trial) -> str:
    """How near this drug-class trial sits to vitiligo.

    ``skin`` is ``_SKIN_DISEASE``, the same list that decides whether a
    prior drug's trial is worth holding at all -- written twice, it drifted,
    and 88 acne and rosacea trials were called distant by one copy and skin
    by the other. Alopecia areata matters most within it: ritlecitinib and
    baricitinib are approved in it, ritlecitinib is in vitiligo trials, and it
    shares the CD8 and interferon-gamma mechanism. ``class_safety`` means another autoimmune disease on the same
    molecule, which is where the class's adverse-event evidence is.
    ``distant`` is the rest: ruxolitinib in myelofibrosis is JAK2 inhibition
    of a driver mutation in a cancer at far higher exposure, and it shares a
    molecule with vitiligo and very little else.
    """
    conditions = " | ".join([*(trial.conditions or []), *(trial.keywords or [])])
    if _SKIN_DISEASE.search(conditions):
        return CLOSE_RELATION
    if _SAFETY.search(conditions):
        return SAFETY_RELATION
    return DISTANT_RELATION


# Vitiligo as the population a paper studied, rather than as something that
# happened to one. A melanoma immunotherapy paper names the disease because
# depigmentation was an adverse event, and reading a title and an abstract
# together for the word admitted six of them to a corpus of vitiligo trials.
_STUDIED = re.compile(
    r"""
      (?:patients?|subjects?|participants?|cases?|volunteers?|individuals?|children|adults?)
      \s+(?:\w+\s+){0,3}?with\s+(?:\w+\s+){0,2}?vitiligo
    | vitiligo\s+(?:patients?|subjects?|participants?|cases?|lesions?|skin|vulgaris|areas?)
    | (?:treatment|therapy|management)\s+of\s+(?:\w+\s+){0,2}?vitiligo
    | \bin\s+(?:stable|segmental|non-?segmental|generalized|localized|active)?\s*vitiligo\b
    """,
    re.X | re.I,
)


# A cancer, where the word means a cancer. "Anti-tumor necrosis factor" is a
# cytokine blocker given for arthritis and psoriasis, and reading "tumor" out
# of it called a population-based study of anti-TNF therapy an oncology paper.
ONCOLOGY_CONDITION = re.compile(
    r"melanoma|carcinoma|cancer|neoplas|lymphoma|leukemi|sarcoma|myeloma"
    r"|(?<!necrosis factor)(?<!anti-)tumou?r(?!\s+necrosis)",
    re.I,
)

# The disease as the population rather than as something that happened to one.
_VITILIGO_POPULATION = re.compile(
    r"vitiligo\s+(?:patients?|vulgaris)|\bin\s+vitiligo\b|patients?\s+with\s+vitiligo", re.I
)


def studies_vitiligo(title: str, abstract: str) -> bool:
    """True when the paper's subjects were people with vitiligo.

    A title that names the disease settles it. Otherwise the abstract has to
    name it as who was studied -- "patients with vitiligo", "treatment of
    vitiligo" -- and not merely mention it, because a paper reporting that
    vitiligo-like depigmentation followed a cancer vaccine mentions it too.
    """
    folded = fold(title)
    # A paper whose title names a cancer studied people with that cancer, and
    # vitiligo is what the treatment did to them. Six held records read as
    # vitiligo trials this way -- tebentafusp, pembrolizumab, a GM-CSF
    # melanoma vaccine -- and each belongs in the stratum kept for exactly
    # that, where the population is honestly described as cancer patients.
    if ONCOLOGY_CONDITION.search(folded) and not _VITILIGO_POPULATION.search(folded):
        return False
    if names_vitiligo(title or ""):
        return True
    return bool(_STUDIED.search(fold(abstract)))
