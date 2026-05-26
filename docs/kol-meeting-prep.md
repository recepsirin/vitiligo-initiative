# KOL Advisor Meeting — Prep Pack

**Purpose:** First structured session with a vitiligo specialist advisor, **with the Evidence Engine live** (local or public URL).  
**Duration:** 60–90 minutes  
**Materials to send 48h ahead:** this doc, [`scientific-brief.md`](scientific-brief.md), [`candidate-report-v1.md`](candidate-report-v1.md), `exports/graph-review.json` (or full KOL pack from `./scripts/review/kol-share-pack.sh`)

---

## Goals

1. Validate that the **Evidence Engine demo** is credible enough to show colleagues  
2. Spot-check **knowledge graph v1** for obvious errors or missing Phase 3 drugs  
3. Agree on **3–5 priority hypotheses** for first validation outreach  
4. Decide **public launch vs closed beta** and advisor COI/disclosure norms  

---

## Pre-meeting (you)

```bash
# Automated checks
./scripts/review/graph-spotcheck.sh
vitiligo graph export -o exports/graph-review.json

# If not yet deployed publicly, run locally
vitiligo serve   # http://127.0.0.1:8765
```

Share URL: `https://vitiligo-evidence-engine.fly.dev` (after deploy) or a scheduled screen share.

---

## Agenda

| Time | Topic |
|------|-------|
| 0–10 min | Mission, non-goals, what we are / are not claiming |
| 10–25 min | **Live demo:** Search → Ask → Hypothesize → **Candidates** → Graph → Trials |
| 25–40 min | **Graph review:** vitiligo neighbors, JAK drugs, top targets |
| 40–55 min | **Candidate report review:** top 10 from **Candidates** tab or [`candidate-report-v1.md`](candidate-report-v1.md) |
| 55–65 min | **Validation proposals:** skim [`validation-proposals/`](validation-proposals/) one-pagers |
| 65–75 min | **Governance:** disclaimers, launch posture, advisor role |
| 75–90 min | Next steps: intro to translational labs, methods paper co-authorship interest |

---

## Demo script (canonical questions)

Use these in order so evidence streams are visible:

1. **Search:** `JAK inhibitor repigmentation non-segmental vitiligo`  
2. **Ask:** `What is the evidence for combining topical ruxolitinib with NB-UVB?`  
3. **Hypothesize:** `Stop spread of active non-segmental vitiligo`  
4. **Candidates:** open **Candidates** tab — review deterministic top 10 (same as [`candidate-report-v1.md`](candidate-report-v1.md))  
5. **Graph:** search `ruxolitinib`, browse neighbors; search `JAK1`  
6. **Trials:** filter `RECRUITING` + Phase 3  

Ask advisor to note: wrong citations, missing pivotal trials, overconfident LLM text.

---

## Questions for the advisor

### Scientific

1. Is the **IFN-γ / JAK framing** reflected correctly in our top hypotheses?  
2. Which **combinations** are most under-studied but clinically plausible?  
3. **Segmental vs NSV** — should we split the engine’s default prompts?  
4. **Acral vitiligo** — any trials or mechanisms we failed to ingest?  

### Graph quality

1. Are **povorcitinib, upadacitinib, ritlecitinib** correctly linked to vitiligo?  
2. Any **spurious drug–disease** edges from Open Targets noise?  
3. Missing **trial sponsors** or EU-only studies clinicians care about?  

### Product / ethics

1. Comfortable with **public URL** now, or **password beta** for 4–8 weeks?  
2. Wording of **medical disclaimer** — sufficient for your institution?  
3. Willing to be named advisor publicly? COI to disclose?  

### Introductions

1. **2–3 translational labs** for first validation proposals?  
2. **Conference** (EADV / World Vitiligo Congress) to target for methods abstract?  

---

## Capture template (during meeting)

| Item | Advisor feedback | Action owner |
|------|------------------|--------------|
| Graph errors | | |
| Hypothesis #1 | | |
| Hypothesis #2 | | |
| Launch decision | public / beta / delay | |
| Lab intro | | |
| Follow-up date | | |

---

## After meeting

- [ ] Update graph seed / priors from advisor corrections  
- [ ] Re-run `./scripts/review/graph-spotcheck.sh`  
- [ ] Log decisions in README open questions where resolved  
- [ ] Send thank-you + link to exported graph + meeting notes  
