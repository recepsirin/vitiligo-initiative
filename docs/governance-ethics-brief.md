# Governance & Ethics Brief

**Status:** Draft v0.1 (May 2026)  
**Audience:** Founders, advisors, legal counsel, future IRB  
**Purpose:** Define how the Vitiligo Initiative operates responsibly while shipping open AI tools and, later, patient-facing products.

---

## Scope

This brief covers **Phase 0–1** (planning + public Evidence Engine) and outlines requirements for **Phase 2+** (registry, patient apps, decision support at scale). It is not legal advice; counsel should review before incorporation and any patient data collection.

---

## Organizational posture (working assumptions)

| Topic | Current assumption | To be decided |
|-------|-------------------|---------------|
| **Legal form** | Non-profit mission; EU-aware operations (Amsterdam hosting option) | US 501(c)(3) vs EU foundation vs fiscal sponsor |
| **Name** | “Vitiligo Initiative” (placeholder) | Final public name + domain |
| **Openness** | Open by default — Apache 2.0 code, CC-BY datasets | Whether any components stay private (e.g. advisor-only beta) |
| **Geography** | Global corpus; EU GDPR compliance from day one for EU users | Primary jurisdiction of entity |

---

## Ethical principles (aligned with [strategic plan](strategic-plan.md) operating principles)

1. **Patient safety first** — no tool presents itself as diagnosis or individualized treatment without appropriate regulatory path.  
2. **Scientific integrity** — AI generates hypotheses; biology and peer review validate.  
3. **Transparency** — cite sources, show evidence level, state limits prominently in UI.  
4. **Consent and privacy** — no patient-identifiable data in the public engine; future registry requires explicit consent.  
5. **Equity** — free public access to evidence tools; no paywall on core literature synthesis.  
6. **Non-exploitation** — patient stories and images only with informed consent; no fear-based marketing.  

---

## Evidence Engine (Phase 1) — governance

### What we ship publicly

- Posted trial results, semantic search, graph browse and trials search over **public literature and trial registries**  
- Rate-limited HTTP API (per-client POST limit; see [`deploy.md`](deploy.md))  
- Health endpoint without patient data  

### Required disclaimers (UI + API)

Every user-facing surface must state:

> **Research and education tool only.** Not medical advice. Not for emergency use. Discuss treatment decisions with a qualified clinician. AI-generated text may be incomplete or incorrect — verify against cited sources.

### Data processed in Phase 1

| Data type | Source | PHI? | Notes |
|-----------|--------|------|-------|
| PubMed / PMC / GEO metadata | NCBI | No | Public scientific metadata |
| Trial registries | CT.gov, EU CTR, ISRCTN, ICTRP | No | Public registry fields. ISRCTN and ICTRP records carry investigator names, addresses, telephone numbers and emails; these are stripped before storage, so none is cached or served |
| Open Targets / DrugBank priors | Public / licensed XML | No | DrugBank requires academic license for full XML |
| Search queries | User input | Potentially | Queries are not logged; nothing is sent to a third party, since no model API is called |

**Action before wide launch:** Publish a short **Privacy Policy** and **Terms of Use** on the deployed site (even if minimal).

### AI-specific risks and mitigations

| Risk | Mitigation |
|------|------------|
| Hallucinated citations | RAG with retrieved docs only; bracketed citations; refusal when evidence thin |
| Overconfident treatment advice | Every figure carries its denominator, its analysis population and its comparator; nothing is narrated |
| A rate read as an effect | Comparator shown from the same trial, endpoint and week, or none at all |
| Missing data read as absence | Figures counting only those assessed are bracketed by what the uncounted could have done |
| Cost / abuse | Rate limits; optional API key tier later |

### Advisor gate (recommended)

Before any ranking or extracted figure is presented as an initiative position:

1. KOL review of the **knowledge graph export** (`exports/graph-review.json`)  
2. Clinical review of the **trial-results table** against the registry records it cites, including the analysis population each figure was computed on  
3. Sign-off on **public launch vs closed beta** (open question in the [scientific brief](scientific-brief.md#open-scientific-questions-for-advisors))  

---

## Future patient-facing tools (Phase 2–3)

Not live. Requirements recorded now to avoid rework:

- **Patient tracking app and registry:** ethics approval (IRB or REC) before enrolment; informed consent covering care, research, sharing and withdrawal; HIPAA/GDPR with a DPIA, data minimization and encryption; de-identified sharing only under a data use agreement; parental consent and stricter retention for minors.
- **Clinical decision support:** framed as a decision aid; FDA CDS guidance (US) and MDR classification (EU) reviewed with counsel; a validation study before clinician use.
- **Automated VASI scoring:** validated against expert graders (ICC) before any equivalence claim; failure modes published (lighting, skin tone, lesion borders).

---

## Security baseline (production)

- HTTPS only (host platform enforces TLS — e.g. Render, DigitalOcean, reverse proxy)  
- No secrets in the deployment, and none in the engine: it calls no model API, so there is no key to vault, leak or rotate  
- Database on private volume; no public SQLite download endpoint  
- Dependency scanning via GitHub Actions (CI: pytest + ruff) and Dependabot (pip + Actions)  
- Incident response: document owner contact; ability to rotate API keys and take app offline  

---

## Intellectual property

Licensing follows the [strategic plan](strategic-plan.md#licensing): Apache 2.0 code, CC-BY 4.0 non-patient data, open-access publications, controlled access for patient data. Third-party terms (NCBI, CT.gov, Open Targets, DrugBank) apply. No patent-first strategy unless the board or advisors approve a narrow defensive use.

---

## Conflicts of interest

Advisors and collaborators should disclose:

- Industry relationships (pharma, device)  
- Financial interest in therapies discussed by the engine  
- Institutional trials overlapping with initiative priorities  

COI will be collected in writing before advisor role is publicized.

---

## Decision rights (interim, pre-board)

Until a formal board exists:

| Decision | Who |
|----------|-----|
| Public deploy of Evidence Engine | Founders + at least one KOL advisor concurrence |
| Patient data collection | Founders + IRB; no collection without approval |
| External claims (“we recommend X”) | Forbidden without validation study + advisor review |
| Licensing exceptions to open default | Documented rationale; advisor visibility |

---

## Checklist before public URL goes live

- [ ] Public deploy complete; `/api/health` shows `ready: true`  
- [x] Privacy Policy + Terms linked from footer (`/privacy`, `/terms`)  
- [x] Disclaimer visible site-wide (banner plus per-panel notes)  
- [ ] Deployment carries no API key at all (the served app makes no model call)  
- [ ] Rate limits verified  
- [x] KOL skim of graph export OR documented decision to launch with “beta” label
- [ ] Contact email for corrections / takedown requests — **parked:** domain not purchased; use GitHub per [SECURITY.md](../SECURITY.md) until `contact@` / `privacy@` are live  

---

## Checklist before first registry enrollment

- [ ] Legal entity + insurance  
- [ ] IRB / REC approval  
- [ ] Consent forms and privacy notice  
- [ ] DPIA / HIPAA security assessment  
- [ ] Data retention and deletion policy  
- [ ] Breach notification procedure  

---

*Draft for advisor review. Becomes v1.0 after legal review and first KOL meeting.*
