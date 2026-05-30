# Contributing

Thank you for your interest in the Vitiligo Initiative Evidence Engine. This project is research and education software — not medical advice. See the [README](README.md) disclaimer before using or citing outputs clinically.

## Ways to help

| Channel | Best for |
|---------|----------|
| [GitHub Discussions](https://github.com/recepsirin/vitiligo-initiative/discussions) | Questions, ideas, corpus/search feedback, collaboration |
| [GitHub Issues](https://github.com/recepsirin/vitiligo-initiative/issues) | Confirmed bugs, small scoped feature requests |
| [GitHub Sponsors](https://github.com/sponsors/recepsirin) | Financial support for corpus hosting, compute, and engineering |
| Pull requests | Code, docs, tests, regression fixtures |
| [Security advisories](SECURITY.md) | Vulnerabilities (do **not** open a public issue) |

**Discussions vs issues:** Use Discussions for “how does this work?”, “did anyone try…?”, or open-ended research questions. Open an issue when you have a reproducible bug or a concrete, actionable change.

## Before you start

1. Read [`docs/engine.md`](docs/engine.md) for local setup (Python 3.11+, `pip install -e ".[dev]"`, corpus build).
2. Skim [`docs/architecture.md`](docs/architecture.md) if your change touches ingestion, embeddings, graph, or the web API.
3. Do **not** commit `.env`, API keys, `vitiligo.db`, or other local corpus files.

## Development workflow

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
vitiligo db init   # optional; many tests use temp DBs

# CI-equivalent (what must pass on every PR)
ruff check src tests && ruff format --check src tests
pytest -m "not corpus and not smoke and not confidence"
python scripts/test/build_regression_db.py
pytest -m confidence
```

Full local release gate (optional): `./scripts/audit/smoke-all.sh`. Tests that need the full corpus (`corpus`, `smoke` markers) are documented in [`tests/README.md`](tests/README.md).

## Pull request guidelines

- **One logical change per PR** when possible (bug fix, feature, or docs — not all three).
- **Include tests** for behavior changes. Search/trials/graph/ask bugs should add or extend a case in `tests/fixtures/regression_expectations.json` (see [`tests/README.md`](tests/README.md)).
- **Run ruff and pytest** locally before pushing; CI runs the commands above on Python 3.13.
- **Match existing style** — ruff for lint/format, typed Python in `src/`, Typer CLI patterns, small focused modules.
- **Document user-facing changes** in `CHANGELOG.md` when the behavior or CLI/API surface changes.

## Code style

- **Formatter/linter:** [Ruff](https://docs.astral.sh/ruff/) (`line-length = 100`, double quotes). Run `ruff format src tests` before committing.
- **Types:** Strict mypy on `src/`; new public functions should be typed.
- **Commits:** Clear subject line; body optional for small fixes.

## Adding data sources or API behavior

- New ingest sources: follow patterns in `src/vitiligo/sources/` and [`docs/engine.md`](docs/engine.md).
- Web API changes: add or update tests under `tests/api/` and, if retrieval quality is affected, confidence fixtures.
- LLM prompts (`ask`, `hypothesize`): prefer deterministic tests with fakes in `tests/helpers/fake_llm.py`; avoid live API keys in CI.

## Licensing

By contributing, you agree that your contributions are licensed under the same terms as the project ([Apache 2.0](LICENSE)), except where third-party notices apply ([NOTICE](NOTICE)).

## Questions?

Start a [Discussion](https://github.com/recepsirin/vitiligo-initiative/discussions) — we’d rather answer there than leave you blocked on a half-formed issue.
