# Contributing

Thank you for your interest in contributing! All contributions - bug reports, fixes, documentation improvements, and feature suggestions - are welcome.

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

For the complete contributing guide - including test strategy, code quality standards, commit conventions, and CI/CD details - see:

**[Full Contributing Guide](docs/pages/contributing.md)**

## Reporting Issues

Found a bug? Have a suggestion? [Open an issue](../../issues/new/choose) and include:

- Python and uv versions
- Steps to reproduce
- Expected vs. actual behavior
