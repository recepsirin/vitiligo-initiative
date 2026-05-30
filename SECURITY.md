# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `master` / latest release tag | Yes — security fixes on a best-effort basis for the open Evidence Engine |

Pre-release and local-only experiments are out of scope unless they affect users of a tagged release or the default public deployment path.

## Reporting a vulnerability

**Please do not** open a public GitHub issue for security vulnerabilities (issues are public and may alert attackers before a fix is available).

Report privately via **GitHub** (domain and project mailboxes are not set up yet):

- **[GitHub Security Advisories](https://github.com/recepsirin/vitiligo-initiative/security/advisories/new)** (preferred for vulnerabilities), or  
- Email the maintainers listed on the repository if you already have a private channel.

When `vitiligo-initiative.org` is live, we plan to use **contact@vitiligo-initiative.org** for security and corrections. Until then, use GitHub (see below and the Privacy/Terms pages).

Include:

- Description of the issue and impact
- Steps to reproduce (or proof of concept)
- Affected component (CLI, web API, ingestion, deployment)
- Your contact if you are open to follow-up

We aim to acknowledge reports within **5 business days**. We will work on a fix or mitigation and coordinate disclosure when appropriate.

## What to report

Examples we care about:

- Remote code execution or SQL injection in the web API
- Authentication or authorization bypass (if auth is added later)
- Secrets committed to the repository or logged in production
- Rate-limit or resource-exhaustion issues that enable sustained abuse of paid LLM endpoints
- Unsafe deserialization or path traversal in ingestion or export paths

## Out of scope (typically)

- Missing features (e.g. no user accounts yet)
- Social engineering of maintainers
- Issues in third-party services (Anthropic, NCBI, GitHub, Render) — report to those providers
- Prompt injection leading to incorrect **research answers** without a technical flaw in our stack (document as product risk, not always a CVE)
- Vulnerabilities in dependencies already fixed in a newer release we have not yet adopted (please still tell us)

## Safe deployment reminders

- Keep `ANTHROPIC_API_KEY` and `NCBI_API_KEY` in environment variables or platform secrets — **never** in git
- Do not expose the SQLite corpus directory as a public download endpoint without access controls
- Keep `VITILIGO_RATE_LIMIT_POST_PER_MINUTE` enabled on public deployments (default: 30)
- Restart the web service after replacing `vitiligo.db` on disk so caches reload cleanly

## Contact and privacy (planned)

| Purpose | Status |
|---------|--------|
| Security reports | **GitHub Security Advisories** (see above) until domain mail is live |
| Privacy / data requests | Planned: `privacy@vitiligo-initiative.org` — not active yet |
| Corrections to indexed public records | Planned: `contact@vitiligo-initiative.org` — not active yet |

Privacy and Terms pages link to GitHub Discussions and Issues until project mailboxes exist.

## Legal entity

The Vitiligo Initiative legal entity is not yet finalized. Security reports are handled by the project maintainers in good faith pending incorporation.
