# Extracting trial results: the guideline

The rules every number in `trial-results.jsonl` was extracted under. They
exist so that about 1,200 trials read over many sessions are read the same
way, so that code can check what was read, and so that anyone using a number
knows what it means.

## The standards it follows

- **Cochrane Handbook, chapter 5 (collecting data).** A data collection form,
  piloted on a sample before the full run; every item tied to its source.
- **RoB 2 (Sterne et al., BMJ 2019).** The five domains of bias in a
  randomised trial, recorded only as the paper states them.
- **The vitiligo core outcome set** agreed by international e-Delphi
  (Eleftheriadou et al., 2015), which includes repigmentation, its
  maintenance and the cessation of spread. Outcomes are recorded in those
  terms and never merged across definitions.
- **CONSORT** says what a trial report should contain; what it does not
  report is recorded as "not reported", never assumed.

## Who extracts it, and how it is checked

One AI reader extracts every trial; there is no second human or AI
extractor, which is below Cochrane's standard of two. What stands in for
the second reader:

1. **Code verifies every number** (`vitiligo trials verify-results`): its
   quote must occur in the stored source, every number in a value must occur
   in its quote unless marked derived, and the arithmetic must hold.
2. **A blind re-extraction** of a random 10% of trials, done after the first
   pass is out of the reader's context and compared field by field by code.
   The agreement is the consistency figure reported with the data.
3. **Cross-source checks**: a registry posting against the paper of the same
   trial, an abstract against the paper's tables.

The data is labelled accordingly: one AI reader, every number verified
against its source by code, consistency measured on a blind re-extraction,
not human-audited.

### The blind re-extraction (2026-11-07)

125 of the 1,245 worklist trials (10%, seed 20261107), drawn from the 1,033
whose first reading was no longer in the reader's context, were read again
from their sources alone into `trial-results-blind.jsonl`, under the same
code checks. `vitiligo trials compare-results` pairs the two readings' values
on the numbers they share and compares every field. Before any correction:

- **The numbers.** 388 of the first reading's 403 values with numbers (96%)
  were read again. Where both readers recorded a number it was the same:
  counts 206 of 206, percentages 196 of 196, standard deviations 49 of 49,
  medians 19 of 19, confidence limits 6 of 6, means 84 of 85 (68 from an
  abstract against 68.3 from the body), denominators 205 of 209.
- **Completeness.** The second reading recorded 176 values with numbers the
  first had not, most of them from the tables of three full papers.
- **Annotation.** Weeks were added by one reader only in 70 of 198 paired
  values, a threshold in 37 of 85, a denominator in 59 of 268; the population
  differed in 21 of 388 (5%), the value type in 20, the arm's role in 43 of
  379, and a subgroup was written into the arm's name by one reader and into
  its own field by the other in 71.
- **The trial.** Treatment trial or not agreed in 118 of 125, randomisation
  in 107, a within-patient unit in 123, the number enrolled in 118, the
  number of arms in 114.

What it changed. The first reading had written "no" for randomisation where
a paper does not say how patients were allocated; the 121 records answering
"no" with two or more arms were re-read, and 63 became "not reported", one
"yes" (its title calls it randomised), and one "yes" became "no" (the left
limb was always the treated one). 38 title-only records the first reading
had left without design or arms were rebuilt from their titles. Three full
papers took the second reading, which was the more complete and corrected an
imputation label. The figures above are from before these corrections;
rerunning the command now compares against the corrected first reading.

Completing the extraction. The first reading took fewer values from full
papers' tables than they hold, so every record was read again against its
sources. The 52 trials whose body or tables the first reading had not used,
and 10 with five values with numbers or fewer, were read in full. For the
rest, code listed every Results sentence with two or more numbers and every
table row, outside baseline tables, that no value cites or whose numbers the
record does not hold, and every abstract sentence printing a number its
record does not hold; each line was read, then recorded under the same code
checks or left out under a rule (baseline, literature tables, associations
of patient factors, figure legends, pharmacokinetic models), with misprints
and ambiguities flagged. This also gave per-arm numbers to three trials and
found an abstract's "randomised" 66 to be the completers of 72. The check
that kept a value from being added twice was itself checked: four of the
values it held back were different values sharing their numbers and a
common word, and were added. Values rose from 6,490 to 8,696 (6,655 with
numbers). 30 of the 147 trials with a full paper still have five values with
numbers or fewer; their papers report no more (no treatment, a design paper,
a case series, a retraction).

Rerun after this, the comparison pairs 547 of the second reading's 564
values with numbers (97%): 303 of 305 for the 13 trials read from a full
paper, 244 of 259 for the 112 read from an abstract. Every number both
readers recorded is the same. The 17 left unpaired are nine correlations of
patient factors with response, four complements or sums of recorded counts,
two baseline serum levels, a misprint and an ambiguity, none of which the
rules record.

Not captured: exposure-adjusted rates (events or patients per 100
patient-years), for which the record has no field, and numbers printed only
in figures.

### Cross-source checks (2026-11-07)

