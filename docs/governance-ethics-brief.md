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

## Ethical principles (aligned with README operating principles)

1. **Patient safety first** — no tool presents itself as diagnosis or individualized treatment without appropriate regulatory path.  
2. **Scientific integrity** — AI generates hypotheses; biology and peer review validate.  
3. **Transparency** — cite sources, show evidence level, state limits prominently in UI.  
4. **Consent and privacy** — no patient-identifiable data in the public engine; future registry requires explicit consent.  
5. **Equity** — free public access to evidence tools; no paywall on core literature synthesis.  
6. **Non-exploitation** — patient stories and images only with informed consent; no fear-based marketing.  

---

## Evidence Engine (Phase 1) — governance

### What we ship publicly

- Semantic search, Ask, Hypothesize, Graph browse, Trials search over **public literature and trial registries**  
- Rate-limited HTTP API (`VITILIGO_RATE_LIMIT_POST_PER_MINUTE`, default 30/min)  
- Health endpoint without patient data  

### Required disclaimers (UI + API)

Every user-facing surface must state:

> **Research and education tool only.** Not medical advice. Not for emergency use. Discuss treatment decisions with a qualified clinician. AI-generated text may be incomplete or incorrect — verify against cited sources.

### Data processed in Phase 1

| Data type | Source | PHI? | Notes |
|-----------|--------|------|-------|
| PubMed / PMC / GEO metadata | NCBI | No | Public scientific metadata |
| Trial registries | CT.gov, EU CTR, ICTRP | No | Public registry fields |
| Open Targets / DrugBank priors | Public / licensed XML | No | DrugBank requires academic license for full XML |
| User queries (Ask/Hypothesize) | User input | Potentially | **Do not log prompts containing identifiable health info in production without policy** |
| Anthropic API | LLM provider | Query content | Review Anthropic DPA; minimize retention where configurable |

**Action before wide launch:** Publish a short **Privacy Policy** and **Terms of Use** on the deployed site (even if minimal).

### AI-specific risks and mitigations

| Risk | Mitigation |
|------|------------|
| Hallucinated citations | RAG with retrieved docs only; bracketed citations; refusal when evidence thin |
| Overconfident treatment advice | System prompts emphasize uncertainty; evidence-level badges |
| Prompt injection | Input length limits; no tool execution from user text |
| Cost / abuse | Rate limits; optional API key tier later |
| Model vendor change | Configurable `ANTHROPIC_MODEL`; document in changelog |

### Advisor gate (recommended)

Before treating Hypothesize outputs as “initiative endorsements”:

1. KOL review of **knowledge graph export** (`exports/graph-review.json`)  
2. Spot-check of **10 Hypothesize runs** on canonical questions (JAK+UVB, SV vs NSV, acral disease)  
3. Sign-off on **public launch vs closed beta** (see open question in README)  

---

## Future patient-facing tools (Phase 2–3) — preview

Not live yet; governance requirements documented early to avoid rework.

### Patient Tracking App & Registry

- **IRB / ethics committee approval** before enrollment (US IRB or EU REC + GDPR lawful basis)  
- **Informed consent** — purpose (care + research), risks, data sharing, withdrawal  
- **HIPAA** (US) / **GDPR** (EU) — DPIA before launch; data minimization; encryption at rest and in transit  
- **De-identification pipeline** for any shared datasets; controlled access via Data Use Agreement (see README licensing table)  
- **Minor patients** — parental consent; stricter retention rules  

### Clinical Decision Support (CDS)

- Frame as **decision aid**, not autonomous diagnosis  
- US: monitor **FDA CDS guidance** (non-device CDS criteria vs SaMD)  
- EU: **MDR** classification assessment with regulatory counsel before clinician-facing recommendations  
- Validation study plan before marketing to clinicians  

### Automated VASI scoring

- Clinical validation protocol (ICC vs expert graders) before claims of equivalence  
- Transparent failure modes (lighting, skin tone, lesion borders)  

---

## Security baseline (production)

- HTTPS only (host platform enforces TLS — e.g. Render, DigitalOcean, reverse proxy)  
- Secrets in platform vault (`ANTHROPIC_API_KEY` in host env/secrets, not in repo)  
- Database on private volume; no public SQLite download endpoint  
- Dependency scanning via GitHub Actions (CI: pytest + ruff; extend with Dependabot as needed)  
- Incident response: document owner contact; ability to rotate API keys and take app offline  

---

## Intellectual property

| Asset | Policy |
|-------|--------|
| Engine source code | Apache 2.0 |
| Non-patient datasets & graph exports | CC-BY 4.0 |
| Publications | Open access target |
| Patient-derived data | Not open; controlled access only |
| Third-party data | Respect NCBI, CT.gov, Open Targets, DrugBank terms |

No patent-first strategy unless explicitly approved by board/advisors for a narrow defensive purpose.

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
- [x] Disclaimer visible on Ask / Hypothesize tabs (site-wide banner + panel hints)  
- [ ] `ANTHROPIC_API_KEY` set only on server, not client  
- [ ] Rate limits verified  
- [x] KOL skim of graph export OR documented decision to launch with “beta” label (see [`open-questions-resolutions.md`](open-questions-resolutions.md))
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
