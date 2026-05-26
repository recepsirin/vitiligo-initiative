# Advisor Outreach — Template

**Purpose:** Invite a vitiligo specialist for the first KOL session documented in [`kol-meeting-prep.md`](kol-meeting-prep.md).  
**Send with:** [`scientific-brief.md`](scientific-brief.md) (PDF export optional), link to live or local demo.

---

## Email subject lines (pick one)

- Vitiligo Initiative — 30 min review of open evidence engine (beta)?
- Request: clinical spot-check of vitiligo AI research tool
- Vitiligo evidence synthesis tool — advisor feedback before public launch

---

## Email body (template)

Dear Dr [Name],

I'm building the **Vitiligo Initiative**, a non-profit, open-source **Evidence Engine** that unifies vitiligo literature, trial registries (ClinicalTrials.gov + EU CTR), Open Targets genetics priors, and a structured knowledge graph — to support cited Q&A and ranked therapeutic hypothesis generation.

**Current corpus (May 2026):** ~14k indexed documents (PubMed + PMC + others), 344 registered trials, and a 1k-node graph seeded from priors and trials. The tool is **research-only** (not medical advice); we're seeking advisor input before wider public release.

Would you have **60–90 minutes** in the next few weeks for a structured review? I'd like your help with:

1. **Clinical credibility** — does the demo behave sensibly on JAK/UVB/combination questions?  
2. **Graph sanity check** — are Phase 3 drugs (ruxolitinib, povorcitinib, upadacitinib) correctly linked to vitiligo?  
3. **Prioritization** — review [`candidate-report-v1.md`](candidate-report-v1.md): do the top 10 evidence-scored candidates match your clinical intuition? Which 3–5 merit first lab validation outreach?  
4. **Launch posture** — public beta vs closed advisor access first?

**Materials attached / linked:**
- Advisor pack: run `./scripts/review/kol-share-pack.sh` → attach `exports/kol-share-YYYYMMDD.tar.gz` (includes candidate report + graph + retrieval eval)
- Or individually: scientific brief, [`candidate-report-v1.md`](candidate-report-v1.md), graph export, retrieval eval JSON
- Live demo: [URL or "happy to screen-share locally"]

I'm not asking for endorsement — only honest feedback on errors, gaps, and what would make this useful (or not) for researchers and clinicians you respect.

Happy to work around your schedule. Thank you for considering.

Best,  
[Your name]  
[Title / affiliation if any]  
[GitHub: github.com/recepsirin/vitiligo-initiative]

---

## Follow-up (1 week, no reply)

Dear Dr [Name],

Brief follow-up on the Vitiligo Initiative Evidence Engine review — totally understand if timing isn't right. If easier, even **20 minutes async** (skim the attached graph export + 3 bullet reactions) would be valuable.

If you'd prefer I reach out again after our methods preprint is posted, just say the word.

Best,  
[Your name]

---

## After they accept

1. Send calendar invite with agenda from [`kol-meeting-prep.md`](kol-meeting-prep.md)  
2. Run `./scripts/review/graph-spotcheck.sh` and `vitiligo graph export` fresh  
3. Confirm demo URL works (`./scripts/deploy/verify-public.sh` if deployed)  
4. Collect COI disclosure verbally; note in meeting capture table  

---

## Who to consider (starting list — verify current affiliations)

| Name | Known area | Notes |
|------|------------|-------|
| John E. Harris | JAK / IFN-γ vitiligo immunology | Strong mechanistic fit |
| Iltefat Hamzavi | Clinical trials, repigmentation | Trial design perspective |
| Amit Pandya | Broad vitiligo clinical expert | Field seniority |
| Yan Valle | Patient advocacy + research bridge | VR Foundation |
| Khaled Ezzedine | EU trial landscape | EADV community |

*This is a brainstorm list, not outreach without vetting conflicts and current roles.*

---

## COI ask (verbal or short form)

Please disclose any financial relationships with manufacturers of JAK inhibitors or other vitiligo therapies discussed during the session. We will not publicize your advisor role without written consent.
