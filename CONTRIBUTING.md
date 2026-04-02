# Contributing

Thank you for your interest in contributing! We welcome all contributions, whether bug reports, fixes, documentation improvements, or feature suggestions.

Please review our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

## Quick Setup

```bash
git clone <repo-url>
cd <project-dir>
uv sync --group dev
uv run pre-commit install
just test-fast
```

## Full Guidelines

The complete contributing guide covers test strategy, code quality standards, commit conventions, and CI/CD details:

**[Full Contributing Guide](docs/pages/how-to/contribute.md)**

## Reporting Issues

Found a bug? Have a suggestion? [Open an issue](../../issues/new/choose) and include:

- Python and uv versions
- Steps to reproduce
- Expected vs. actual behavior
