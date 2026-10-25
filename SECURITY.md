# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `master` / latest release tag | Yes — security fixes on a best-effort basis for the open Evidence Engine |

Pre-release and local-only experiments are out of scope unless they affect users of a tagged release or the default public deployment path.

## Reporting a vulnerability

**Please do not** open a public GitHub issue for security vulnerabilities (issues are public and may alert attackers before a fix is available).

Report privately through **[GitHub Security Advisories](https://github.com/recepsirin/vitiligo-initiative/security/advisories/new)** (requires Private Vulnerability Reporting to be enabled on the repository).

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
- Rate-limit or resource-exhaustion issues that enable sustained abuse of the public endpoints
- Unsafe deserialization or path traversal in ingestion or export paths

## Out of scope (typically)

- Missing features (e.g. no user accounts yet)
- Social engineering of maintainers
- Issues in third-party services (NCBI, GitHub, Render) — report to those providers
- Prompt injection leading to incorrect **research answers** without a technical flaw in our stack (document as product risk, not always a CVE)
- Vulnerabilities in dependencies already fixed in a newer release we have not yet adopted (please still tell us)

## Safe deployment

Keep API keys in environment variables or platform secrets, never in git, and never serve the corpus directory publicly. Rate limits, proxy hops and LLM caps are set as described in [`docs/deploy.md`](docs/deploy.md).

## Contact and privacy

Project mailboxes (`privacy@` and `contact@vitiligo-initiative.org`) are planned but not active. Until then, privacy requests and corrections go through GitHub Discussions or Issues; security reports go through Security Advisories.

## Legal entity

The Vitiligo Initiative legal entity is not yet finalized. Security reports are handled by the project maintainers in good faith pending incorporation.
