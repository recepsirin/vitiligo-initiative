"""A relation extractor of this project's own, trained and run on this machine.

PubTator reads relations out of abstracts only. This reads the rest -- the
bodies of the full texts, and the text PubTator never sees -- with an encoder
fine-tuned on NCBI's gold BioRED abstracts, and judged on BioRED's held-out
test split before anything it reads reaches the graph. It produces the same
eight relation types PubTator does, so the graph loader that checks
PubTator's relations checks these too.

The model in use is published as re-cep/vitiligo-relation-extractor on
Hugging Face. It is BiomedBERT trained first on PubTator's reading of 11,106
abstracts in this corpus, then on BioRED's 400 training abstracts. On BioRED's
test split it finds a related pair with F1 0.687, and the pair with its
relation type with F1 0.540 (precision 0.559, recall 0.522). The BioRED
paper's PubMedBERT scores 0.729 and 0.589, but reads each pair as a separate
input, which the 821,413 candidate pairs in the full texts would not allow.
Choices were made on the development split and are recorded beside it:

=======================================  ========  =====================
Trained on                                dev F1    test F1 (pair, type)
=======================================  ========  =====================
DeBERTa-v3-base, BioRED                  0.475     0.645, 0.451
BiomedBERT, BioRED                       0.499     0.642, 0.459
BiomedBERT, PubTator's reading here      0.510     0.635, 0.537
BiomedBERT, PubTator's reading, BioRED   0.554     0.687, 0.540
=======================================  ========  =====================

On the 591 abstracts here that training never saw, it agrees with PubTator's
relations with F1 0.611 by type and 0.710 by pair.

Running the model (``model``, ``train``) needs the ``train`` extra (torch,
transformers); ``data``, ``scoring``, ``lexicon`` and ``apply`` are plain
Python and import without it.
"""
