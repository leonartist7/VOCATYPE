# Contributing to Vocatype

Thanks for your interest in contributing! This document outlines the workflow,
standards, and conventions we use so contributions land quickly and cleanly.

## Getting Started

1. Fork the repository and clone your fork.
2. Set up the backend and desktop environments (see [README.md](README.md)).
3. Create a branch: `git checkout -b feat/your-change`.
4. Make your changes, then run the quality gates below.
5. Push and open a pull request against `main`.

## Development Setup

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install ruff pytest pytest-asyncio httpx  # dev dependencies
```

```bash
# Desktop
cd desktop
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install ruff pytest pytest-mock
```

## Quality Gates

Every pull request must pass:

1. **Lint** — `ruff check .` (see `pyproject.toml` / `ruff.toml` for the ruleset).
2. **Format** — `ruff format .` (black-compatible formatting).
3. **Tests** — `pytest` from each subproject directory.
4. **CI** — the `test` workflow runs lint + tests on every push/PR.

Run all three locally before pushing. CI will block merges that fail.

## Conventions

### Code style

- Follow [PEP 8](https://peps.python.org/pep-0008/) as enforced by Ruff.
- Type-hint all public functions and modules (`from __future__ import annotations`).
- Keep functions small and single-purpose. Prefer composition over inheritance.
- Use `logger = logging.getLogger(__name__)` in every module; no `print()`.

### Testing

- Tests live in `backend/tests/` and `desktop/tests/`, mirrored to the package layout.
- Never hit the real DeepSeek or whisper models in tests — mock
  `app.services.deepseek._client` and the whisper pipeline instead.
- Cover the happy path plus the error branches (invalid JSON, empty audio, oversized file).

### Commits

- Use [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`.
- Keep each commit focused on a single logical change.
- Never commit `.env` files, API keys, or secrets.

### Versioning

This project follows [Semantic Versioning](https://semver.org/). Release notes are
maintained in [CHANGELOG.md](CHANGELOG.md) using
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## Releasing

Releases are triggered by pushing a `v*.*.*` tag:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The `release` workflow builds desktop binaries (PyInstaller) and the `docker`
workflow publishes the multi-arch backend image to the container registry.
Update `CHANGELOG.md` with the new version's entries before tagging.

## Code of Conduct

Be respectful, constructive, and inclusive. Harassment of any kind will not be
tolerated. If you have concerns, open an issue or contact a maintainer directly.