- **Registry against paper.** `vitiligo trials registry-results` parses the
  posted results of all 30 vitiligo trials that have them into
  `registry-results.jsonl`, 18 of them trials no paper in the store
  reports. For the trials with both, every efficacy number the registry posts
  as primary is printed in a curated paper value, sign aside (a paper's
  improvement is a registry's negative change), except those the papers never
  print: one ruxolitinib dose, one ritlecitinib dose, CXCL10, and absolute
  colour readings where the paper gives changes. The registries' primary
  safety tallies are in the registry file, not in the papers' values.
- **Abstract against its own paper.** Of 267 abstract values whose paper's
  body or tables are held, 15 have no number in them. Two are conflicts and
  are kept from both sources with a flag: an abstract's 69.7% "excellent"
  where the body has 293 of 491 (59.7%), and a mean VASI of 1.269 where the
  body has 1.25. The other 13 are not contradicted, only not printed in the
  body text.

## Scope

- Every distinct vitiligo trial in the corpus, from every source held: the
  registry posting, the abstract, the body and the tables of the paper.
- Only the trial the paper reports. Results of other studies cited in its
  introduction or discussion are not this trial's.
- Registry postings with structured results are parsed by code, not read.

## The record

One line per trial in `trial-results.jsonl`. A *value* is one number: which
arm, which outcome, at what time, in which population, and where it is
printed.

| Part | Fields |
|---|---|
| Trial | `trial` (registry id, or `pmid:`/`doi:` for a trial known only from its paper); `linked` (its other ids); `sources` read |
| Design | `randomised` (yes / no / not reported); `control` (placebo or vehicle / active / untreated side / none); `blinding` as stated; `phase`; `unit` (patient / side / lesion) |
| Population | vitiligo `type` (non-segmental / segmental / mixed / not reported); `activity` (stable / active / not reported); `sites`; `ages` (adults / children / both / not reported); `n_randomised` per arm and in total |
| Arms | `label` as printed; `role` (active / control); each component's `agent`, `dose`, `unit`, `frequency`, `route`, `form`; `phototherapy` (type and schedule); `procedure` (microneedling, laser, grafting) |
| Values | `arm`; `outcome` as printed and normalised (`instrument`, `threshold`, `assessor`); `time` as printed and in weeks; `type` (responders / mean / change / adverse event / relapse / spread); `responders`, `n`, `percent`, `mean`, `sd` or `se`, `median` with its `q1` and `q3`, `ci` and its level, `p` as printed; `population` (`nri` / `as_observed` / `locf` / `per_lesion` / `not_reported`); `derived` (the fields computed rather than printed); `source` and `quote` |
| Risk of bias | the five RoB 2 domains, each `reported` / `not reported` with its quote |
| Flags | anything ambiguous, conflicting or doubtful, in words |

## Rules

1. **No value without a verbatim source.** The quote is copied exactly from
   the stored text; a table value cites its table, row and column and the
   cell as printed.
2. **Nothing is read off a figure.**
3. **Arithmetic only when exact, and labelled.** 12 of 40 may become 30%,
   marked derived. A bare 30% never becomes a count unless n is printed and
   the rounding matches.
4. **Denominators as printed.** `as_observed` is never converted to `nri`; if
   a paper reports both, both are recorded. Last observation carried forward is
   `locf`. When the source does not say how
   missing patients were handled, the population is `not_reported`, never a
   guess.
5. **Split-body and per-lesion trials stay apart.** Their unit is a side or a
   lesion, and their values are never pooled with per-patient ones.
6. **Different outcomes are never merged.** VASI50, "≥50% repigmentation of a
   target lesion" and "good or excellent response" are different measures.
   A grading scale is recorded with its cut-points as printed.
7. **Time is kept as written.** Weeks are added when stated or exactly
   convertible; "month 6" becomes week 26 only as a derived value.
8. **One trial is one trial.** Its registry posting, paper and conference
   abstract are linked, never counted twice. Values that conflict are all
   kept, with their sources, and flagged. A pooled analysis of several trials
   is recorded under the set it pools (`pooled:NCT…+NCT…`), never under one of
   them, and never combined with those trials' own values.
9. **Subgroups are labelled** and never pooled with the main analysis.
10. **Qualitative results stay qualitative.** "Significantly better
    (p<0.05)" is recorded as a direction and the p as printed, never turned
    into an effect size.
11. **Adverse events per arm, as printed**: any, serious, and named events.
12. **Risk of bias only as stated.** Unstated is "not reported".
13. **Retracted papers** and papers under an expression of concern are
    flagged and their values not used.
14. **Ambiguity is flagged, never guessed.** A flagged value is not used in
    any analysis until it is resolved against the source.
15. **Alternation is not randomisation.** Allocation by alternation, date of
    birth or record number is recorded as quasi-randomised, with its quote,
    whatever the paper calls it ("every even patient was put into Group A").
16. **A discussion may restate another trial.** Numbers in a discussion that
    match a cited study are that study's: one paper printed another trial's
    medians as though they were its own.
17. **Impossible arithmetic is a misprint.** A printed value whose own numbers
    contradict each other ("1 (77%)" of 13) is described in the flags and
    not recorded as a value.

## What the pilot changed

The form was piloted on 20 trials drawn at random from the worklist (6 with
tables, 8 PubMed-indexed trials, 6 others) before the full run, as the
Cochrane Handbook advises. It changed the form in nine places: counts written
as words ("Nineteen (86.4%) children"); a value citing several sentences or
cells, because a count and its denominator are often printed apart; a table
value naming its row and column, which code checks; percentages a paper
truncates rather than rounds (20 of 23 printed as 86.9%), accepted to one unit
of the last place; `not_reported` as a population; pooled analyses kept apart;
and rules 15 to 17. Every one of the pilot's 108 values passed the checks.

## Status of a value

- `verified`: its quote is in the source and its arithmetic holds.
- `flagged`: verified, but a reader's doubt is recorded against it.
- `rejected`: it failed a check; kept, with the reason, so the failure can be
  seen and the value re-read.
