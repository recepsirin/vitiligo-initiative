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

from vitiligo.storage import Trial

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
    vitilig                      # every language's spelling begins this way
    | vtiligo | vilitigo | vitligo  # the three misspellings in the corpus
    | sh?witra                   # Ayurvedic; "shvitra" always appears beside it
    """,
    re.X,
)

# Names this disease shares with others, accepted when nothing disqualifies.
SUGGESTIVE = re.compile(r"leukoderma | leucoderma | white\s+patch", re.X)

# Another cause, another disease, or another tissue entirely.
DISQUALIFYING = re.compile(
    r"""
    # Another cause of the same melanocyte loss.
      post[\s-]?burn | burn\s+scar | rhododenol | chemical\s+leuk | occupational
    | actinic | photoag | photodamag | nonionizing | cutis\s+laxa  # sun-damaged skin
    # Another disease that also presents as a pale patch.
    | idiopathic\s+guttate | \bigh\b | pityriasis | bahaq
    | mycosis\s+fungoides | lichen\s+sclerosus | nevus\s+depigmentosus
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
    lowered = (text or "").lower()
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


def is_drug_class_trial(trial: Trial) -> bool:
    """True when the trial is held for its drug rather than its disease."""
    return str((trial.raw_metadata or {}).get("scope") or "") in DRUG_CLASS_SCOPES


def in_vitiligo_corpus(trial: Trial) -> bool:
    """True when the trial counts towards a figure about vitiligo trials.

    This is the filter behind every published count. Without it, importing a
    drug class's 1,358 trials in other diseases would silently turn "1,027
    vitiligo trials" into a number about rheumatoid arthritis.
    """
    return not is_drug_class_trial(trial)


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
