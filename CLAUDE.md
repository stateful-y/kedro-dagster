# Kedro-Dagster

Deploy Kedro projects to Dagster

Instructions for AI coding assistants working in this repository.

**This file is yours.** It is seeded once when the project is generated and never
delivered again: a template update will not overwrite your edits, and there is no
merge to lose. Rewrite it freely. What follows is a starting point, not a contract.

## Project overview

A Python package generated from [python-package-copier](https://github.com/stateful-y/python-package-copier).
Source lives in `src/kedro_dagster/`, tests in `tests/`.

## Critical workflows

- **Package management**: `uv` exclusively. No `pip`, no `venv`.
- **Task running**: `just` (see `just --list`), or `uvx nox` for the CI sessions.
- **Setup**: `just install` creates the lockfile and installs the git hooks.
  The `-f` matters: without it an existing pre-commit shim is chained rather than
  replaced, and both run on every commit.
- **Testing**: `just test-fast` for quick feedback, `just test` for everything.
- **Lint and format**: `just fix`. Tools are pinned by `uv.lock`, so `--locked`
  failures mean the lockfile is stale, not that the tool changed.
- **Docs**: `just serve` to preview, `just build` to build.

## Conventions

- Conventional commits are enforced at commit time and on pull request titles.
- `uv.lock` is tracked and CI runs with `--locked`; commit it with dependency changes.
- Docstrings follow numpydoc. In `References` sections use a markdown ordered list
  with plain `[1]` citations, never reStructuredText (`.. [1]` or `[1]_`), which
  renders literally on the generated API pages.

## What to record here

The things a newcomer cannot derive from the code: why a dependency is pinned, which
assumptions this project breaks relative to the template, what a failing check
actually means. Keep it short enough that it stays true.
