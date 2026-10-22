# Trial concept: stop or step down after JAK-induced repigmentation?

A concept for an investigator-initiated trial, aimed at outcome 3 of [what success means](../success.md). **Not a protocol.** It needs a clinical lead, sites, ethics approval and funding.

## The question

After repigmentation on ruxolitinib cream, does a **light maintenance regimen** keep the response better than **stopping**?

**Why this question:**
- **Every responder faces it.** Patients and clinicians must decide whether to continue a costly cream indefinitely.
- **No trial answers it.** The one randomized withdrawal study compared stopping with continuing full treatment ([TRuE-V extension](README.md)). Nothing has tested a step-down.
- **The one maintenance trial was tiny.** Twice-weekly tacrolimus after other treatments had 35 patients, and its intention-to-treat result was inconclusive ([evidence](README.md#across-treatments-durability-is-poor-and-maintenance-may-help)).

## Design

| | |
|---|---|
| **Who** | Adults and adolescents with nonsegmental vitiligo who reached F-VASI75 on ruxolitinib 1.5% cream, approved in the US and EU, after at least 52 weeks |
| **Randomization** | 1:1, double-blind: **twice-weekly tacrolimus 0.1% ointment** on previously affected facial areas vs **vehicle ointment** (stopping) |
| **Primary endpoint** | Time to loss of F-VASI75, over 52 weeks: the TRuE-V definition, so results are comparable |
| **Secondary endpoints** | Loss of F-VASI90; loss of T-VASI50 in those with it; patient-reported noticeability (Vitiligo Noticeability Scale); rescue treatment; cost |
| **Size** | **Event-driven: 66 losses of response** give 80% power to detect a hazard ratio of 0.5 (two-sided 5%). That means about 64–185 patients per arm, depending on how often responses are lost after stopping |
| **Analysis** | Log-rank test and Cox model, pre-registered before enrolment. The result is forecast and sealed beforehand by our models, as a prospective test |

**Choices made, with the alternatives:**
- **Tacrolimus as the maintenance agent.** It is generic and cheap, has one maintenance trial, and its blinding is simple. The alternative, twice-weekly ruxolitinib cream, tests a step-down of the same drug, but costs more. A third arm would cover both, at about 1.5 times the size.
- **Facial F-VASI75 as the primary endpoint.** The face matters most to patients and is the most comparable with TRuE-V. Body response is secondary because it fades more and starts lower.
- **Ruxolitinib cream responders, not oral ones.** The cream is approved and in clinical use, so responders can be found in clinics. Oral JAK inhibitors are not yet approved for vitiligo.

## Sample size

From `scripts/durability/maintenance_trial_size.py` ([`maintenance-trial-size.json`](data/maintenance-trial-size.json)): 80% power, two-sided 5%, 15% dropout, proportional hazards.

| One-year loss after stopping | HR 0.4 | HR 0.5 | HR 0.6 |
|---|---|---|---|
| 27% (TRuE-V, relapse below F-VASI75 after stopping the cream) | 114 per arm | 185 | 321 |
| 58% (sealed oral forecast's median) | 51 | 83 | 144 |
| 73% (TRuE-V, losing a threshold patients sit just above) | 39 | 64 | 112 |

- **The loss rate after stopping is the main unknown.** It depends on how close responders sit to the F-VASI75 threshold. That is why the trial counts events rather than patients.
- **Patients who just cross F-VASI75 lose it more readily** than TRuE-V's near-complete responders did, which favours the top two rows.

## What it would settle

If maintenance halves the risk of relapse, responders can keep most of their repigmentation with a cheap twice-weekly ointment instead of daily cream.
- **A positive result** answers a decision every responder faces.
- **A null result** is also useful: stopping would cost little.

## What is needed

- A clinical lead and sites that treat with ruxolitinib cream.
- Ethics approval, funding, trial registration.
- A statistician.

**Our part:** design support, the pre-registered analysis, and sealed forecasts of the result.
