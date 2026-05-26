# Open Questions — Recommended Working Defaults

**Status:** Draft recommendations (May 2026)  
**Purpose:** Provisional decisions so execution can continue. **Founder must confirm or override** — mark each item when finalized.

Use this doc to unblock deploy, outreach, and incorporation. Update README open questions when a item is confirmed.

---

## How to use

| Symbol | Meaning |
|--------|---------|
| **Recommend** | Suggested default if you have no strong preference |
| **Confirm** | You decide; fill in the blank |
| **Defer** | OK to postpone; note date to revisit |

---

## Personal / team

| Question | Recommend | Confirm |
|----------|-----------|---------|
| Time commitment | **Defer formal answer** — ship Phase 1 on evenings/part-time; revisit at first lab partnership | [ ] |
| Co-founders | **Start solo** with 1–2 KOL advisors (not co-founders yet); add technical co-founder only if corpus/engine maintenance exceeds capacity | [ ] |
| Geography / base | **EU-aware, global mission** — host in Amsterdam (`ams`); incorporate where advisor/funder cluster is strongest | [ ] |
| Personal connection | **Confirm in private** — authentic patient/clinician/family link informs outreach tone; not required in public repo | [ ] |
| Financial runway | **Bootstrap Phase 1** (~Fly + API costs < $100/mo); apply for VR Foundation / NIAMS / CZI once methods preprint + advisor letter exist | [ ] |

---

## Strategic

| Question | Recommend | Confirm |
|----------|-----------|---------|
| Hybrid model (AI + lab partners) | **Yes** — core strategy unchanged | [x] working assumption |
| Geographic scope | **Global corpus and tools from day one**; clinical partnerships start EU + US advisors you already reach | [ ] |
| Openness | **Fully open** — Apache 2.0 code, CC-BY graph exports; no open-core paywall on evidence synthesis | [ ] |
| Launch speed vs credibility | **Public beta with guardrails** — live URL + Beta badge + disclaimers + KOL review in parallel (not blocking launch on peer review). Switch to “stable” after advisor sign-off + 30-query eval labeled | [ ] |

**Launch posture detail:** See [`governance-ethics-brief.md`](governance-ethics-brief.md). Recommended sequence:

1. Deploy public beta (this week after `fly auth login`)
2. Email 2–3 advisors with [`kol-share-pack.sh`](../scripts/review/kol-share-pack.sh) output
3. Fix graph/prompt issues from feedback within 2 weeks
4. Remove “beta” or keep until methods preprint posted — advisor call

---

## Operational

| Question | Recommend | Confirm |
|----------|-----------|---------|
| Legal structure | **Defer 501(c)(3) until first grant or donation > $5k** — use **fiscal sponsorship** inquiry (SCIENCE 501, Multiplier, or EU equivalent) OR Dutch ANBI/Stichting if Amsterdam-based. Consult counsel before patient registry | [ ] |
| Organization name | Keep **Vitiligo Initiative** publicly until trademark/domain review; register domain before wide press | [ ] |
| Initial advisors | **2 dermatology KOLs + 1 patient-advocacy bridge** — approach via [`advisor-outreach.md`](advisor-outreach.md); no public listing without written consent | [ ] |

---

## Decisions needed before Phase 2 (registry / patient app)

These can wait until after Evidence Engine v1.0 public:

- IRB jurisdiction (US vs EU vs both)
- Legal entity required before any PHI collection
- Insurance (D&O, cyber) before registry launch
- DPIA / HIPAA assessment timeline

---

## Confirmation log

| Date | Decision | Notes |
|------|----------|-------|
| 2026-05 | Hybrid AI + lab model | README working assumption |
| | Public beta launch | Pending fly deploy |
| | Legal structure | Pending founder + counsel |

---

*When you confirm an item, check the box above and update the [README open questions](../README.md#open-questions) section or remove resolved items.*
